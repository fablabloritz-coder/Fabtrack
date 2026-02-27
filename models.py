"""
FabTrack v2 — Modèles de base de données SQLite
Schéma enrichi : fiches techniques machines, catégories référents,
types d'activité paramétrables, données de démonstration, réinitialisation.
Matériaux liés aux machines via table de jonction (pas de doublons).
Consommations dénormalisées (noms en brut) pour résilience aux suppressions.
"""

import sqlite3
import os
import random
from datetime import datetime, timedelta

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fabtrack.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ============================================================
# INITIALISATION & MIGRATION
# ============================================================

def init_db():
    conn = get_db()
    c = conn.cursor()

    c.executescript('''
    CREATE TABLE IF NOT EXISTS preparateurs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        image_path TEXT DEFAULT '',
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS types_activite (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        icone TEXT DEFAULT '',
        couleur TEXT DEFAULT '#2563eb',
        badge_class TEXT DEFAULT '',
        unite_defaut TEXT DEFAULT '',
        image_path TEXT DEFAULT '',
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS machines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        type_activite_id INTEGER NOT NULL,
        quantite INTEGER DEFAULT 1,
        marque TEXT DEFAULT '',
        zone_travail TEXT DEFAULT '',
        puissance TEXT DEFAULT '',
        photo_url TEXT DEFAULT '',
        image_path TEXT DEFAULT '',
        description TEXT DEFAULT '',
        statut TEXT DEFAULT 'disponible',
        notes TEXT DEFAULT '',
        raison_reparation TEXT DEFAULT '',
        date_reparation TEXT DEFAULT '',
        principes_conception TEXT DEFAULT '',
        actif INTEGER DEFAULT 1,
        FOREIGN KEY (type_activite_id) REFERENCES types_activite(id)
    );

    CREATE TABLE IF NOT EXISTS materiaux (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        unite TEXT DEFAULT '',
        image_path TEXT DEFAULT '',
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS materiau_machine (
        materiau_id INTEGER NOT NULL,
        machine_id INTEGER NOT NULL,
        PRIMARY KEY (materiau_id, machine_id),
        FOREIGN KEY (materiau_id) REFERENCES materiaux(id) ON DELETE CASCADE,
        FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        image_path TEXT DEFAULT '',
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS referents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        categorie TEXT DEFAULT 'Professeur',
        image_path TEXT DEFAULT '',
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS consommations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_saisie TEXT NOT NULL,
        preparateur_id INTEGER,
        type_activite_id INTEGER,
        machine_id INTEGER,
        classe_id INTEGER,
        referent_id INTEGER,
        materiau_id INTEGER,
        nom_preparateur TEXT DEFAULT '',
        nom_type_activite TEXT DEFAULT '',
        nom_machine TEXT DEFAULT '',
        nom_classe TEXT DEFAULT '',
        nom_referent TEXT DEFAULT '',
        nom_materiau TEXT DEFAULT '',
        quantite REAL DEFAULT 0,
        unite TEXT DEFAULT '',
        poids_grammes REAL,
        longueur_mm REAL,
        largeur_mm REAL,
        surface_m2 REAL,
        epaisseur TEXT,
        nb_feuilles INTEGER,
        format_papier TEXT,
        nb_feuilles_plastique INTEGER,
        type_feuille TEXT,
        commentaire TEXT DEFAULT '',
        impression_couleur TEXT DEFAULT '',
        projet_nom TEXT DEFAULT '',
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime'))
    );

    CREATE INDEX IF NOT EXISTS idx_conso_date ON consommations(date_saisie);
    CREATE INDEX IF NOT EXISTS idx_conso_type ON consommations(type_activite_id);
    CREATE INDEX IF NOT EXISTS idx_conso_prep ON consommations(preparateur_id);
    CREATE INDEX IF NOT EXISTS idx_conso_mach ON consommations(machine_id);

    CREATE TABLE IF NOT EXISTS custom_fields (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        field_name TEXT NOT NULL,
        field_label TEXT NOT NULL,
        field_type TEXT DEFAULT 'text',
        options TEXT DEFAULT '',
        obligatoire INTEGER DEFAULT 0,
        position INTEGER DEFAULT 0,
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS custom_field_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id INTEGER NOT NULL,
        custom_field_id INTEGER NOT NULL,
        value TEXT DEFAULT '',
        FOREIGN KEY (custom_field_id) REFERENCES custom_fields(id)
    );
    ''')

    _migrate_db(c)
    _insert_reference_data(c)
    conn.commit()
    conn.close()
    print("[FabTrack] Base de données initialisée.")


