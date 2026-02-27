"""
FabTrack v2 — Application Flask principale
Suivi de consommation pour Fablab (Loritz)
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, send_file
from models import get_db, init_db, reset_db, generate_demo_data
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import csv, io, json, os, shutil, glob

app = Flask(__name__)
app.secret_key = os.environ.get('FABTRACK_SECRET', 'fabtrack-secret-2025')

# Upload config
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Backup config
BACKUP_FOLDER = os.path.join(BASE_DIR, 'backups')
BACKUP_CONFIG_PATH = os.path.join(BASE_DIR, 'backup_config.json')
os.makedirs(BACKUP_FOLDER, exist_ok=True)

def _load_backup_config():
    """Charge la configuration de sauvegarde depuis le fichier JSON."""
    defaults = {'frequency': 'off', 'last_backup': '', 'max_backups': 30, 'backup_path': ''}
    if os.path.exists(BACKUP_CONFIG_PATH):
        try:
            with open(BACKUP_CONFIG_PATH, 'r', encoding='utf-8') as f:
                cfg = json.load(f)
            return {**defaults, **cfg}
        except (json.JSONDecodeError, IOError):
            pass
    return defaults

def _save_backup_config(cfg):
    """Sauvegarde la configuration de sauvegarde."""
    with open(BACKUP_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)

def _get_backup_folder():
    """Retourne le dossier de sauvegarde : chemin personnalisé ou dossier par défaut."""
    cfg = _load_backup_config()
    custom = cfg.get('backup_path', '').strip()
    if custom and os.path.isdir(custom):
        return custom
    return BACKUP_FOLDER

def _create_backup(label='auto'):
    """Crée une copie .fabtrack de la base de données. Retourne le nom du fichier créé."""
    from models import DB_PATH
    if not os.path.exists(DB_PATH):
        return None
    folder = _get_backup_folder()
    os.makedirs(folder, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'fabtrack_{label}_{ts}.fabtrack'
    dest = os.path.join(folder, filename)
    shutil.copy2(DB_PATH, dest)
    # Nettoyage des vieilles sauvegardes
    cfg = _load_backup_config()
    max_b = cfg.get('max_backups', 30)
    backups = sorted(glob.glob(os.path.join(folder, '*.fabtrack')), key=os.path.getmtime)
    while len(backups) > max_b:
        os.remove(backups.pop(0))
    return filename

def _check_auto_backup():
    """Vérifie si une sauvegarde automatique est nécessaire selon la fréquence configurée."""
    cfg = _load_backup_config()
    freq = cfg.get('frequency', 'off')
    if freq == 'off':
        return
    last = cfg.get('last_backup', '')
    now = datetime.now()
    needs_backup = False
    if not last:
        needs_backup = True
    else:
        try:
            last_dt = datetime.strptime(last, '%Y-%m-%d %H:%M:%S')
            if freq == 'daily' and (now - last_dt).total_seconds() >= 86400:
                needs_backup = True
            elif freq == 'weekly' and (now - last_dt).total_seconds() >= 604800:
                needs_backup = True
        except ValueError:
            needs_backup = True
    if needs_backup:
        fname = _create_backup(f'auto_{freq}')
        if fname:
            cfg['last_backup'] = now.strftime('%Y-%m-%d %H:%M:%S')
            _save_backup_config(cfg)
            print(f'[FabTrack] Sauvegarde automatique ({freq}): {fname}')

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# INIT
# ============================================================

_db_initialized = False

@app.before_request
def ensure_db():
    global _db_initialized
    if _db_initialized:
        return
    from models import DB_PATH
    if not os.path.exists(DB_PATH):
        init_db()
    _check_auto_backup()
    _db_initialized = True


# ============================================================
# HELPERS
# ============================================================

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]

def _resolve_nom(db, table, id_val):
    """Résout un nom à partir d'un ID dans une table de référence."""
    ALLOWED = {'preparateurs','types_activite','machines','classes','referents','materiaux'}
    if not id_val or table not in ALLOWED: return ''
    row = db.execute(f'SELECT nom FROM {table} WHERE id=?', (id_val,)).fetchone()
    return row['nom'] if row else ''


# ============================================================
# PAGES
# ============================================================

@app.route('/')
def index():
    return render_template('index.html', page='saisie')

@app.route('/historique')
def historique():
    return render_template('historique.html', page='historique')

@app.route('/statistiques')
def statistiques():
    return render_template('statistiques.html', page='statistiques')

@app.route('/parametres')
def parametres():
    return render_template('parametres.html', page='parametres')

@app.route('/export')
def export_page():
    return render_template('export.html', page='export')

@app.route('/calculateur')
def calculateur():
    return render_template('calculateur.html', page='calculateur')

@app.route('/etat-machines')
def etat_machines():
    return render_template('etat_machines.html', page='etat_machines')


# ============================================================
# API — DONNÉES DE RÉFÉRENCE
# ============================================================

@app.route('/api/reference')
def api_reference():
    db = get_db()
    try:
        return jsonify({
            'preparateurs':  rows_to_list(db.execute('SELECT * FROM preparateurs WHERE actif=1 ORDER BY nom').fetchall()),
            'types_activite':rows_to_list(db.execute('SELECT * FROM types_activite WHERE actif=1 ORDER BY id').fetchall()),
            'machines':      rows_to_list(db.execute('SELECT * FROM machines WHERE actif=1 ORDER BY type_activite_id, nom').fetchall()),
            'materiaux':     rows_to_list(db.execute('SELECT * FROM materiaux WHERE actif=1 ORDER BY nom').fetchall()),
            'materiau_machine': rows_to_list(db.execute('SELECT * FROM materiau_machine').fetchall()),
            'classes':       rows_to_list(db.execute('SELECT * FROM classes WHERE actif=1 ORDER BY nom').fetchall()),
            'referents':     rows_to_list(db.execute('SELECT * FROM referents WHERE actif=1 ORDER BY categorie, nom').fetchall()),
        })
    finally:
        db.close()


# ============================================================
# API — CONSOMMATIONS CRUD
# ============================================================

