"""
FabTrack v2 — Application Flask principale
Suivi de consommation pour Fablab (Loritz)
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response
from models import get_db, init_db, reset_db, generate_demo_data
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import csv, io, json, os

app = Flask(__name__)
app.secret_key = 'fabtrack-secret-2025'

# Upload config
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'}
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# INIT
# ============================================================

@app.before_request
def ensure_db():
    import os
    from models import DB_PATH
    if not os.path.exists(DB_PATH):
        init_db()


# ============================================================
# HELPERS
# ============================================================

def row_to_dict(row):
    return dict(row) if row else None

def rows_to_list(rows):
    return [dict(r) for r in rows]


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
            'materiaux':     rows_to_list(db.execute('SELECT * FROM materiaux WHERE actif=1 ORDER BY type_activite_id, nom').fetchall()),
            'classes':       rows_to_list(db.execute('SELECT * FROM classes WHERE actif=1 ORDER BY nom').fetchall()),
            'referents':     rows_to_list(db.execute('SELECT * FROM referents WHERE actif=1 ORDER BY categorie, nom').fetchall()),
            'salles':        rows_to_list(db.execute('SELECT * FROM salles WHERE actif=1 ORDER BY nom').fetchall()),
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
        page     = int(request.args.get('page',1))
        per_page = int(request.args.get('per_page',50))

        query = '''
            SELECT c.*, p.nom as preparateur_nom,
                   t.nom as type_activite_nom, t.icone as type_icone, t.badge_class,
                   m.nom as machine_nom,
                   cl.nom as classe_nom,
                   r.nom as referent_nom, r.categorie as referent_categorie,
                   s.nom as salle_nom,
                   mat.nom as materiau_nom, mat.unite as materiau_unite
            FROM consommations c
            LEFT JOIN preparateurs p ON c.preparateur_id=p.id
            LEFT JOIN types_activite t ON c.type_activite_id=t.id
            LEFT JOIN machines m ON c.machine_id=m.id
            LEFT JOIN classes cl ON c.classe_id=cl.id
            LEFT JOIN referents r ON c.referent_id=r.id
            LEFT JOIN salles s ON c.salle_id=s.id
            LEFT JOIN materiaux mat ON c.materiau_id=mat.id
            WHERE 1=1
        '''
        params = []
        count_q = 'SELECT COUNT(*) as total FROM consommations c WHERE 1=1'
        cp = []

        for col, val, cast in [
            ('c.date_saisie >=', date_debut, str),
            ('c.date_saisie <=', date_fin, str),
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

        cur = db.execute('''
            INSERT INTO consommations (
                date_saisie, preparateur_id, type_activite_id, machine_id,
                classe_id, referent_id, salle_id, materiau_id,
                quantite, unite,
                poids_grammes, longueur_mm, largeur_mm, surface_m2, epaisseur,
                nb_feuilles, format_papier,
                nb_feuilles_plastique, type_feuille, commentaire
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            data.get('date_saisie', datetime.now().strftime('%Y-%m-%d')),
            data.get('preparateur_id'), data.get('type_activite_id'),
            data.get('machine_id') or None, data.get('classe_id') or None,
            data.get('referent_id') or None, data.get('salle_id') or None,
            data.get('materiau_id') or None,
            data.get('quantite') or 0, data.get('unite',''),
            data.get('poids_grammes') or None,
            data.get('longueur_mm') or None, data.get('largeur_mm') or None,
            surface or data.get('surface_m2') or None,
            data.get('epaisseur') or None,
            data.get('nb_feuilles') or None, data.get('format_papier') or None,
            data.get('nb_feuilles_plastique') or None,
            data.get('type_feuille') or None, data.get('commentaire',''),
        ))
        db.commit()
        return jsonify({'success':True,'id':cur.lastrowid}), 201
    except Exception as e:
        db.rollback(); return jsonify({'success':False,'error':str(e)}), 400
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

        db.execute('''
            UPDATE consommations SET
                date_saisie=?, preparateur_id=?, type_activite_id=?, machine_id=?,
                classe_id=?, referent_id=?, salle_id=?, materiau_id=?,
                quantite=?, unite=?,
                poids_grammes=?, longueur_mm=?, largeur_mm=?, surface_m2=?, epaisseur=?,
                nb_feuilles=?, format_papier=?,
                nb_feuilles_plastique=?, type_feuille=?, commentaire=?,
                updated_at=datetime('now','localtime')
            WHERE id=?
        ''', (
            data.get('date_saisie'), data.get('preparateur_id'),
            data.get('type_activite_id'), data.get('machine_id') or None,
            data.get('classe_id') or None, data.get('referent_id') or None,
            data.get('salle_id') or None, data.get('materiau_id') or None,
            data.get('quantite') or 0, data.get('unite',''),
            data.get('poids_grammes') or None,
            data.get('longueur_mm') or None, data.get('largeur_mm') or None,
            surface or data.get('surface_m2') or None,
            data.get('epaisseur') or None,
            data.get('nb_feuilles') or None, data.get('format_papier') or None,
            data.get('nb_feuilles_plastique') or None,
            data.get('type_feuille') or None, data.get('commentaire',''), id,
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
        if df: w+=' AND c.date_saisie <= ?'; p.append(df)

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

        return jsonify({
            'total_interventions': total,
            'by_type': by_type, 'by_preparateur': by_prep,
            'total_3d_grammes': round(total_3d, 1),
            'total_decoupe_m2': round(total_decoupe, 3),
            'total_papier_feuilles': int(total_papier),
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
        if df: w+=' AND c.date_saisie <= ?'; p.append(df)

        dex = {"day":"c.date_saisie","week":"strftime('%Y-W%W',c.date_saisie)","month":"strftime('%Y-%m',c.date_saisie)"}.get(gb,"strftime('%Y-%m',c.date_saisie)")

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
        w = '1=1'; p = []
        if dd: w+=' AND c.date_saisie >= ?'; p.append(dd)
        if df: w+=' AND c.date_saisie <= ?'; p.append(df)

        rows = db.execute(f'''
            SELECT c.date_saisie,p.nom as preparateur,t.nom as type_activite,
                   m.nom as machine,cl.nom as classe,r.nom as referent,r.categorie as ref_categorie,
                   s.nom as salle,mat.nom as materiau,
                   c.poids_grammes,c.surface_m2,c.longueur_mm,c.largeur_mm,
                   c.epaisseur,c.nb_feuilles,c.format_papier,
                   c.nb_feuilles_plastique,c.type_feuille,c.commentaire
            FROM consommations c
            LEFT JOIN preparateurs p ON c.preparateur_id=p.id
            LEFT JOIN types_activite t ON c.type_activite_id=t.id
            LEFT JOIN machines m ON c.machine_id=m.id
            LEFT JOIN classes cl ON c.classe_id=cl.id
            LEFT JOIN referents r ON c.referent_id=r.id
            LEFT JOIN salles s ON c.salle_id=s.id
            LEFT JOIN materiaux mat ON c.materiau_id=mat.id
            WHERE {w} ORDER BY c.date_saisie DESC
        ''', p).fetchall()

        out = io.StringIO()
        out.write('\ufeff')  # BOM Excel
        wr = csv.writer(out, delimiter=';')
        wr.writerow(['Date','Préparateur','Type activité','Machine','Classe',
                      'Référent','Catégorie réf.','Salle','Matériau',
                      'Poids (g)','Surface (m²)','Longueur (mm)','Largeur (mm)',
                      'Épaisseur','Nb feuilles','Format papier',
                      'Nb feuilles plastique','Type feuille','Commentaire'])
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
    'machines':   ('nom;type_activite;quantite;marque;zone_travail;puissance;description\n'
                   'Exemple Machine;Impression 3D;1;Marque;300x300 mm;100W;Description\n'),
    'materiaux':  ('nom;type_activite;unite\n'
                   'Exemple Matériau;Impression 3D;g\n'),
    'classes':    ('nom\n501\n502\nBTS CPRP\n'),
    'referents':  ('nom;categorie\n'
                   'M. Dupont;Professeur\nMme Martin;Agent technique\nEntreprise X;Demande extérieure\n'),
    'salles':     ('nom\nSalle B12\nAtelier Nord\n'),
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
                    db.execute('INSERT INTO machines (nom,type_activite_id,quantite,marque,zone_travail,puissance,description) VALUES (?,?,?,?,?,?,?)',
                               (row['nom'].strip(), tid, int(row.get('quantite',1) or 1),
                                row.get('marque','').strip(), row.get('zone_travail','').strip(),
                                row.get('puissance','').strip(), row.get('description','').strip()))

                elif entity == 'materiaux':
                    tid = type_map.get(row.get('type_activite','').strip())
                    if not tid:
                        errors.append(f"Ligne {i}: type activité inconnu"); continue
                    db.execute('INSERT OR IGNORE INTO materiaux (nom,type_activite_id,unite) VALUES (?,?,?)',
                               (row['nom'].strip(), tid, row.get('unite','').strip()))

                elif entity == 'classes':
                    db.execute('INSERT OR IGNORE INTO classes (nom) VALUES (?)', (row['nom'].strip(),))

                elif entity == 'referents':
                    cat = row.get('categorie','Professeur').strip() or 'Professeur'
                    db.execute('INSERT OR IGNORE INTO referents (nom,categorie) VALUES (?,?)',
                               (row['nom'].strip(), cat))

                elif entity == 'salles':
                    db.execute('INSERT OR IGNORE INTO salles (nom) VALUES (?)', (row['nom'].strip(),))

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
        cur = db.execute(
            'INSERT OR IGNORE INTO types_activite (nom,icone,couleur,badge_class,unite_defaut) VALUES (?,?,?,?,?)',
            (data['nom'].strip(), data.get('icone','🔧'), data.get('couleur','#6b7280'),
             data.get('badge_class',''), data.get('unite_defaut','')))
        db.commit()
        return jsonify({'success':True,'id':cur.lastrowid})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/types_activite/<int:id>', methods=['PUT'])
def api_update_type_activite(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('UPDATE types_activite SET nom=?,icone=?,couleur=?,unite_defaut=? WHERE id=?',
                   (data['nom'].strip(), data.get('icone',''), data.get('couleur',''),
                    data.get('unite_defaut',''), id))
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
            'INSERT INTO machines (nom,type_activite_id,quantite,marque,zone_travail,puissance,description) VALUES (?,?,?,?,?,?,?)',
            (data['nom'].strip(), data['type_activite_id'],
             int(data.get('quantite',1) or 1),
             data.get('marque','').strip(), data.get('zone_travail','').strip(),
             data.get('puissance','').strip(), data.get('description','').strip()))
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
                      marque=?,zone_travail=?,puissance=?,description=?,statut=?,image_path=? WHERE id=?''',
                   (data['nom'].strip(), data['type_activite_id'],
                    int(data.get('quantite',1) or 1),
                    data.get('marque','').strip(), data.get('zone_travail','').strip(),
                    data.get('puissance','').strip(), data.get('description','').strip(),
                    data.get('statut','disponible'), data.get('image_path',''), id))
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
        cur = db.execute('INSERT INTO materiaux (nom,type_activite_id,unite) VALUES (?,?,?)',
                         (data['nom'].strip(), data['type_activite_id'], data.get('unite','')))
        db.commit()
        return jsonify({'success':True,'id':cur.lastrowid})
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
        db.execute('UPDATE materiaux SET nom=?,type_activite_id=?,unite=?,image_path=? WHERE id=?',
                   (data['nom'].strip(), data['type_activite_id'], data.get('unite',''),
                    data.get('image_path',''), id))
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
        cur = db.execute('INSERT OR IGNORE INTO classes (nom) VALUES (?)', (data['nom'].strip(),))
        db.commit()
        return jsonify({'success':True,'id':cur.lastrowid})
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
        cat = data.get('categorie','Professeur').strip() or 'Professeur'
        cur = db.execute('INSERT OR IGNORE INTO referents (nom,categorie) VALUES (?,?)',
                         (data['nom'].strip(), cat))
        db.commit()
        return jsonify({'success':True,'id':cur.lastrowid})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/referents/<int:id>', methods=['PUT'])
def api_update_referent(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('UPDATE referents SET nom=?,categorie=? WHERE id=?',
                   (data['nom'].strip(), data.get('categorie','Professeur'), id))
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

# ---- Salles ----
@app.route('/api/salles', methods=['POST'])
def api_add_salle():
    data = request.get_json(); db = get_db()
    try:
        cur = db.execute('INSERT OR IGNORE INTO salles (nom) VALUES (?)', (data['nom'].strip(),))
        db.commit()
        return jsonify({'success':True,'id':cur.lastrowid})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/salles/<int:id>', methods=['DELETE'])
def api_delete_salle(id):
    db = get_db()
    try:
        db.execute('UPDATE salles SET actif=0 WHERE id=?',(id,)); db.commit()
        return jsonify({'success':True})
    except Exception as e:
        return jsonify({'success':False,'error':str(e)}), 400
    finally:
        db.close()

@app.route('/api/salles/<int:id>', methods=['PUT'])
def api_update_salle(id):
    data = request.get_json(); db = get_db()
    try:
        db.execute('UPDATE salles SET nom=?,image_path=? WHERE id=?',
                   (data['nom'].strip(), data.get('image_path',''), id))
        db.commit()
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
        cur = db.execute('INSERT OR IGNORE INTO preparateurs (nom) VALUES (?)', (data['nom'].strip(),))
        db.commit()
        return jsonify({'success':True,'id':cur.lastrowid})
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
    'salles': 'salle_id',
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
        if replacement_id:
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
    """Met à jour le statut d'une machine."""
    data = request.get_json()
    statut = data.get('statut', 'disponible')
    if statut not in ('disponible', 'en_reparation', 'hors_service'):
        return jsonify({'success': False, 'error': 'Statut invalide'}), 400
    db = get_db()
    try:
        db.execute('UPDATE machines SET statut=? WHERE id=?', (statut, id))
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
    allowed = {'machines','materiaux','classes','referents','salles','preparateurs','types_activite'}
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