def _migrate_db(c):
    """Ajoute les colonnes manquantes pour les bases existantes."""
    mcols = [r[1] for r in c.execute("PRAGMA table_info(machines)").fetchall()]
    for col, spec in {'quantite':'INTEGER DEFAULT 1','marque':"TEXT DEFAULT ''",'zone_travail':"TEXT DEFAULT ''",'puissance':"TEXT DEFAULT ''",'photo_url':"TEXT DEFAULT ''",'description':"TEXT DEFAULT ''",'statut':"TEXT DEFAULT 'disponible'",'image_path':"TEXT DEFAULT ''",'notes':"TEXT DEFAULT ''",'raison_reparation':"TEXT DEFAULT ''",'date_reparation':"TEXT DEFAULT ''",'principes_conception':"TEXT DEFAULT ''"}.items():
        if col not in mcols:
            c.execute(f"ALTER TABLE machines ADD COLUMN {col} {spec}")

    rcols = [r[1] for r in c.execute("PRAGMA table_info(referents)").fetchall()]
    if 'categorie' not in rcols:
        c.execute("ALTER TABLE referents ADD COLUMN categorie TEXT DEFAULT 'Professeur'")
    if 'image_path' not in rcols:
        c.execute("ALTER TABLE referents ADD COLUMN image_path TEXT DEFAULT ''")

    tcols = [r[1] for r in c.execute("PRAGMA table_info(types_activite)").fetchall()]
    if 'unite_defaut' not in tcols:
        c.execute("ALTER TABLE types_activite ADD COLUMN unite_defaut TEXT DEFAULT ''")
    if 'actif' not in tcols:
        c.execute("ALTER TABLE types_activite ADD COLUMN actif INTEGER DEFAULT 1")
    if 'image_path' not in tcols:
        c.execute("ALTER TABLE types_activite ADD COLUMN image_path TEXT DEFAULT ''")

    # Migration image_path pour les autres tables
    for tbl in ('preparateurs', 'materiaux', 'classes'):
        cols = [r[1] for r in c.execute(f"PRAGMA table_info({tbl})").fetchall()]
        if 'image_path' not in cols:
            c.execute(f"ALTER TABLE {tbl} ADD COLUMN image_path TEXT DEFAULT ''")

    # Migration impression_couleur pour consommations
    ccols = [r[1] for r in c.execute("PRAGMA table_info(consommations)").fetchall()]
    if 'impression_couleur' not in ccols:
        c.execute("ALTER TABLE consommations ADD COLUMN impression_couleur TEXT DEFAULT ''")
    if 'projet_nom' not in ccols:
        c.execute("ALTER TABLE consommations ADD COLUMN projet_nom TEXT DEFAULT ''")

    # Colonnes dénormalisées pour résilience aux suppressions
    for col in ('nom_preparateur','nom_type_activite','nom_machine','nom_classe','nom_referent','nom_materiau'):
        if col not in ccols:
            c.execute(f"ALTER TABLE consommations ADD COLUMN {col} TEXT DEFAULT ''")

    # Migration matériaux : retirer type_activite_id (anciens schémas)
    matcols = [r[1] for r in c.execute("PRAGMA table_info(materiaux)").fetchall()]
    if 'type_activite_id' in matcols:
        _migrate_materiaux_to_junction(c)

    # Remplir les noms dénormalisés pour les consommations existantes qui n'en ont pas
    _backfill_denormalized_names(c)


