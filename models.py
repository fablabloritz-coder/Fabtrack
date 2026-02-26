"""
FabTrack v2 — Modèles de base de données SQLite
Schéma enrichi : fiches techniques machines, catégories référents,
types d'activité paramétrables, données de démonstration, réinitialisation.
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
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS types_activite (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        icone TEXT DEFAULT '',
        couleur TEXT DEFAULT '#2563eb',
        badge_class TEXT DEFAULT '',
        unite_defaut TEXT DEFAULT '',
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
        description TEXT DEFAULT '',
        actif INTEGER DEFAULT 1,
        FOREIGN KEY (type_activite_id) REFERENCES types_activite(id)
    );

    CREATE TABLE IF NOT EXISTS materiaux (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL,
        type_activite_id INTEGER NOT NULL,
        unite TEXT DEFAULT '',
        actif INTEGER DEFAULT 1,
        FOREIGN KEY (type_activite_id) REFERENCES types_activite(id)
    );

    CREATE TABLE IF NOT EXISTS classes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS referents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        categorie TEXT DEFAULT 'Professeur',
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS salles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        actif INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS consommations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date_saisie TEXT NOT NULL,
        preparateur_id INTEGER NOT NULL,
        type_activite_id INTEGER NOT NULL,
        machine_id INTEGER,
        classe_id INTEGER,
        referent_id INTEGER,
        salle_id INTEGER,
        materiau_id INTEGER,
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
        created_at TEXT DEFAULT (datetime('now','localtime')),
        updated_at TEXT DEFAULT (datetime('now','localtime')),
        FOREIGN KEY (preparateur_id) REFERENCES preparateurs(id),
        FOREIGN KEY (type_activite_id) REFERENCES types_activite(id),
        FOREIGN KEY (machine_id) REFERENCES machines(id),
        FOREIGN KEY (classe_id) REFERENCES classes(id),
        FOREIGN KEY (referent_id) REFERENCES referents(id),
        FOREIGN KEY (salle_id) REFERENCES salles(id),
        FOREIGN KEY (materiau_id) REFERENCES materiaux(id)
    );

    CREATE INDEX IF NOT EXISTS idx_conso_date ON consommations(date_saisie);
    CREATE INDEX IF NOT EXISTS idx_conso_type ON consommations(type_activite_id);
    CREATE INDEX IF NOT EXISTS idx_conso_prep ON consommations(preparateur_id);
    CREATE INDEX IF NOT EXISTS idx_conso_mach ON consommations(machine_id);
    ''')

    _migrate_db(c)
    _insert_reference_data(c)
    conn.commit()
    conn.close()
    print("[FabTrack] Base de données initialisée.")


def _migrate_db(c):
    """Ajoute les colonnes manquantes pour les bases existantes."""
    mcols = [r[1] for r in c.execute("PRAGMA table_info(machines)").fetchall()]
    for col, spec in {'quantite':'INTEGER DEFAULT 1','marque':"TEXT DEFAULT ''",'zone_travail':"TEXT DEFAULT ''",'puissance':"TEXT DEFAULT ''",'photo_url':"TEXT DEFAULT ''",'description':"TEXT DEFAULT ''"}.items():
        if col not in mcols:
            c.execute(f"ALTER TABLE machines ADD COLUMN {col} {spec}")

    rcols = [r[1] for r in c.execute("PRAGMA table_info(referents)").fetchall()]
    if 'categorie' not in rcols:
        c.execute("ALTER TABLE referents ADD COLUMN categorie TEXT DEFAULT 'Professeur'")

    tcols = [r[1] for r in c.execute("PRAGMA table_info(types_activite)").fetchall()]
    if 'unite_defaut' not in tcols:
        c.execute("ALTER TABLE types_activite ADD COLUMN unite_defaut TEXT DEFAULT ''")
    if 'actif' not in tcols:
        c.execute("ALTER TABLE types_activite ADD COLUMN actif INTEGER DEFAULT 1")


# ============================================================
# DONNÉES DE RÉFÉRENCE (parc réel Loritz)
# ============================================================

def _insert_reference_data(c):
    for p in ['Steven LEFRANCOIS','Axel BRUA','Jeremy LOUIS','Élève','Professeur']:
        c.execute('INSERT OR IGNORE INTO preparateurs (nom) VALUES (?)', (p,))

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
        for nom,qte,marque,zone,puiss,desc in mlist:
            if not c.execute('SELECT 1 FROM machines WHERE nom=? AND type_activite_id=?',(nom,tid)).fetchone():
                c.execute('INSERT INTO machines (nom,type_activite_id,quantite,marque,zone_travail,puissance,description) VALUES (?,?,?,?,?,?,?)',
                          (nom,tid,qte,marque,zone,puiss,desc))

    materiaux = {
        'Impression 3D': [('PLA','g'),('PETG','g'),('ABS','g'),('TPU','g')],
        'Découpe Laser': [('MDF 3mm','m²'),('MDF 6mm','m²'),('MDF 8mm','m²'),('MDF 10mm','m²'),('MDF 12mm','m²'),
                          ('PLEXI 3mm','m²'),('PLEXI 6mm','m²'),('PLEXI 20mm','m²')],
        'CNC / Fraisage': [('Carton 5mm','m²'),('Carton 13mm','m²'),('MDF 3mm','m²'),('MDF 6mm','m²'),
                           ('Mousse usinée','m²'),('Aluminium','m²')],
        'Impression Papier': [('Papier A0 (1189×841)','feuilles'),('Papier A1 (841×594)','feuilles'),
                              ('Papier A2 (594×420)','feuilles'),('Papier A3 (420×297)','feuilles'),
                              ('Papier A4 (297×210)','feuilles')],
        'Thermoformage': [('Feuille opaque','feuilles'),('Feuille transparente','feuilles')],
    }
    for tnom, mats in materiaux.items():
        tid = tmap.get(tnom)
        if tid:
            for nom,unite in mats:
                c.execute('INSERT OR IGNORE INTO materiaux (nom,type_activite_id,unite) VALUES (?,?,?)',(nom,tid,unite))

    classes = [
        '500','500 CNED','501','502','503','504','505','506','507','508','509','510','511','512','513','514',
        '600 CNED','601','602','603','604','605','606','607','608','609','610','611','612','613','614','641',
        '701','702','703','704','705','706','707','708','709','710','711','712','713','714','715','741','750',
        '800 DNMADE','8001MADE','801 CPI CPRP','802 CRSA','804 ELEC','805 FONDERIE','806 GA','807 MGTMN',
        '809 CIELer1','810 CIELir1','811A','812A','813A','815A','816A','817A','818A','819A','851','852','853',
        '900 DNMADE','9001MADE','901 CPI CPRP','902 CRSA','904 ELEC','905 FONDERIE','906 GA','907 MGTMN',
        '909 CIELer2','910 CIELir2','911A','912A','913A','915A','916A','917A','918A','919A','951','952','953','995',
        'CPGEPCSI','EXTERIEUR','JPO','FMS2','FMS3','Ing EEIGM','LPRO BIO','LPROCND','LPROFOND',
        'TCND GRETA','TCND GRETA 2','LP CIG',
    ]
    for cl in classes:
        c.execute('INSERT OR IGNORE INTO classes (nom) VALUES (?)',(cl,))

    for s in ['Fablab','Salle CNC','Salle Laser','Salle impression','Atelier général']:
        c.execute('INSERT OR IGNORE INTO salles (nom) VALUES (?)',(s,))


# ============================================================
# RÉINITIALISATION
# ============================================================

def reset_db():
    conn = get_db()
    conn.cursor().executescript('''
        DROP TABLE IF EXISTS consommations; DROP TABLE IF EXISTS machines;
        DROP TABLE IF EXISTS materiaux; DROP TABLE IF EXISTS classes;
        DROP TABLE IF EXISTS referents; DROP TABLE IF EXISTS salles;
        DROP TABLE IF EXISTS preparateurs; DROP TABLE IF EXISTS types_activite;
    ''')
    conn.commit(); conn.close()
    init_db()
    print("[FabTrack] Base RÉINITIALISÉE.")


# ============================================================
# DONNÉES DE DÉMONSTRATION
# ============================================================

def generate_demo_data():
    """Génère ~150 consommations fictives + référents diversifiés."""
    conn = get_db(); c = conn.cursor()

    demo_refs = [
        ('M. Martin','Professeur'),('Mme Dubois','Professeur'),
        ('M. Laurent','Professeur'),('Mme Moreau','Professeur'),
        ('M. Garcia','Agent technique'),('Mme Petit','Agent technique'),
        ('M. Bernard','Agent technique'),
        ('Association MakerSpace','Demande extérieure'),
        ('Entreprise ACME','Demande extérieure'),
        ('Mairie de Nancy','Demande extérieure'),
        ('Club Robotique','Demande extérieure'),
        ('Secrétariat Direction','Administration'),
        ('Service Communication','Administration'),
    ]
    for nom, cat in demo_refs:
        c.execute('INSERT OR IGNORE INTO referents (nom,categorie) VALUES (?,?)',(nom,cat))

    preps    = [r[0] for r in c.execute('SELECT id FROM preparateurs WHERE actif=1')]
    types    = {r[1]:r[0] for r in c.execute('SELECT id,nom FROM types_activite WHERE actif=1')}
    mach_bt  = {}
    mats_bt  = {}
    for tn,tid in types.items():
        mach_bt[tid] = [r[0] for r in c.execute('SELECT id FROM machines WHERE type_activite_id=? AND actif=1',(tid,))]
        mats_bt[tid] = [(r[0],r[1]) for r in c.execute('SELECT id,unite FROM materiaux WHERE type_activite_id=? AND actif=1',(tid,))]
    cls   = [r[0] for r in c.execute('SELECT id FROM classes WHERE actif=1')]
    refs  = [r[0] for r in c.execute('SELECT id FROM referents WHERE actif=1')]
    salles= [r[0] for r in c.execute('SELECT id FROM salles WHERE actif=1')]

    if not preps or not types: conn.close(); return 0

    w = {'Impression 3D':40,'Découpe Laser':25,'CNC / Fraisage':10,
         'Impression Papier':15,'Thermoformage':5,'Bricolage':3,'Broderie':2}
    tnames = list(types.keys()); wts = [w.get(t,1) for t in tnames]
    now = datetime.now(); n = 0

    for _ in range(150):
        dt   = (now - timedelta(days=random.randint(0,180))).strftime('%Y-%m-%d')
        prep = random.choice(preps)
        tn   = random.choices(tnames, weights=wts, k=1)[0]
        tid  = types[tn]
        mid  = random.choice(mach_bt[tid]) if mach_bt.get(tid) else None
        matid,matu = (None,'')
        if mats_bt.get(tid):
            matid,matu = random.choice(mats_bt[tid])
        cid = random.choice(cls) if cls and random.random()>0.15 else None
        rid = random.choice(refs) if refs and random.random()>0.25 else None
        sid = random.choice(salles) if salles and random.random()>0.35 else None

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
            classe_id,referent_id,salle_id,materiau_id,quantite,unite,
            poids_grammes,longueur_mm,largeur_mm,surface_m2,epaisseur,
            nb_feuilles,format_papier,nb_feuilles_plastique,type_feuille,commentaire)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (dt,prep,tid,mid,cid,rid,sid,matid,0,matu,pg,lg,wg,sf,ep,nf,fp,nfp,tf,com))
        n+=1

    conn.commit(); conn.close()
    return n


if __name__ == '__main__':
    init_db()