@app.route('/api/consommations', methods=['GET'])
def api_get_consommations():
    db = get_db()
    try:
        date_debut = request.args.get('date_debut','')
        date_fin   = request.args.get('date_fin','')
        type_activite_id = request.args.get('type_activite_id','')
        preparateur_id   = request.args.get('preparateur_id','')
        classe_id  = request.args.get('classe_id','')
        referent_id= request.args.get('referent_id','')
        page     = max(1, int(request.args.get('page',1) or 1))
        per_page = min(max(1, int(request.args.get('per_page',50) or 50)), 10000)

        query = '''
            SELECT c.*,
                   COALESCE(p.nom, c.nom_preparateur) as preparateur_nom,
                   COALESCE(t.nom, c.nom_type_activite) as type_activite_nom,
                   t.icone as type_icone, t.badge_class,
                   COALESCE(m.nom, c.nom_machine) as machine_nom,
                   COALESCE(cl.nom, c.nom_classe) as classe_nom,
                   COALESCE(r.nom, c.nom_referent) as referent_nom, r.categorie as referent_categorie,
                   COALESCE(mat.nom, c.nom_materiau) as materiau_nom, mat.unite as materiau_unite
            FROM consommations c
            LEFT JOIN preparateurs p ON c.preparateur_id=p.id
            LEFT JOIN types_activite t ON c.type_activite_id=t.id
            LEFT JOIN machines m ON c.machine_id=m.id
            LEFT JOIN classes cl ON c.classe_id=cl.id
            LEFT JOIN referents r ON c.referent_id=r.id
            LEFT JOIN materiaux mat ON c.materiau_id=mat.id
            WHERE 1=1
        '''
        params = []
        count_q = 'SELECT COUNT(*) as total FROM consommations c WHERE 1=1'
        cp = []

        for col, val, cast in [
            ('c.date_saisie >=', date_debut, str),
            ('c.date_saisie <=', date_fin + ' 23:59:59' if date_fin and len(date_fin) == 10 else date_fin, str),
            ('c.type_activite_id =', type_activite_id, int),
            ('c.preparateur_id =', preparateur_id, int),
            ('c.classe_id =', classe_id, int),
            ('c.referent_id =', referent_id, int),
        ]:
            if val:
                query += f' AND {col} ?'; params.append(cast(val))
                count_q += f' AND {col} ?'; cp.append(cast(val))

        total = db.execute(count_q, cp).fetchone()['total']
        query += ' ORDER BY c.date_saisie DESC, c.created_at DESC LIMIT ? OFFSET ?'
        params.extend([per_page, (page-1)*per_page])

        return jsonify({
            'data': rows_to_list(db.execute(query, params).fetchall()),
            'total': total, 'page': page, 'per_page': per_page,
            'pages': max(1, (total + per_page - 1) // per_page),
        })
    finally:
        db.close()


@app.route('/api/consommations', methods=['POST'])
def api_create_consommation():
    data = request.get_json(); db = get_db()
    try:
        surface = None
        if data.get('longueur_mm') and data.get('largeur_mm'):
            try: surface = (float(data['longueur_mm'])*float(data['largeur_mm']))/1e6
            except: pass

        # Résoudre les noms pour stockage dénormalisé
        nom_prep = _resolve_nom(db, 'preparateurs', data.get('preparateur_id'))
        nom_type = _resolve_nom(db, 'types_activite', data.get('type_activite_id'))
        nom_mach = _resolve_nom(db, 'machines', data.get('machine_id'))
        nom_cls  = _resolve_nom(db, 'classes', data.get('classe_id'))
        nom_ref  = _resolve_nom(db, 'referents', data.get('referent_id'))
        nom_mat  = _resolve_nom(db, 'materiaux', data.get('materiau_id'))

        cur = db.execute('''
            INSERT INTO consommations (
                date_saisie, preparateur_id, type_activite_id, machine_id,
                classe_id, referent_id, materiau_id,
                nom_preparateur, nom_type_activite, nom_machine, nom_classe, nom_referent, nom_materiau,
                quantite, unite,
                poids_grammes, longueur_mm, largeur_mm, surface_m2, epaisseur,
                nb_feuilles, format_papier,
                nb_feuilles_plastique, type_feuille, commentaire,
                impression_couleur, projet_nom
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data.get('date_saisie', datetime.now().strftime('%Y-%m-%d %H:%M')),
            data.get('preparateur_id'), data.get('type_activite_id'),
            data.get('machine_id') or None, data.get('classe_id') or None,
            data.get('referent_id') or None,
            data.get('materiau_id') or None,
            nom_prep, nom_type, nom_mach, nom_cls, nom_ref, nom_mat,
            data.get('quantite') or 0, data.get('unite',''),
            data.get('poids_grammes') or None,
            data.get('longueur_mm') or None, data.get('largeur_mm') or None,
            surface or data.get('surface_m2') or None,
            data.get('epaisseur') or None,
            data.get('nb_feuilles') or None, data.get('format_papier') or None,
            data.get('nb_feuilles_plastique') or None,
            data.get('type_feuille') or None, data.get('commentaire',''),
            data.get('impression_couleur',''),
            data.get('projet_nom',''),
        ))
        db.commit()
        return jsonify({'success':True,'id':cur.lastrowid}), 201
    except Exception as e:
        db.rollback(); return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()


@app.route('/api/consommations/batch', methods=['POST'])
def api_create_consommation_batch():
    """Crée plusieurs consommations en une seule requête (multi-action saisie)."""
    data = request.get_json()
    actions = data.get('actions', [])
    if not actions:
        return jsonify({'success': False, 'error': 'Aucune action fournie'}), 400

    common = {
        'date_saisie': data.get('date_saisie', datetime.now().strftime('%Y-%m-%d %H:%M')),
        'preparateur_id': data.get('preparateur_id'),
        'classe_id': data.get('classe_id'),
        'referent_id': data.get('referent_id'),
        'projet_nom': data.get('projet_nom', ''),
    }

    db = get_db()
    ids = []
    try:
        # Résoudre les noms communs une seule fois
        nom_prep = _resolve_nom(db, 'preparateurs', common['preparateur_id'])
        nom_cls  = _resolve_nom(db, 'classes', common['classe_id'])
        nom_ref  = _resolve_nom(db, 'referents', common['referent_id'])

        for action in actions:
            surface = None
            if action.get('longueur_mm') and action.get('largeur_mm'):
                try: surface = (float(action['longueur_mm']) * float(action['largeur_mm'])) / 1e6
                except (ValueError, TypeError): pass

            nom_type = _resolve_nom(db, 'types_activite', action.get('type_activite_id'))
            nom_mach = _resolve_nom(db, 'machines', action.get('machine_id'))
            nom_mat  = _resolve_nom(db, 'materiaux', action.get('materiau_id'))

            cur = db.execute('''
                INSERT INTO consommations (
                    date_saisie, preparateur_id, type_activite_id, machine_id,
                    classe_id, referent_id, materiau_id,
                    nom_preparateur, nom_type_activite, nom_machine, nom_classe, nom_referent, nom_materiau,
                    quantite, unite,
                    poids_grammes, longueur_mm, largeur_mm, surface_m2, epaisseur,
                    nb_feuilles, format_papier,
                    nb_feuilles_plastique, type_feuille, commentaire,
                    impression_couleur, projet_nom
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ''', (
                common['date_saisie'], common['preparateur_id'],
                action.get('type_activite_id'), action.get('machine_id') or None,
                common.get('classe_id') or None, common.get('referent_id') or None,
                action.get('materiau_id') or None,
                nom_prep, nom_type, nom_mach, nom_cls, nom_ref, nom_mat,
                action.get('quantite') or 0, action.get('unite', ''),
                action.get('poids_grammes') or None,
                action.get('longueur_mm') or None, action.get('largeur_mm') or None,
                surface or action.get('surface_m2') or None,
                action.get('epaisseur') or None,
                action.get('nb_feuilles') or None, action.get('format_papier') or None,
                action.get('nb_feuilles_plastique') or None,
                action.get('type_feuille') or None, action.get('commentaire', ''),
                action.get('impression_couleur', ''), common['projet_nom'],
            ))
            ids.append(cur.lastrowid)

        db.commit()
        return jsonify({'success': True, 'ids': ids, 'count': len(ids)}), 201
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/consommations/<int:id>', methods=['DELETE'])
def api_delete_consommation(id):
    db = get_db()
    try:
        db.execute('DELETE FROM consommations WHERE id=?',(id,)); db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()


@app.route('/api/consommations/<int:id>', methods=['PUT'])
def api_update_consommation(id):
    data = request.get_json(); db = get_db()
    try:
        surface = None
        if data.get('longueur_mm') and data.get('largeur_mm'):
            try: surface = (float(data['longueur_mm'])*float(data['largeur_mm']))/1e6
            except: pass

        # Résoudre les noms pour stockage dénormalisé
        nom_prep = _resolve_nom(db, 'preparateurs', data.get('preparateur_id'))
        nom_type = _resolve_nom(db, 'types_activite', data.get('type_activite_id'))
        nom_mach = _resolve_nom(db, 'machines', data.get('machine_id'))
        nom_cls  = _resolve_nom(db, 'classes', data.get('classe_id'))
        nom_ref  = _resolve_nom(db, 'referents', data.get('referent_id'))
        nom_mat  = _resolve_nom(db, 'materiaux', data.get('materiau_id'))

        db.execute('''
            UPDATE consommations SET
                date_saisie=?, preparateur_id=?, type_activite_id=?, machine_id=?,
                classe_id=?, referent_id=?, materiau_id=?,
                nom_preparateur=?, nom_type_activite=?, nom_machine=?, nom_classe=?, nom_referent=?, nom_materiau=?,
                quantite=?, unite=?,
                poids_grammes=?, longueur_mm=?, largeur_mm=?, surface_m2=?, epaisseur=?,
                nb_feuilles=?, format_papier=?,
                nb_feuilles_plastique=?, type_feuille=?, commentaire=?,
                impression_couleur=?,
                projet_nom=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
        ''', (
            data.get('date_saisie'), data.get('preparateur_id'),
            data.get('type_activite_id'), data.get('machine_id') or None,
            data.get('classe_id') or None, data.get('referent_id') or None,
            data.get('materiau_id') or None,
            nom_prep, nom_type, nom_mach, nom_cls, nom_ref, nom_mat,
            data.get('quantite') or 0, data.get('unite',''),
            data.get('poids_grammes') or None,
            data.get('longueur_mm') or None, data.get('largeur_mm') or None,
            surface or data.get('surface_m2') or None,
            data.get('epaisseur') or None,
            data.get('nb_feuilles') or None, data.get('format_papier') or None,
            data.get('nb_feuilles_plastique') or None,
            data.get('type_feuille') or None, data.get('commentaire',''),
            data.get('impression_couleur',''),
            data.get('projet_nom',''), id,
        ))
        db.commit(); return jsonify({'success':True})
    except Exception as e:
        db.rollback(); return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()


# ============================================================
# API — STATISTIQUES
# ============================================================

@app.route('/api/stats/summary')
def api_stats_summary():
    db = get_db()
    try:
        dd = request.args.get('date_debut','')
        df = request.args.get('date_fin','')
        w = '1=1'; p = []
        if dd: w+=' AND c.date_saisie >= ?'; p.append(dd)
        if df: w+=' AND c.date_saisie <= ?'; p.append(df + ' 23:59:59' if df and len(df) == 10 else df)

        total = db.execute(f'SELECT COUNT(*) as n FROM consommations c WHERE {w}', p).fetchone()['n']

        by_type = rows_to_list(db.execute(f'''
            SELECT t.nom,t.icone,t.couleur,t.badge_class,COUNT(*) as count
            FROM consommations c JOIN types_activite t ON c.type_activite_id=t.id
            WHERE {w} GROUP BY t.id ORDER BY count DESC''', p).fetchall())

        by_prep = rows_to_list(db.execute(f'''
            SELECT p.nom,COUNT(*) as count FROM consommations c
            JOIN preparateurs p ON c.preparateur_id=p.id
            WHERE {w} GROUP BY p.id ORDER BY count DESC''', p).fetchall())

        total_3d = db.execute(f'''
            SELECT COALESCE(SUM(c.poids_grammes),0) as t FROM consommations c
            JOIN types_activite t ON c.type_activite_id=t.id
            WHERE t.nom='Impression 3D' AND {w}''', p).fetchone()['t']

        # Surface découpe = Laser + CNC combinés
        total_decoupe = db.execute(f'''
            SELECT COALESCE(SUM(c.surface_m2),0) as t FROM consommations c
            JOIN types_activite t ON c.type_activite_id=t.id
            WHERE t.nom IN ('Découpe Laser','CNC / Fraisage') AND {w}''', p).fetchone()['t']

        total_papier = db.execute(f'''
            SELECT COALESCE(SUM(c.nb_feuilles),0) as t FROM consommations c
            JOIN types_activite t ON c.type_activite_id=t.id
            WHERE t.nom='Impression Papier' AND {w}''', p).fetchone()['t']

        papier_detail = db.execute(f'''
            SELECT
                COALESCE(SUM(CASE WHEN COALESCE(mat.nom, c.nom_materiau) LIKE '%Couleur%' THEN c.nb_feuilles ELSE 0 END),0) as couleur,
                COALESCE(SUM(CASE WHEN COALESCE(mat.nom, c.nom_materiau) LIKE '%N&B%' THEN c.nb_feuilles ELSE 0 END),0) as nb
            FROM consommations c
            JOIN types_activite t ON c.type_activite_id=t.id
            LEFT JOIN materiaux mat ON c.materiau_id=mat.id
            WHERE t.nom='Impression Papier' AND {w}''', p).fetchone()

        return jsonify({
            'total_interventions': total,
            'by_type': by_type, 'by_preparateur': by_prep,
            'total_3d_grammes': round(total_3d, 1),
            'total_decoupe_m2': round(total_decoupe, 3),
            'total_papier_feuilles': int(total_papier),
            'total_papier_couleur': int(papier_detail['couleur']),
            'total_papier_nb': int(papier_detail['nb']),
        })
    finally:
        db.close()


@app.route('/api/stats/activity')
def api_stats_activity():
    """Statistiques d'activité journalière : répartition par heure, par jour de semaine, filtrable."""
    db = get_db()
    try:
        dd = request.args.get('date_debut', '')
        df = request.args.get('date_fin', '')
        prep_id = request.args.get('preparateur_id', '')
        machine_id = request.args.get('machine_id', '')
        w = '1=1'; p = []
        if dd: w += ' AND c.date_saisie >= ?'; p.append(dd)
        if df: w += ' AND c.date_saisie <= ?'; p.append(df + ' 23:59:59' if df and len(df) == 10 else df)
        if prep_id: w += ' AND c.preparateur_id = ?'; p.append(int(prep_id))
        if machine_id: w += ' AND c.machine_id = ?'; p.append(int(machine_id))

        # By hour (0-23)
        by_hour = rows_to_list(db.execute(f'''
            SELECT CAST(strftime('%H', c.date_saisie) AS INTEGER) as hour, COUNT(*) as count
            FROM consommations c WHERE {w}
            GROUP BY hour ORDER BY hour
        ''', p).fetchall())

        # By day of week (0=Sunday..6=Saturday in strftime('%w'))
        by_dow = rows_to_list(db.execute(f'''
            SELECT CAST(strftime('%w', c.date_saisie) AS INTEGER) as dow, COUNT(*) as count
            FROM consommations c WHERE {w}
            GROUP BY dow ORDER BY dow
        ''', p).fetchall())

        # By hour + preparateur (heatmap data)
        by_hour_prep = rows_to_list(db.execute(f'''
            SELECT CAST(strftime('%H', c.date_saisie) AS INTEGER) as hour,
                   pr.nom as preparateur, COUNT(*) as count
            FROM consommations c
            JOIN preparateurs pr ON c.preparateur_id=pr.id
            WHERE {w}
            GROUP BY hour, pr.id ORDER BY hour
        ''', p).fetchall())

        return jsonify({
            'by_hour': by_hour,
            'by_day_of_week': by_dow,
            'by_hour_prep': by_hour_prep,
        })
    finally:
        db.close()


@app.route('/api/stats/timeline')
def api_stats_timeline():
    db = get_db()
    try:
        dd = request.args.get('date_debut','')
        df = request.args.get('date_fin','')
        gb = request.args.get('group_by','month')
        w = '1=1'; p = []
        if dd: w+=' AND c.date_saisie >= ?'; p.append(dd)
        if df: w+=' AND c.date_saisie <= ?'; p.append(df + ' 23:59:59' if df and len(df) == 10 else df)

        dex = {"day":"strftime('%Y-%m-%d',c.date_saisie)","week":"strftime('%Y-W%W',c.date_saisie)","month":"strftime('%Y-%m',c.date_saisie)"}.get(gb,"strftime('%Y-%m',c.date_saisie)")

        timeline = rows_to_list(db.execute(f'''
            SELECT {dex} as period,t.nom as type_nom,t.couleur,COUNT(*) as count
            FROM consommations c JOIN types_activite t ON c.type_activite_id=t.id
            WHERE {w} GROUP BY period,t.id ORDER BY period''', p).fetchall())

        timeline_3d = rows_to_list(db.execute(f'''
            SELECT {dex} as period, mat.nom as materiau,
                   COALESCE(SUM(c.poids_grammes),0) as total_g
            FROM consommations c JOIN types_activite t ON c.type_activite_id=t.id
            LEFT JOIN materiaux mat ON c.materiau_id=mat.id
            WHERE t.nom='Impression 3D' AND {w}
            GROUP BY period,mat.nom ORDER BY period''', p).fetchall())

        # Surface découpe = Laser + CNC
        timeline_decoupe = rows_to_list(db.execute(f'''
            SELECT {dex} as period, mat.nom as materiau,
                   COALESCE(SUM(c.surface_m2),0) as total_m2
            FROM consommations c JOIN types_activite t ON c.type_activite_id=t.id
            LEFT JOIN materiaux mat ON c.materiau_id=mat.id
            WHERE t.nom IN ('Découpe Laser','CNC / Fraisage') AND {w}
            GROUP BY period,mat.nom ORDER BY period''', p).fetchall())

        # Papier par couleur / N&B
        timeline_papier = rows_to_list(db.execute(f'''
            SELECT {dex} as period,
                   CASE
                       WHEN COALESCE(mat.nom, c.nom_materiau) LIKE '%Couleur%' THEN 'Couleur'
                       WHEN COALESCE(mat.nom, c.nom_materiau) LIKE '%N&B%' THEN 'N&B'
                       ELSE 'Autre'
                   END as type_impression,
                   COALESCE(SUM(c.nb_feuilles),0) as total_feuilles
            FROM consommations c
            JOIN types_activite t ON c.type_activite_id=t.id
            LEFT JOIN materiaux mat ON c.materiau_id=mat.id
            WHERE t.nom='Impression Papier' AND {w}
            GROUP BY period, type_impression ORDER BY period''', p).fetchall())

        top_machines = rows_to_list(db.execute(f'''
            SELECT m.nom,t.nom as type_nom,t.couleur,COUNT(*) as count
            FROM consommations c JOIN machines m ON c.machine_id=m.id
            JOIN types_activite t ON c.type_activite_id=t.id
            WHERE {w} GROUP BY m.id ORDER BY count DESC LIMIT 10''', p).fetchall())

        top_classes = rows_to_list(db.execute(f'''
            SELECT cl.nom,COUNT(*) as count FROM consommations c
            JOIN classes cl ON c.classe_id=cl.id
            WHERE {w} GROUP BY cl.id ORDER BY count DESC LIMIT 10''', p).fetchall())

        return jsonify({
            'timeline': timeline, 'timeline_3d': timeline_3d,
            'timeline_decoupe': timeline_decoupe,
            'timeline_papier': timeline_papier,
            'top_machines': top_machines, 'top_classes': top_classes,
        })
    finally:
        db.close()


# ============================================================
# API — EXPORT CSV
# ============================================================

@app.route('/api/export/csv')
def api_export_csv():
    db = get_db()
    try:
        dd = request.args.get('date_debut','')
        df = request.args.get('date_fin','')
        ta = request.args.get('type_activite_id','')
        w = '1=1'; p = []
        if dd: w+=' AND c.date_saisie >= ?'; p.append(dd)
        if df: w+=' AND c.date_saisie <= ?'; p.append(df + ' 23:59:59' if df and len(df) == 10 else df)
        if ta: w+=' AND c.type_activite_id = ?'; p.append(int(ta))

        rows = db.execute(f'''
            SELECT c.date_saisie,
                   COALESCE(p.nom, c.nom_preparateur) as preparateur,
                   COALESCE(t.nom, c.nom_type_activite) as type_activite,
                   COALESCE(m.nom, c.nom_machine) as machine,
                   COALESCE(cl.nom, c.nom_classe) as classe,
                   COALESCE(r.nom, c.nom_referent) as referent,
                   r.categorie as ref_categorie,
                   COALESCE(mat.nom, c.nom_materiau) as materiau,
                   c.poids_grammes,c.surface_m2,c.longueur_mm,c.largeur_mm,
                   c.epaisseur,c.nb_feuilles,c.format_papier,c.impression_couleur,
                   c.nb_feuilles_plastique,c.type_feuille,c.projet_nom,c.commentaire
            FROM consommations c
            LEFT JOIN preparateurs p ON c.preparateur_id=p.id
            LEFT JOIN types_activite t ON c.type_activite_id=t.id
            LEFT JOIN machines m ON c.machine_id=m.id
            LEFT JOIN classes cl ON c.classe_id=cl.id
            LEFT JOIN referents r ON c.referent_id=r.id
            LEFT JOIN materiaux mat ON c.materiau_id=mat.id
            WHERE {w} ORDER BY c.date_saisie DESC
        ''', p).fetchall()

        out = io.StringIO()
        out.write('\ufeff')  # BOM Excel
        wr = csv.writer(out, delimiter=';')
        wr.writerow(['Date','Préparateur','Type activité','Machine','Classe',
                      'Référent','Catégorie réf.','Matériau',
                      'Poids (g)','Surface (m²)','Longueur (mm)','Largeur (mm)',
                      'Épaisseur','Nb feuilles','Format papier','Impression couleur',
                      'Nb feuilles plastique','Type feuille','Projet','Commentaire'])
        for row in rows:
            wr.writerow([row[k] or '' for k in row.keys()])

        out.seek(0)
        return Response(out.getvalue(), mimetype='text/csv',
                        headers={'Content-Disposition':f'attachment; filename=fabtrack_export_{datetime.now().strftime("%Y%m%d")}.csv'})
    finally:
        db.close()


# ============================================================
# API — GABARITS CSV (téléchargement)
# ============================================================

CSV_TEMPLATES = {
    'machines':   ('nom;type_activite;quantite;marque;zone_travail;puissance;description;principes_conception\n'
                   'Exemple Machine;Impression 3D;1;Marque;300x300 mm;100W;Description;ajout\n'),
    'materiaux':  ('nom;unite;machines\n'
                   'Exemple Matériau;g;Creality CR10-S,Raise 3D Pro\n'),
    'classes':    ('nom\n501\n502\nBTS CPRP\n'),
    'referents':  ('nom;categorie\n'
                   'M. Dupont;Professeur\nMme Martin;Agent technique\nEntreprise X;Demande extérieure\n'),
    'preparateurs':('nom\nJean Martin\nMarie Curie\n'),
}

@app.route('/api/template/<entity>')
def api_download_template(entity):
    tpl = CSV_TEMPLATES.get(entity)
    if not tpl:
        return jsonify({'error':'Gabarit inconnu'}), 404
    return Response('\ufeff'+tpl, mimetype='text/csv',
                    headers={'Content-Disposition':f'attachment; filename=gabarit_{entity}.csv'})


# ============================================================
# API — IMPORT CSV
# ============================================================

@app.route('/api/import/<entity>', methods=['POST'])
def api_import_csv(entity):
    """Import en masse depuis un fichier CSV."""
    if 'file' not in request.files:
        return jsonify({'success':False,'error':'Aucun fichier'}), 400
    f = request.files['file']
    content = f.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content), delimiter=';')
    db = get_db()
    imported = 0
    errors = []

    try:
        type_map = {r[1]:r[0] for r in db.execute('SELECT id,nom FROM types_activite').fetchall()}

        for i, row in enumerate(reader, start=2):
            try:
                if entity == 'machines':
                    tid = type_map.get(row.get('type_activite','').strip())
                    if not tid:
                        errors.append(f"Ligne {i}: type activité inconnu '{row.get('type_activite','')}'")
                        continue
                    db.execute('INSERT INTO machines (nom,type_activite_id,quantite,marque,zone_travail,puissance,description,principes_conception) VALUES (?,?,?,?,?,?,?,?)',
                               (row['nom'].strip(), tid, int(row.get('quantite',1) or 1),
                                row.get('marque','').strip(), row.get('zone_travail','').strip(),
                                row.get('puissance','').strip(), row.get('description','').strip(),
                                row.get('principes_conception','').strip()))

                elif entity == 'materiaux':
                    cur_mat = db.execute('INSERT OR IGNORE INTO materiaux (nom,unite) VALUES (?,?)',
                               (row['nom'].strip(), row.get('unite','').strip()))
                    if cur_mat.lastrowid:
                        mat_id = cur_mat.lastrowid
                    else:
                        mat_id = db.execute('SELECT id FROM materiaux WHERE nom=?', (row['nom'].strip(),)).fetchone()[0]
                    # Lier aux machines si spécifiées
                    machines_str = row.get('machines', '').strip()
                    if machines_str:
                        for mnom in machines_str.split(','):
                            mnom = mnom.strip()
                            mrow = db.execute('SELECT id FROM machines WHERE nom=?', (mnom,)).fetchone()
                            if mrow:
                                db.execute('INSERT OR IGNORE INTO materiau_machine (materiau_id, machine_id) VALUES (?,?)', (mat_id, mrow[0]))

                elif entity == 'classes':
                    db.execute('INSERT OR IGNORE INTO classes (nom) VALUES (?)', (row['nom'].strip(),))

                elif entity == 'referents':
                    cat = row.get('categorie','Professeur').strip() or 'Professeur'
                    db.execute('INSERT OR IGNORE INTO referents (nom,categorie) VALUES (?,?)',
                               (row['nom'].strip(), cat))


                elif entity == 'preparateurs':
                    db.execute('INSERT OR IGNORE INTO preparateurs (nom) VALUES (?)', (row['nom'].strip(),))
                else:
                    return jsonify({'success':False,'error':'Entité inconnue'}), 400

                imported += 1
            except Exception as e:
                errors.append(f"Ligne {i}: {e}")

        db.commit()
        return jsonify({'success':True,'imported':imported,'errors':errors})
    except Exception as e:
        db.rollback()
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()


# ============================================================
# API — GESTION RÉFÉRENTIELS (CRUD)
# ============================================================

# ---- Types d'activité ----
@app.route('/api/types_activite', methods=['POST'])
def api_add_type_activite():
    data = request.get_json(); db = get_db()
    try:
        nom = data['nom'].strip()
        cur = db.execute(
            'INSERT OR IGNORE INTO types_activite (nom,icone,couleur,badge_class,unite_defaut,image_path) VALUES (?,?,?,?,?,?)',
            (nom, data.get('icone','🔧'), data.get('couleur','#6b7280'),
             data.get('badge_class',''), data.get('unite_defaut',''), data.get('image_path','')))
        db.commit()
        rid = cur.lastrowid
        if not rid:
            row = db.execute('SELECT id FROM types_activite WHERE nom=?', (nom,)).fetchone()
            rid = row['id'] if row else 0
        return jsonify({'success':True,'id':rid})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/types_activite/<int:id>', methods=['PUT'])
def api_update_type_activite(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('UPDATE types_activite SET nom=?,icone=?,couleur=?,badge_class=?,unite_defaut=?,image_path=? WHERE id=?',
                   (data['nom'].strip(), data.get('icone',''), data.get('couleur',''),
                    data.get('badge_class',''), data.get('unite_defaut',''), data.get('image_path',''), id))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/types_activite/<int:id>', methods=['DELETE'])
def api_delete_type_activite(id):
    db = get_db()
    try:
        db.execute('UPDATE types_activite SET actif=0 WHERE id=?',(id,)); db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

# ---- Machines ----
@app.route('/api/machines', methods=['POST'])
def api_add_machine():
    data = request.get_json(); db = get_db()
    try:
        cur = db.execute(
            'INSERT INTO machines (nom,type_activite_id,quantite,marque,zone_travail,puissance,description,image_path,principes_conception) VALUES (?,?,?,?,?,?,?,?,?)',
            (data['nom'].strip(), data['type_activite_id'],
             int(data.get('quantite',1) or 1),
             data.get('marque','').strip(), data.get('zone_travail','').strip(),
             data.get('puissance','').strip(), data.get('description','').strip(),
             data.get('image_path',''), data.get('principes_conception','')))
        db.commit()
        return jsonify({'success':True,'id':cur.lastrowid})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/machines/<int:id>', methods=['PUT'])
def api_update_machine(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('''UPDATE machines SET nom=?,type_activite_id=?,quantite=?,
                      marque=?,zone_travail=?,puissance=?,description=?,statut=?,image_path=?,principes_conception=? WHERE id=?''',
                   (data['nom'].strip(), data['type_activite_id'],
                    int(data.get('quantite',1) or 1),
                    data.get('marque','').strip(), data.get('zone_travail','').strip(),
                    data.get('puissance','').strip(), data.get('description','').strip(),
                    data.get('statut','disponible'), data.get('image_path',''),
                    data.get('principes_conception',''), id))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/machines/<int:id>', methods=['DELETE'])
def api_delete_machine(id):
    db = get_db()
    try:
        db.execute('UPDATE machines SET actif=0 WHERE id=?',(id,)); db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

# ---- Matériaux ----
@app.route('/api/materiaux', methods=['POST'])
def api_add_materiau():
    data = request.get_json(); db = get_db()
    try:
        cur = db.execute('INSERT INTO materiaux (nom,unite,image_path) VALUES (?,?,?)',
                         (data['nom'].strip(), data.get('unite',''), data.get('image_path','')))
        mat_id = cur.lastrowid
        # Lier aux machines sélectionnées
        for mid in data.get('machine_ids', []):
            db.execute('INSERT OR IGNORE INTO materiau_machine (materiau_id, machine_id) VALUES (?,?)', (mat_id, int(mid)))
        db.commit()
        return jsonify({'success':True,'id':mat_id})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/materiaux/<int:id>', methods=['DELETE'])
def api_delete_materiau(id):
    db = get_db()
    try:
        db.execute('UPDATE materiaux SET actif=0 WHERE id=?',(id,)); db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/materiaux/<int:id>', methods=['PUT'])
def api_update_materiau(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('UPDATE materiaux SET nom=?,unite=?,image_path=? WHERE id=?',
                   (data['nom'].strip(), data.get('unite',''),
                    data.get('image_path',''), id))
        # Mettre à jour les liens machine
        db.execute('DELETE FROM materiau_machine WHERE materiau_id=?', (id,))
        for mid in data.get('machine_ids', []):
            db.execute('INSERT OR IGNORE INTO materiau_machine (materiau_id, machine_id) VALUES (?,?)', (id, int(mid)))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

# ---- Classes ----
@app.route('/api/classes', methods=['POST'])
def api_add_classe():
    data = request.get_json(); db = get_db()
    try:
        nom = data['nom'].strip()
        cur = db.execute('INSERT OR IGNORE INTO classes (nom,image_path) VALUES (?,?)', (nom, data.get('image_path','')))
        db.commit()
        rid = cur.lastrowid
        if not rid:
            row = db.execute('SELECT id FROM classes WHERE nom=?', (nom,)).fetchone()
            rid = row['id'] if row else 0
        return jsonify({'success':True,'id':rid})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/classes/<int:id>', methods=['DELETE'])
def api_delete_classe(id):
    db = get_db()
    try:
        db.execute('UPDATE classes SET actif=0 WHERE id=?',(id,)); db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/classes/<int:id>', methods=['PUT'])
def api_update_classe(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('UPDATE classes SET nom=?,image_path=? WHERE id=?',
                   (data['nom'].strip(), data.get('image_path',''), id))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

# ---- Référents ----
@app.route('/api/referents', methods=['POST'])
def api_add_referent():
    data = request.get_json(); db = get_db()
    try:
        nom = data['nom'].strip()
        cat = data.get('categorie','Professeur').strip() or 'Professeur'
        cur = db.execute('INSERT OR IGNORE INTO referents (nom,categorie,image_path) VALUES (?,?,?)',
                         (nom, cat, data.get('image_path','')))
        db.commit()
        rid = cur.lastrowid
        if not rid:
            row = db.execute('SELECT id FROM referents WHERE nom=?', (nom,)).fetchone()
            rid = row['id'] if row else 0
        return jsonify({'success':True,'id':rid})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/referents/<int:id>', methods=['PUT'])
def api_update_referent(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('UPDATE referents SET nom=?,categorie=?,image_path=? WHERE id=?',
                   (data['nom'].strip(), data.get('categorie','Professeur'), data.get('image_path',''), id))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/referents/<int:id>', methods=['DELETE'])
def api_delete_referent(id):
    db = get_db()
    try:
        db.execute('UPDATE referents SET actif=0 WHERE id=?',(id,)); db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

# ---- Préparateurs ----
@app.route('/api/preparateurs', methods=['POST'])
def api_add_preparateur():
    data = request.get_json(); db = get_db()
    try:
        nom = data['nom'].strip()
        cur = db.execute('INSERT OR IGNORE INTO preparateurs (nom,image_path) VALUES (?,?)', (nom, data.get('image_path','')))
        db.commit()
        rid = cur.lastrowid
        if not rid:
            row = db.execute('SELECT id FROM preparateurs WHERE nom=?', (nom,)).fetchone()
            rid = row['id'] if row else 0
        return jsonify({'success':True,'id':rid})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/preparateurs/<int:id>', methods=['DELETE'])
def api_delete_preparateur(id):
    db = get_db()
    try:
        db.execute('UPDATE preparateurs SET actif=0 WHERE id=?',(id,)); db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/preparateurs/<int:id>', methods=['PUT'])
def api_update_preparateur(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('UPDATE preparateurs SET nom=?,image_path=? WHERE id=?',
                   (data['nom'].strip(), data.get('image_path',''), id))
        db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()


# ============================================================
# API — VÉRIFICATION DÉPENDANCES AVANT SUPPRESSION
# ============================================================

ENTITY_FK_MAP = {
    'machines': 'machine_id',
    'types_activite': 'type_activite_id',
    'materiaux': 'materiau_id',
    'classes': 'classe_id',
    'referents': 'referent_id',
    'preparateurs': 'preparateur_id',
}

@app.route('/api/<entity>/<int:id>/usage-count')
def api_usage_count(entity, id):
    """Compte le nombre de consommations utilisant cet élément."""
    col = ENTITY_FK_MAP.get(entity)
    if not col:
        return jsonify({'error': 'Entité inconnue'}), 400
    db = get_db()
    try:
        count = db.execute(f'SELECT COUNT(*) as n FROM consommations WHERE {col}=?', (id,)).fetchone()['n']
        return jsonify({'count': count, 'entity': entity, 'id': id})
    finally:
        db.close()

@app.route('/api/<entity>/<int:id>/replace-and-delete', methods=['POST'])
def api_replace_and_delete(entity, id):
    """Remplace toutes les références puis désactive l'élément."""
    col = ENTITY_FK_MAP.get(entity)
    if not col:
        return jsonify({'success': False, 'error': 'Entité inconnue'}), 400
    data = request.get_json()
    replacement_id = data.get('replacement_id')
    db = get_db()
    try:
        # Mettre à jour aussi la colonne nom_* dénormalisée
        nom_col_map = {
            'preparateur_id': 'nom_preparateur', 'type_activite_id': 'nom_type_activite',
            'machine_id': 'nom_machine', 'classe_id': 'nom_classe',
            'referent_id': 'nom_referent', 'materiau_id': 'nom_materiau',
        }
        nom_col = nom_col_map.get(col)
        if replacement_id:
            new_nom = _resolve_nom(db, entity, replacement_id) if nom_col else ''
            if nom_col:
                db.execute(f'UPDATE consommations SET {col}=?, {nom_col}=? WHERE {col}=?',
                           (replacement_id, new_nom, id))
            else:
                db.execute(f'UPDATE consommations SET {col}=? WHERE {col}=?', (replacement_id, id))
        else:
            db.execute(f'UPDATE consommations SET {col}=NULL WHERE {col}=?', (id,))
        db.execute(f'UPDATE {entity} SET actif=0 WHERE id=?', (id,))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ============================================================
# API — UPLOAD D'IMAGES
# ============================================================

@app.route('/api/upload-image', methods=['POST'])
def api_upload_image():
    """Upload une image et retourne le chemin relatif."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier'}), 400
    f = request.files['file']
    if f.filename == '' or not allowed_file(f.filename):
        return jsonify({'success': False, 'error': 'Fichier non autorisé (png, jpg, gif, webp, svg)'}), 400
    entity = request.form.get('entity', 'general')
    entity_id = request.form.get('entity_id', '0')
    ext = f.filename.rsplit('.', 1)[1].lower()
    filename = secure_filename(f"{entity}_{entity_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}")
    filepath = os.path.join(UPLOAD_FOLDER, filename)
    f.save(filepath)
    rel_path = f'/static/uploads/{filename}'
    return jsonify({'success': True, 'path': rel_path})


# ============================================================
# API — STATUT MACHINES
# ============================================================

@app.route('/api/machines/<int:id>/statut', methods=['PUT'])
def api_update_machine_statut(id):
    """Met à jour le statut d'une machine, notes, raison de réparation."""
    data = request.get_json()
    statut = data.get('statut', 'disponible')
    if statut not in ('disponible', 'en_reparation', 'hors_service'):
        return jsonify({'success': False, 'error': 'Statut invalide'}), 400
    notes = data.get('notes', '')
    raison_reparation = data.get('raison_reparation', '')
    date_reparation = data.get('date_reparation', '')
    # Auto-set repair date when switching to en_reparation
    if statut in ('en_reparation', 'hors_service') and not date_reparation:
        date_reparation = datetime.now().strftime('%Y-%m-%d %H:%M')
    if statut == 'disponible':
        raison_reparation = ''
        date_reparation = ''
    db = get_db()
    try:
        db.execute('UPDATE machines SET statut=?, notes=?, raison_reparation=?, date_reparation=? WHERE id=?',
                   (statut, notes, raison_reparation, date_reparation, id))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ============================================================
# API — CHAMPS PERSONNALISÉS
# ============================================================

@app.route('/api/custom-fields', methods=['GET'])
def api_get_custom_fields():
    """Liste les champs personnalisés, filtrable par entity_type."""
    db = get_db()
    try:
        entity_type = request.args.get('entity_type', '')
        if entity_type:
            rows = db.execute('SELECT * FROM custom_fields WHERE entity_type=? AND actif=1 ORDER BY position', (entity_type,)).fetchall()
        else:
            rows = db.execute('SELECT * FROM custom_fields WHERE actif=1 ORDER BY entity_type, position').fetchall()
        return jsonify(rows_to_list(rows))
    finally:
        db.close()

@app.route('/api/custom-fields', methods=['POST'])
def api_add_custom_field():
    data = request.get_json(); db = get_db()
    try:
        cur = db.execute(
            'INSERT INTO custom_fields (entity_type,field_name,field_label,field_type,options,obligatoire,position) VALUES (?,?,?,?,?,?,?)',
            (data['entity_type'], data['field_name'], data['field_label'],
             data.get('field_type','text'), data.get('options',''),
             int(data.get('obligatoire',0)), int(data.get('position',0))))
        db.commit()
        return jsonify({'success': True, 'id': cur.lastrowid})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()

@app.route('/api/custom-fields/<int:id>', methods=['PUT'])
def api_update_custom_field(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('UPDATE custom_fields SET field_label=?,field_type=?,options=?,obligatoire=?,position=? WHERE id=?',
                   (data['field_label'], data.get('field_type','text'), data.get('options',''),
                    int(data.get('obligatoire',0)), int(data.get('position',0)), id))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()

@app.route('/api/custom-fields/<int:id>', methods=['DELETE'])
def api_delete_custom_field(id):
    db = get_db()
    try:
        db.execute('UPDATE custom_fields SET actif=0 WHERE id=?', (id,))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()

@app.route('/api/custom-field-values/<entity_type>/<int:entity_id>', methods=['GET'])
def api_get_custom_values(entity_type, entity_id):
    db = get_db()
    try:
        rows = db.execute('''SELECT cfv.*, cf.field_label, cf.field_type
            FROM custom_field_values cfv JOIN custom_fields cf ON cfv.custom_field_id=cf.id
            WHERE cfv.entity_type=? AND cfv.entity_id=?''', (entity_type, entity_id)).fetchall()
        return jsonify(rows_to_list(rows))
    finally:
        db.close()

@app.route('/api/custom-field-values/<entity_type>/<int:entity_id>', methods=['POST'])
def api_save_custom_values(entity_type, entity_id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('DELETE FROM custom_field_values WHERE entity_type=? AND entity_id=?', (entity_type, entity_id))
        for field_id, value in data.get('values', {}).items():
            db.execute('INSERT INTO custom_field_values (entity_type,entity_id,custom_field_id,value) VALUES (?,?,?,?)',
                       (entity_type, entity_id, int(field_id), str(value)))
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ============================================================
# API — SUPPRESSION DE MASSE
# ============================================================

@app.route('/api/<entity>/mass-delete', methods=['POST'])
def api_mass_delete(entity):
    """Supprime (désactive) plusieurs éléments à la fois."""
    allowed = {'machines','materiaux','classes','referents','preparateurs','types_activite'}
    if entity not in allowed:
        return jsonify({'success':False,'error':'Entité inconnue'}), 400

    data = request.get_json()
    ids = data.get('ids', [])
    if not ids:
        return jsonify({'success':False,'error':'Aucun ID fourni'}), 400

    db = get_db()
    try:
        placeholders = ','.join('?' * len(ids))
        db.execute(f'UPDATE {entity} SET actif=0 WHERE id IN ({placeholders})', ids)
        db.commit()
        return jsonify({'success':True,'count':len(ids)})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()


# ============================================================
# API — DÉMONSTRATION & RÉINITIALISATION
# ============================================================

@app.route('/api/demo/generate', methods=['POST'])
def api_generate_demo():
    """Génère des données de démonstration."""
    try:
        count = generate_demo_data()
        return jsonify({'success':True,'count':count,'message':f'{count} consommations de démo créées'})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 500

@app.route('/api/reset', methods=['POST'])
def api_reset():
    """Réinitialise la base. Requiert confirmation='REINITIALISER'."""
    data = request.get_json()
    if data.get('confirmation') != 'REINITIALISER':
        return jsonify({'success':False,'error':'Tapez REINITIALISER pour confirmer'}), 400
    try:
        reset_db()
        return jsonify({'success':True,'message':'Base de données réinitialisée'})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 500


# ============================================================
# API — SAUVEGARDE / RESTAURATION (.fabtrack)
# ============================================================

@app.route('/api/backup/settings', methods=['GET'])
def api_backup_settings_get():
    """Retourne les paramètres de sauvegarde automatique."""
    cfg = _load_backup_config()
    return jsonify(cfg)

@app.route('/api/backup/settings', methods=['PUT'])
def api_backup_settings_put():
    """Met à jour les paramètres de sauvegarde (fréquence, chemin, max)."""
    data = request.get_json()
    cfg = _load_backup_config()
    freq = data.get('frequency', cfg.get('frequency', 'off'))
    if freq not in ('off', 'daily', 'weekly'):
        return jsonify({'success': False, 'error': 'Fréquence invalide (off, daily, weekly)'}), 400
    cfg['frequency'] = freq
    if 'max_backups' in data:
        cfg['max_backups'] = max(1, min(int(data['max_backups']), 100))
    if 'backup_path' in data:
        new_path = data['backup_path'].strip()
        if new_path:
            # Tenter de créer le dossier s'il n'existe pas
            try:
                os.makedirs(new_path, exist_ok=True)
            except OSError:
                pass
            if not os.path.isdir(new_path):
                return jsonify({'success': False, 'error': f'Le dossier est inaccessible : {new_path}'}), 400
            # Test d'écriture
            test_file = os.path.join(new_path, '.fabtrack_write_test')
            try:
                with open(test_file, 'w') as tf:
                    tf.write('test')
                os.remove(test_file)
            except OSError:
                return jsonify({'success': False, 'error': f'Le dossier n\'est pas accessible en écriture : {new_path}'}), 400
        cfg['backup_path'] = new_path
    _save_backup_config(cfg)
    return jsonify({'success': True, **cfg})

@app.route('/api/backup/create', methods=['POST'])
def api_backup_create():
    """Crée une sauvegarde manuelle de la base de données."""
    try:
        fname = _create_backup('manuel')
        if fname:
            cfg = _load_backup_config()
            cfg['last_backup'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            _save_backup_config(cfg)
            return jsonify({'success': True, 'filename': fname, 'message': f'Sauvegarde créée : {fname}'})
        return jsonify({'success': False, 'error': 'Base de données introuvable'}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/backup/list')
def api_backup_list():
    """Liste toutes les sauvegardes existantes."""
    folder = _get_backup_folder()
    backups = []
    for fp in sorted(glob.glob(os.path.join(folder, '*.fabtrack')), key=os.path.getmtime, reverse=True):
        fname = os.path.basename(fp)
        stat = os.stat(fp)
        backups.append({
            'filename': fname,
            'size_bytes': stat.st_size,
            'size_human': _human_size(stat.st_size),
            'created': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S'),
        })
    return jsonify(backups)

def _human_size(nbytes):
    """Convertit des octets en unité lisible."""
    for unit in ('o', 'Ko', 'Mo', 'Go'):
        if nbytes < 1024:
            return f'{nbytes:.1f} {unit}'
        nbytes /= 1024
    return f'{nbytes:.1f} To'

@app.route('/api/backup/export/<filename>')
def api_backup_export(filename):
    """Télécharge un fichier de sauvegarde .fabtrack."""
    safe = secure_filename(filename)
    if not safe.endswith('.fabtrack'):
        return jsonify({'error': 'Fichier invalide'}), 400
    folder = _get_backup_folder()
    fp = os.path.join(folder, safe)
    if not os.path.exists(fp):
        return jsonify({'error': 'Fichier introuvable'}), 404
    return send_file(fp, as_attachment=True, download_name=safe,
                     mimetype='application/octet-stream')

@app.route('/api/backup/export-current')
def api_backup_export_current():
    """Exporte la base de données actuelle en .fabtrack (sans créer de sauvegarde permanente)."""
    from models import DB_PATH
    if not os.path.exists(DB_PATH):
        return jsonify({'error': 'Base introuvable'}), 404
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(DB_PATH, as_attachment=True,
                     download_name=f'fabtrack_export_{ts}.fabtrack',
                     mimetype='application/octet-stream')

@app.route('/api/backup/import', methods=['POST'])
def api_backup_import():
    """Importe un fichier .fabtrack pour remplacer la base de données actuelle."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'error': 'Aucun fichier fourni'}), 400
    f = request.files['file']
    if not f.filename or not f.filename.endswith('.fabtrack'):
        return jsonify({'success': False, 'error': 'Le fichier doit avoir l\'extension .fabtrack'}), 400
    from models import DB_PATH
    import sqlite3
    import tempfile
    # Sauvegarder une copie de sécurité avant remplacement
    try:
        if os.path.exists(DB_PATH):
            _create_backup('avant_import')
        # Écrire dans un fichier temporaire d'abord pour vérifier la validité
        tmp_fd, tmp_path = tempfile.mkstemp(suffix='.db', dir=BASE_DIR)
        os.close(tmp_fd)
        f.save(tmp_path)
        # Vérifier que c'est bien une base SQLite valide avec les tables attendues
        try:
            test_conn = sqlite3.connect(tmp_path)
            tables = [r[0] for r in test_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
            test_conn.close()
            required = {'consommations', 'machines', 'materiaux', 'types_activite'}
            if not required.issubset(set(tables)):
                os.remove(tmp_path)
                return jsonify({'success': False,
                    'error': f'Base invalide. Tables requises manquantes : {required - set(tables)}'}), 400
        except sqlite3.DatabaseError:
            os.remove(tmp_path)
            return jsonify({'success': False, 'error': 'Le fichier n\'est pas une base SQLite valide'}), 400
        # Remplacer la base
        if os.path.exists(DB_PATH):
            os.remove(DB_PATH)
        shutil.move(tmp_path, DB_PATH)
        # Réinitialiser le flag pour forcer la vérification au prochain requête
        global _db_initialized
        _db_initialized = False
        return jsonify({'success': True, 'message': 'Base de données importée avec succès',
                        'tables': tables})
    except Exception as e:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/backup/delete/<filename>', methods=['DELETE'])
def api_backup_delete(filename):
    """Supprime un fichier de sauvegarde."""
    safe = secure_filename(filename)
    if not safe.endswith('.fabtrack'):
        return jsonify({'success': False, 'error': 'Fichier invalide'}), 400
    folder = _get_backup_folder()
    fp = os.path.join(folder, safe)
    if not os.path.exists(fp):
        return jsonify({'success': False, 'error': 'Fichier introuvable'}), 404
    os.remove(fp)
    return jsonify({'success': True})

@app.route('/api/backup/validate-path', methods=['POST'])
def api_backup_validate_path():
    """Valide qu'un chemin est accessible en écriture pour les sauvegardes."""
    data = request.get_json()
    path = data.get('path', '').strip()
    if not path:
        return jsonify({'valid': False, 'error': 'Chemin vide'}), 400
    try:
        os.makedirs(path, exist_ok=True)
    except OSError as e:
        return jsonify({'valid': False, 'error': f'Impossible de créer le dossier : {e}'}), 400
    if not os.path.isdir(path):
        return jsonify({'valid': False, 'error': 'Ce chemin n\'est pas un dossier valide'}), 400
    # Test écriture
    test_file = os.path.join(path, '.fabtrack_write_test')
    try:
        with open(test_file, 'w') as tf:
            tf.write('test')
        os.remove(test_file)
    except OSError:
        return jsonify({'valid': False, 'error': 'Le dossier n\'est pas accessible en écriture'}), 400
    # Compter les sauvegardes existantes
    existing = glob.glob(os.path.join(path, '*.fabtrack'))
    return jsonify({'valid': True, 'path': os.path.abspath(path),
                    'existing_backups': len(existing),
                    'message': f'Chemin valide ({len(existing)} sauvegarde(s) existante(s))'})


# ============================================================
# LANCEMENT
# ============================================================

if __name__ == '__main__':
    init_db()
    print("\n" + "="*50)
    print("  🏭 FabTrack v2 — Suivi Consommation Fablab")
    print("  📍 http://localhost:5555")
    print("  📍 Réseau: http://<IP>:5555")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5555, debug=True)