def _migrate_materiaux_to_junction(c):
    """Migre l'ancien schéma materiaux (avec type_activite_id) vers le nouveau (junction table)."""
    print("[FabTrack] Migration matériaux → table de jonction...")

    # Créer la table de jonction si elle n'existe pas
    c.execute('''CREATE TABLE IF NOT EXISTS materiau_machine (
        materiau_id INTEGER NOT NULL,
        machine_id INTEGER NOT NULL,
        PRIMARY KEY (materiau_id, machine_id),
        FOREIGN KEY (materiau_id) REFERENCES materiaux(id) ON DELETE CASCADE,
        FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE
    )''')

    # Lire les anciens matériaux avec leur type_activite_id
    old_mats = c.execute('SELECT id, nom, type_activite_id, unite, image_path, actif FROM materiaux').fetchall()

    # Grouper par nom → garder un seul matériau par nom, fusionner les type_activite_id
    from collections import defaultdict
    by_name = defaultdict(list)
    for mid, nom, taid, unite, img, actif in old_mats:
        by_name[nom].append({'id': mid, 'type_activite_id': taid, 'unite': unite, 'image_path': img, 'actif': actif})

    # Recréer la table materiaux sans type_activite_id
    c.execute('ALTER TABLE materiaux RENAME TO materiaux_old')
    c.execute('''CREATE TABLE materiaux (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        unite TEXT DEFAULT '',
        image_path TEXT DEFAULT '',
        actif INTEGER DEFAULT 1
    )''')

    # Pour chaque nom unique, insérer un seul matériau et créer les liens machine
    id_mapping = {}  # old_id → new_id
    for nom, entries in by_name.items():
        best = entries[0]
        c.execute('INSERT INTO materiaux (nom, unite, image_path, actif) VALUES (?,?,?,?)',
                  (nom, best['unite'], best['image_path'] or '', best['actif']))
        new_id = c.lastrowid
        for e in entries:
            id_mapping[e['id']] = new_id
            # Trouver les machines liées à ce type_activite_id
            machines = c.execute('SELECT id FROM machines WHERE type_activite_id=?', (e['type_activite_id'],)).fetchall()
            for (mach_id,) in machines:
                c.execute('INSERT OR IGNORE INTO materiau_machine (materiau_id, machine_id) VALUES (?,?)',
                          (new_id, mach_id))

    # Mettre à jour les consommations pour pointer vers les nouveaux IDs
    for old_id, new_id in id_mapping.items():
        if old_id != new_id:
            c.execute('UPDATE consommations SET materiau_id=? WHERE materiau_id=?', (new_id, old_id))

    c.execute('DROP TABLE materiaux_old')
    print("[FabTrack] Migration matériaux terminée.")


def _backfill_denormalized_names(c):
    """Remplit les colonnes nom_* pour les consommations existantes."""
    c.execute('''UPDATE consommations SET
        nom_preparateur = COALESCE((SELECT nom FROM preparateurs WHERE id=consommations.preparateur_id), nom_preparateur),
        nom_type_activite = COALESCE((SELECT nom FROM types_activite WHERE id=consommations.type_activite_id), nom_type_activite),
        nom_machine = COALESCE((SELECT nom FROM machines WHERE id=consommations.machine_id), nom_machine),
        nom_classe = COALESCE((SELECT nom FROM classes WHERE id=consommations.classe_id), nom_classe),
        nom_referent = COALESCE((SELECT nom FROM referents WHERE id=consommations.referent_id), nom_referent),
        nom_materiau = COALESCE((SELECT nom FROM materiaux WHERE id=consommations.materiau_id), nom_materiau)
        WHERE nom_preparateur IS NULL OR nom_preparateur = ''
    ''')


# ============================================================
# DONNÉES DE RÉFÉRENCE (parc réel Loritz)
# ============================================================

def _insert_reference_data(c):
    # Pas de préparateurs par défaut — à configurer par chaque fablab

    types = [
        ('Impression 3D','🖨️','#f59e0b','badge-3d','g'),
        ('Découpe Laser','⚡','#ef4444','badge-laser','m²'),
        ('CNC / Fraisage','⚙️','#3b82f6','badge-cnc','m²'),
        ('Impression Papier','📄','#22c55e','badge-papier','feuilles'),
        ('Thermoformage','🔥','#a855f7','badge-thermo','feuilles'),
        ('Bricolage','🔧','#6366f1','badge-bricolage',''),
        ('Broderie','🧵','#ec4899','badge-broderie',''),
    ]
    for nom,icone,couleur,badge,unite in types:
        c.execute('INSERT OR IGNORE INTO types_activite (nom,icone,couleur,badge_class,unite_defaut) VALUES (?,?,?,?,?)',
                  (nom,icone,couleur,badge,unite))
        c.execute('UPDATE types_activite SET unite_defaut=? WHERE nom=? AND (unite_defaut IS NULL OR unite_defaut="")',
                  (unite,nom))

    c.execute('SELECT id,nom FROM types_activite')
    tmap = {r[1]:r[0] for r in c.fetchall()}

    # Principes de conception par type d'activité
    principes_map = {
        'Impression 3D': 'ajout',
        'Découpe Laser': 'enlevement',
        'CNC / Fraisage': 'enlevement',
        'Thermoformage': 'deformation',
        'Broderie': 'ajout',
    }

    machines = {
        'Impression 3D': [
            ('Creality CR10-S',2,'Creality','300×300×400 mm','','Imprimante 3D FDM grand format'),
            ('Creality Ender 3',1,'Creality','220×220×250 mm','','Imprimante 3D FDM compacte'),
            ('Raise 3D Pro',1,'Raise3D','305×305×305 mm','','Imprimante 3D FDM professionnelle'),
            ('Raise 3D Pro 2',1,'Raise3D','305×305×300 mm','','Imprimante 3D FDM double extrudeur'),
            ('Raise 3D Pro 3',1,'Raise3D','300×300×300 mm','','Imprimante 3D FDM dernière génération'),
            ('Creabot D600',1,'Creabot','600×600×600 mm','','Imprimante 3D FDM très grand format'),
        ],
        'Thermoformage': [
            ('Formech 300XQ',1,'Formech','300×300 mm','1500W','Thermoformeuse compacte'),
        ],
        'Découpe Laser': [
            ('JAMP 78 Moy',1,'JAMP','780×460 mm','80W CO2','Découpeuse laser CO2 format moyen'),
        ],
        'Impression Papier': [
            ('Kyocera',1,'Kyocera','','','Imprimante laser multifonction'),
            ('Epson Eco-tank',1,'Epson','','','Imprimante jet d\'encre éco-réservoir'),
            ('Traceur HP',1,'HP','Grand format','','Traceur grand format'),
        ],
        'CNC / Fraisage': [
            ('Grande strato',1,'','1200×900 mm','','Fraiseuse CNC grand format'),
            ('Petite strato',1,'','600×450 mm','','Fraiseuse CNC format moyen'),
        ],
    }
    for tnom, mlist in machines.items():
        tid = tmap.get(tnom)
        if not tid: continue
        principes = principes_map.get(tnom, '')
        for nom,qte,marque,zone,puiss,desc in mlist:
            if not c.execute('SELECT 1 FROM machines WHERE nom=? AND type_activite_id=?',(nom,tid)).fetchone():
                c.execute('INSERT INTO machines (nom,type_activite_id,quantite,marque,zone_travail,puissance,description,principes_conception) VALUES (?,?,?,?,?,?,?,?)',
                          (nom,tid,qte,marque,zone,puiss,desc,principes))
            else:
                c.execute('UPDATE machines SET principes_conception=? WHERE nom=? AND type_activite_id=? AND (principes_conception IS NULL OR principes_conception="")',
                          (principes, nom, tid))

    # Matériaux uniques — chacun inséré UNE SEULE FOIS, puis lié aux machines
    # Format: (nom, unite, image_path, [noms_machines_liées])
    # Si la liste de machines est vide → matériau générique (visible pour activités sans machine)
    materiaux_seed = [
        # Impression 3D
        ('PLA','g','/static/img/pla.png',['Creality CR10-S','Creality Ender 3','Raise 3D Pro','Raise 3D Pro 2','Raise 3D Pro 3','Creabot D600']),
        ('PETG','g','/static/img/petg.png',['Creality CR10-S','Creality Ender 3','Raise 3D Pro','Raise 3D Pro 2','Raise 3D Pro 3','Creabot D600']),
        ('ABS','g','/static/img/abs.png',['Creality CR10-S','Creality Ender 3','Raise 3D Pro','Raise 3D Pro 2','Raise 3D Pro 3','Creabot D600']),
        ('TPU','g','/static/img/tpu.png',['Creality CR10-S','Creality Ender 3','Raise 3D Pro','Raise 3D Pro 2','Raise 3D Pro 3','Creabot D600']),
        # Découpe Laser + CNC
        ('MDF 3mm','m²','/static/img/mdf.png',['JAMP 78 Moy','Grande strato','Petite strato']),
        ('MDF 6mm','m²','/static/img/mdf.png',['JAMP 78 Moy','Grande strato','Petite strato']),
        ('MDF 8mm','m²','/static/img/mdf.png',['JAMP 78 Moy','Grande strato','Petite strato']),
        ('MDF 10mm','m²','/static/img/mdf.png',['JAMP 78 Moy','Grande strato','Petite strato']),
        ('MDF 12mm','m²','/static/img/mdf.png',['JAMP 78 Moy','Grande strato','Petite strato']),
        ('PLEXI 3mm','m²','/static/img/plexi.png',['JAMP 78 Moy','Grande strato','Petite strato']),
        ('PLEXI 6mm','m²','/static/img/plexi.png',['JAMP 78 Moy','Grande strato','Petite strato']),
        ('PLEXI 20mm','m²','/static/img/plexi.png',['JAMP 78 Moy','Grande strato','Petite strato']),
        ('Contre-plaqué','m²','/static/img/contre_plaqué.png',['JAMP 78 Moy','Grande strato','Petite strato']),
        # CNC uniquement
        ('Carton 5mm','m²','/static/img/carton.png',['Grande strato','Petite strato']),
        ('Carton 13mm','m²','/static/img/carton.png',['Grande strato','Petite strato']),
        ('Mousse usinée','m²','/static/img/mousse.png',['Grande strato','Petite strato']),
        ('Aluminium','m²','/static/img/alu.png',['Grande strato','Petite strato']),
        ('Polystyrène extrudé','m²','/static/img/polystyrene_extrude.png',['Grande strato','Petite strato']),
        # Impression Papier
        # Traceur HP : A0→A5, Couleur + N&B
        ('Papier A0 Couleur','feuilles','/static/img/papier_a0.png',['Traceur HP']),
        ('Papier A0 N&B','feuilles','/static/img/papier_a0_noir_et_blanc.png',['Traceur HP']),
        ('Papier A1 Couleur','feuilles','/static/img/papier_a1.png',['Traceur HP']),
        ('Papier A1 N&B','feuilles','/static/img/papier_a1_noir_et_blanc.png',['Traceur HP']),
        ('Papier A2 Couleur','feuilles','/static/img/papier_a2.png',['Traceur HP']),
        ('Papier A2 N&B','feuilles','/static/img/papier_a2_noir_et_blanc.png',['Traceur HP']),
        # Kyocera : A3 + A4, N&B uniquement (pas de couleur)
        ('Papier A3 Couleur','feuilles','/static/img/papier_a3.png',['Traceur HP']),
        ('Papier A3 N&B','feuilles','/static/img/papier_a3_noir_et_blanc.png',['Kyocera','Traceur HP']),
        # Epson Eco-tank : A4 uniquement, Couleur + N&B
        ('Papier A4 Couleur','feuilles','/static/img/papier_a4.png',['Epson Eco-tank','Traceur HP']),
        ('Papier A4 N&B','feuilles','/static/img/papier_a4_noir_et_blanc.png',['Kyocera','Epson Eco-tank','Traceur HP']),
        ('Papier A5 Couleur','feuilles','/static/img/papier_a5.png',['Traceur HP']),
        ('Papier A5 N&B','feuilles','/static/img/papier_a5_noir_et_blanc.png',['Traceur HP']),
        # Thermoformage
        ('Feuille opaque','feuilles','',['Formech 300XQ']),
        ('Feuille transparente','feuilles','',['Formech 300XQ']),
    ]
    for nom, unite, img, linked_machines in materiaux_seed:
        c.execute('INSERT OR IGNORE INTO materiaux (nom, unite, image_path) VALUES (?,?,?)',
                  (nom, unite, img))
        mat_id = c.execute('SELECT id FROM materiaux WHERE nom=?', (nom,)).fetchone()[0]
        for mnom in linked_machines:
            row = c.execute('SELECT id FROM machines WHERE nom=?', (mnom,)).fetchone()
            if row:
                c.execute('INSERT OR IGNORE INTO materiau_machine (materiau_id, machine_id) VALUES (?,?)',
                          (mat_id, row[0]))

    # Pas de classes par défaut — à configurer par chaque fablab
    # Les classes et préparateurs peuvent être ajoutés via les paramètres ou la démo



# ============================================================
# RÉINITIALISATION
# ============================================================

def reset_db():
    """Réinitialise la base : supprime tout et recrée avec machines et matériaux par défaut.
    Les classes, préparateurs et référents sont vidés (non recréés)."""
    conn = get_db()
    conn.cursor().executescript('''
        DROP TABLE IF EXISTS custom_field_values; DROP TABLE IF EXISTS custom_fields;
        DROP TABLE IF EXISTS consommations; DROP TABLE IF EXISTS materiau_machine;
        DROP TABLE IF EXISTS machines;
        DROP TABLE IF EXISTS materiaux; DROP TABLE IF EXISTS classes;
        DROP TABLE IF EXISTS referents;
        DROP TABLE IF EXISTS preparateurs; DROP TABLE IF EXISTS types_activite;
    ''')
    conn.commit(); conn.close()
    init_db()
    print("[FabTrack] Base RÉINITIALISÉE (machines & matériaux par défaut).")


# ============================================================
# DONNÉES DE DÉMONSTRATION
# ============================================================

def generate_demo_data():
    """Génère ~150 consommations fictives + classes, préparateurs et référents fictifs."""
    conn = get_db(); c = conn.cursor()

    # Préparateurs fictifs
    demo_preps = ['Préparateur A', 'Préparateur B', 'Préparateur C', 'Élève', 'Professeur']
    for nom in demo_preps:
        c.execute('INSERT OR IGNORE INTO preparateurs (nom) VALUES (?)', (nom,))

    # Classes fictives
    demo_classes = [
        'Classe 1A', 'Classe 1B', 'Classe 2A', 'Classe 2B',
        'Classe 3A', 'Classe 3B', 'Terminale A', 'Terminale B',
        'BTS 1', 'BTS 2', 'Licence Pro', 'Extérieur',
    ]
    for cl in demo_classes:
        c.execute('INSERT OR IGNORE INTO classes (nom) VALUES (?)', (cl,))

    # Référents fictifs
    demo_refs = [
        ('M. Martin','Professeur'),('Mme Dubois','Professeur'),
        ('M. Laurent','Professeur'),('Mme Moreau','Professeur'),
        ('M. Garcia','Agent technique'),('Mme Petit','Agent technique'),
        ('M. Bernard','Agent technique'),
        ('Association locale','Demande extérieure'),
        ('Entreprise ABC','Demande extérieure'),
        ('Club Robotique','Demande extérieure'),
        ('Secrétariat','Administration'),
        ('Service Communication','Administration'),
    ]
    for nom, cat in demo_refs:
        c.execute('INSERT OR IGNORE INTO referents (nom,categorie) VALUES (?,?)',(nom,cat))

    preps    = [(r[0],r[1]) for r in c.execute('SELECT id,nom FROM preparateurs WHERE actif=1')]
    types    = {r[1]:(r[0],r[1]) for r in c.execute('SELECT id,nom FROM types_activite WHERE actif=1')}
    mach_bt  = {}
    for tn,(tid,_) in types.items():
        mach_bt[tid] = [(r[0],r[1]) for r in c.execute('SELECT id,nom FROM machines WHERE type_activite_id=? AND actif=1',(tid,))]

    # Matériaux par machine (via junction) + matériaux sans machine
    mats_by_machine = {}  # machine_id → [(mat_id, mat_nom, unite)]
    for r in c.execute('''SELECT mm.machine_id, m.id, m.nom, m.unite
                          FROM materiau_machine mm JOIN materiaux m ON m.id=mm.materiau_id WHERE m.actif=1'''):
        mats_by_machine.setdefault(r[0], []).append((r[1], r[2], r[3]))
    # Matériaux sans aucune machine
    generic_mats = [(r[0],r[1],r[2]) for r in c.execute(
        '''SELECT id, nom, unite FROM materiaux WHERE actif=1
           AND id NOT IN (SELECT materiau_id FROM materiau_machine)''')]

    cls   = [(r[0],r[1]) for r in c.execute('SELECT id,nom FROM classes WHERE actif=1')]
    refs  = [(r[0],r[1]) for r in c.execute('SELECT id,nom FROM referents WHERE actif=1')]
    if not preps or not types: conn.close(); return 0

    w = {'Impression 3D':40,'Découpe Laser':25,'CNC / Fraisage':10,
         'Impression Papier':15,'Thermoformage':5,'Bricolage':3,'Broderie':2}
    tnames = list(types.keys()); wts = [w.get(t,1) for t in tnames]
    now = datetime.now(); n = 0

    for _ in range(150):
        day_offset = random.randint(0, 180)
        base_date = now - timedelta(days=day_offset)
        hour = random.choices(range(24), weights=[0]*7 + [3,8,10,10,10,8,10,10,10,8,3] + [0]*6, k=1)[0]
        minute = random.randint(0, 59)
        dt = base_date.replace(hour=hour, minute=minute, second=0).strftime('%Y-%m-%d %H:%M')

        prep_id, prep_nom = random.choice(preps)
        tn   = random.choices(tnames, weights=wts, k=1)[0]
        tid, tnom = types[tn]

        mid, mnom = (None, '')
        if mach_bt.get(tid):
            mid, mnom = random.choice(mach_bt[tid])

        # Matériaux disponibles = ceux liés à la machine sélectionnée + génériques
        available_mats = list(generic_mats)
        if mid and mid in mats_by_machine:
            available_mats += mats_by_machine[mid]
        matid, matnom, matu = (None, '', '')
        if available_mats:
            matid, matnom, matu = random.choice(available_mats)

        cid, cnom = (None, '')
        if cls and random.random() > 0.15:
            cid, cnom = random.choice(cls)
        rid, rnom = (None, '')
        if refs and random.random() > 0.25:
            rid, rnom = random.choice(refs)

        pg=lg=wg=sf=None; nf=nfp=None; fp=tf=ep=None; com=''

        if tn=='Impression 3D':
            pg=round(random.uniform(5,500),1)
            com=random.choice(['Prototype boîtier','Pièce rechange','Projet élève','Support montage','Engrenage','Capot','Test résistance','Maquette',''])
        elif tn in ('Découpe Laser','CNC / Fraisage'):
            lg=round(random.uniform(50,800),1); wg=round(random.uniform(50,600),1)
            sf=round((lg*wg)/1e6,4)
            ep=random.choice(['3mm','5mm','6mm','8mm','10mm','12mm'])
            com=random.choice(['Plaque signalétique','Pièce découpée','Gravure logo','Puzzle éducatif','Support expo','',''])
        elif tn=='Impression Papier':
            nf=random.randint(1,50); fp=random.choice(['A0','A1','A2','A3','A4','A4'])
            com=random.choice(['Plans fabrication','Affiche','Documents cours','Poster','Fiches techniques',''])
        elif tn=='Thermoformage':
            nfp=random.randint(1,5); tf=random.choice(['opaque','transparente'])
            com=random.choice(['Moule prototype','Blister','Protection pièce',''])
        else:
            com=random.choice(['Projet perso','Atelier découverte','Maintenance','Démo',''])

        c.execute('''INSERT INTO consommations (date_saisie,preparateur_id,type_activite_id,machine_id,
            classe_id,referent_id,materiau_id,quantite,unite,
            poids_grammes,longueur_mm,largeur_mm,surface_m2,epaisseur,
            nb_feuilles,format_papier,nb_feuilles_plastique,type_feuille,commentaire,
            nom_preparateur,nom_type_activite,nom_machine,nom_classe,nom_referent,nom_materiau)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (dt,prep_id,tid,mid,cid,rid,matid,0,matu,pg,lg,wg,sf,ep,nf,fp,nfp,tf,com,
             prep_nom,tnom,mnom,cnom,rnom,matnom))
        n+=1

    conn.commit(); conn.close()
    return n


if __name__ == '__main__':
    init_db()
