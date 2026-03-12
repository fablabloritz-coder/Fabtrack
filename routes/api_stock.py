"""Routes du module Stock — CRUD articles, mouvements, catégories, fournisseurs, inventaire."""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from models import get_db
from datetime import datetime

bp = Blueprint('stock', __name__, url_prefix='/stock')


def _rows_to_list(rows):
    return [dict(r) for r in rows]


# ============================================================
#  PAGES HTML
# ============================================================

@bp.route('/')
def stock_index():
    """Dashboard stock — vue par catégorie, alertes, mouvements récents."""
    db = get_db()
    try:
        categories = db.execute(
            'SELECT * FROM stock_categories ORDER BY ordre, nom'
        ).fetchall()

        articles = db.execute('''
            SELECT a.*, c.nom AS cat_nom, c.couleur AS cat_couleur, c.icone AS cat_icone,
                   f.nom AS fourn_nom
            FROM stock_articles a
            LEFT JOIN stock_categories c ON a.categorie_id = c.id
            LEFT JOIN stock_fournisseurs f ON a.fournisseur_id = f.id
            WHERE a.actif = 1
            ORDER BY c.ordre, c.nom, a.nom
        ''').fetchall()

        mouvements = db.execute('''
            SELECT m.*, a.nom AS article_nom, a.unite
            FROM stock_mouvements m
            JOIN stock_articles a ON m.article_id = a.id
            ORDER BY m.date DESC, m.id DESC LIMIT 8
        ''').fetchall()

        nb_articles = len(articles)
        nb_alertes = sum(1 for a in articles
                         if a['quantite_minimum'] is not None
                         and a['quantite_actuelle'] < a['quantite_minimum'])

        # Grouper articles par catégorie
        cat_articles = {}
        for a in articles:
            cid = a['categorie_id'] or 0
            cat_articles.setdefault(cid, []).append(a)

        return render_template('stock/index.html', page='stock',
                               categories=categories, articles=articles,
                               cat_articles=cat_articles,
                               mouvements=mouvements,
                               nb_articles=nb_articles, nb_alertes=nb_alertes)
    finally:
        db.close()


@bp.route('/articles')
def stock_articles():
    """Liste des articles avec filtres."""
    db = get_db()
    try:
        categories = db.execute('SELECT * FROM stock_categories ORDER BY ordre, nom').fetchall()
        fournisseurs = db.execute('SELECT * FROM stock_fournisseurs WHERE actif=1 ORDER BY nom').fetchall()
        unites = db.execute('SELECT * FROM stock_unites ORDER BY ordre, nom').fetchall()

        # Filtres
        cat_id = request.args.get('categorie', type=int)
        statut = request.args.get('statut', '')
        fourn_id = request.args.get('fournisseur', type=int)
        recherche = request.args.get('q', '').strip()

        query = '''
            SELECT a.*, c.nom AS cat_nom, c.couleur AS cat_couleur,
                   f.nom AS fourn_nom
            FROM stock_articles a
            LEFT JOIN stock_categories c ON a.categorie_id = c.id
            LEFT JOIN stock_fournisseurs f ON a.fournisseur_id = f.id
            WHERE a.actif = 1
        '''
        params = []

        if cat_id:
            query += ' AND a.categorie_id = ?'
            params.append(cat_id)
        if fourn_id:
            query += ' AND a.fournisseur_id = ?'
            params.append(fourn_id)
        if recherche:
            query += ' AND (a.nom LIKE ? OR a.reference LIKE ? OR a.emplacement LIKE ?)'
            like = f'%{recherche}%'
            params.extend([like, like, like])
        if statut == 'faible':
            query += ' AND a.quantite_minimum IS NOT NULL AND a.quantite_actuelle > 0 AND a.quantite_actuelle < a.quantite_minimum'
        elif statut == 'vide':
            query += ' AND a.quantite_actuelle <= 0'
        elif statut == 'ok':
            query += ' AND (a.quantite_minimum IS NULL OR a.quantite_actuelle >= a.quantite_minimum)'

        query += ' ORDER BY c.ordre, a.nom'
        articles = db.execute(query, params).fetchall()

        return render_template('stock/articles.html', page='stock',
                               articles=articles, categories=categories,
                               fournisseurs=fournisseurs, unites=unites,
                               filtre_cat=cat_id, filtre_statut=statut,
                               filtre_fourn=fourn_id, filtre_q=recherche)
    finally:
        db.close()


@bp.route('/mouvements')
def stock_mouvements():
    """Historique des mouvements avec filtres et pagination."""
    db = get_db()
    try:
        page_num = request.args.get('page', 1, type=int)
        per_page = 50
        offset = (page_num - 1) * per_page

        article_id = request.args.get('article', type=int)
        type_mvt = request.args.get('type', '')
        source = request.args.get('source', '')

        query = '''
            SELECT m.*, a.nom AS article_nom, a.unite
            FROM stock_mouvements m
            JOIN stock_articles a ON m.article_id = a.id
            WHERE 1=1
        '''
        count_query = '''
            SELECT COUNT(*) AS cnt FROM stock_mouvements m WHERE 1=1
        '''
        params = []
        count_params = []

        if article_id:
            query += ' AND m.article_id = ?'
            count_query += ' AND m.article_id = ?'
            params.append(article_id)
            count_params.append(article_id)
        if type_mvt:
            query += ' AND m.type = ?'
            count_query += ' AND m.type = ?'
            params.append(type_mvt)
            count_params.append(type_mvt)
        if source:
            query += ' AND m.source = ?'
            count_query += ' AND m.source = ?'
            params.append(source)
            count_params.append(source)

        total = db.execute(count_query, count_params).fetchone()['cnt']
        query += ' ORDER BY m.date DESC, m.id DESC LIMIT ? OFFSET ?'
        params.extend([per_page, offset])
        mouvements = db.execute(query, params).fetchall()

        articles = db.execute(
            'SELECT id, nom FROM stock_articles WHERE actif=1 ORDER BY nom'
        ).fetchall()

        total_pages = (total + per_page - 1) // per_page

        return render_template('stock/mouvements.html', page='stock',
                               mouvements=mouvements, articles=articles,
                               page_num=page_num, total_pages=total_pages,
                               total=total,
                               filtre_article=article_id, filtre_type=type_mvt,
                               filtre_source=source)
    finally:
        db.close()


@bp.route('/fournisseurs')
def stock_fournisseurs():
    """Liste des fournisseurs."""
    db = get_db()
    try:
        fournisseurs = db.execute('''
            SELECT f.*, COUNT(a.id) AS nb_articles
            FROM stock_fournisseurs f
            LEFT JOIN stock_articles a ON a.fournisseur_id = f.id AND a.actif = 1
            WHERE f.actif = 1
            GROUP BY f.id
            ORDER BY f.nom
        ''').fetchall()
        return render_template('stock/fournisseurs.html', page='stock',
                               fournisseurs=fournisseurs)
    finally:
        db.close()


@bp.route('/inventaire')
def stock_inventaire():
    """Page d'inventaire physique."""
    db = get_db()
    try:
        categories = db.execute('SELECT * FROM stock_categories ORDER BY ordre, nom').fetchall()
        articles = db.execute('''
            SELECT a.*, c.nom AS cat_nom, c.couleur AS cat_couleur
            FROM stock_articles a
            LEFT JOIN stock_categories c ON a.categorie_id = c.id
            WHERE a.actif = 1
            ORDER BY c.ordre, c.nom, a.nom
        ''').fetchall()
        return render_template('stock/inventaire.html', page='stock',
                               categories=categories, articles=articles)
    finally:
        db.close()


@bp.route('/categories')
def stock_categories():
    """Liste des catégories de stock."""
    db = get_db()
    try:
        categories = db.execute('''
            SELECT c.*, COUNT(a.id) AS nb_articles
            FROM stock_categories c
            LEFT JOIN stock_articles a ON a.categorie_id = c.id AND a.actif = 1
            GROUP BY c.id
            ORDER BY c.ordre, c.nom
        ''').fetchall()
        return render_template('stock/categories.html', page='stock',
                               categories=categories)
    finally:
        db.close()


# ============================================================
#  API JSON — Articles
# ============================================================

@bp.route('/api/articles', methods=['GET'])
def api_stock_articles():
    """Liste des articles en JSON."""
    db = get_db()
    try:
        articles = db.execute('''
            SELECT a.*, c.nom AS cat_nom, f.nom AS fourn_nom
            FROM stock_articles a
            LEFT JOIN stock_categories c ON a.categorie_id = c.id
            LEFT JOIN stock_fournisseurs f ON a.fournisseur_id = f.id
            WHERE a.actif = 1
            ORDER BY a.nom
        ''').fetchall()
        return jsonify(_rows_to_list(articles))
    finally:
        db.close()


@bp.route('/api/articles/<int:article_id>', methods=['GET'])
def api_stock_article(article_id):
    """Détail d'un article en JSON."""
    db = get_db()
    try:
        a = db.execute('''
            SELECT a.*, c.nom AS cat_nom, f.nom AS fourn_nom
            FROM stock_articles a
            LEFT JOIN stock_categories c ON a.categorie_id = c.id
            LEFT JOIN stock_fournisseurs f ON a.fournisseur_id = f.id
            WHERE a.id = ?
        ''', (article_id,)).fetchone()
        if not a:
            return jsonify({'error': 'Article introuvable'}), 404
        return jsonify(dict(a))
    finally:
        db.close()


@bp.route('/api/articles', methods=['POST'])
def api_stock_add_article():
    """Crée un article (JSON ou formulaire)."""
    db = get_db()
    try:
        data = request.get_json() if request.is_json else request.form
        nom = (data.get('nom') or '').strip()
        if not nom:
            return jsonify({'success': False, 'error': 'Nom requis'}), 400

        cur = db.execute('''
            INSERT INTO stock_articles
            (nom, reference, categorie_id, fournisseur_id, unite,
             longueur_cm, largeur_cm, quantite_actuelle,
             quantite_minimum, quantite_maximum, prix_unitaire,
             emplacement, description)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            nom,
            (data.get('reference') or '').strip(),
            data.get('categorie_id') or None,
            data.get('fournisseur_id') or None,
            data.get('unite', 'pièce'),
            _to_float(data.get('longueur_cm')),
            _to_float(data.get('largeur_cm')),
            _to_float(data.get('quantite_actuelle')) or 0,
            _to_float(data.get('quantite_minimum')),
            _to_float(data.get('quantite_maximum')),
            _to_float(data.get('prix_unitaire')),
            (data.get('emplacement') or '').strip(),
            (data.get('description') or '').strip(),
        ))
        article_id = cur.lastrowid

        # Mouvement initial si quantité > 0
        qte_init = _to_float(data.get('quantite_actuelle')) or 0
        if qte_init > 0:
            db.execute('''
                INSERT INTO stock_mouvements
                (article_id, type, quantite, quantite_avant, quantite_apres, source, notes)
                VALUES (?, 'entree', ?, 0, ?, 'manuel', 'Stock initial')
            ''', (article_id, qte_init, qte_init))

        db.commit()
        if request.is_json:
            return jsonify({'success': True, 'id': article_id})
        flash('Article ajouté avec succès', 'success')
        return redirect(url_for('stock.stock_articles'))
    finally:
        db.close()


@bp.route('/api/articles/<int:article_id>', methods=['PUT', 'POST'])
def api_stock_update_article(article_id):
    """Met à jour un article."""
    db = get_db()
    try:
        existing = db.execute('SELECT id FROM stock_articles WHERE id=?', (article_id,)).fetchone()
        if not existing:
            return jsonify({'success': False, 'error': 'Article introuvable'}), 404

        data = request.get_json() if request.is_json else request.form
        db.execute('''
            UPDATE stock_articles SET
                nom=?, reference=?, categorie_id=?, fournisseur_id=?,
                unite=?, longueur_cm=?, largeur_cm=?,
                quantite_minimum=?, quantite_maximum=?, prix_unitaire=?,
                emplacement=?, description=?, date_modification=?
            WHERE id=?
        ''', (
            (data.get('nom') or '').strip(),
            (data.get('reference') or '').strip(),
            data.get('categorie_id') or None,
            data.get('fournisseur_id') or None,
            data.get('unite', 'pièce'),
            _to_float(data.get('longueur_cm')),
            _to_float(data.get('largeur_cm')),
            _to_float(data.get('quantite_minimum')),
            _to_float(data.get('quantite_maximum')),
            _to_float(data.get('prix_unitaire')),
            (data.get('emplacement') or '').strip(),
            (data.get('description') or '').strip(),
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            article_id,
        ))
        db.commit()
        if request.is_json:
            return jsonify({'success': True})
        flash('Article mis à jour', 'success')
        return redirect(url_for('stock.stock_articles'))
    finally:
        db.close()


@bp.route('/api/articles/<int:article_id>/archiver', methods=['POST'])
def api_stock_archive_article(article_id):
    """Archive (soft delete) un article."""
    db = get_db()
    try:
        db.execute('UPDATE stock_articles SET actif=0 WHERE id=?', (article_id,))
        db.commit()
        if request.is_json:
            return jsonify({'success': True})
        flash('Article archivé', 'success')
        return redirect(url_for('stock.stock_articles'))
    finally:
        db.close()


# ============================================================
#  API JSON — Mouvements
# ============================================================

@bp.route('/api/mouvements', methods=['POST'])
def api_stock_add_mouvement():
    """Crée un mouvement de stock (entrée ou sortie)."""
    db = get_db()
    try:
        data = request.get_json() if request.is_json else request.form
        article_id = int(data['article_id'])
        type_mvt = data['type']
        quantite = float(data['quantite'])

        if type_mvt not in ('entree', 'sortie'):
            return jsonify({'success': False, 'error': 'Type invalide'}), 400
        if quantite <= 0:
            return jsonify({'success': False, 'error': 'Quantité invalide'}), 400

        article = db.execute(
            'SELECT quantite_actuelle FROM stock_articles WHERE id=? AND actif=1',
            (article_id,)
        ).fetchone()
        if not article:
            return jsonify({'success': False, 'error': 'Article introuvable'}), 404

        avant = article['quantite_actuelle']
        if type_mvt == 'sortie':
            apres = avant - quantite
            if apres < 0:
                return jsonify({'success': False, 'error': 'Stock insuffisant'}), 400
        else:
            apres = avant + quantite

        db.execute('''
            INSERT INTO stock_mouvements
            (article_id, type, quantite, quantite_avant, quantite_apres, source, utilisateur, notes)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (
            article_id, type_mvt, quantite, avant, apres,
            data.get('source', 'manuel'),
            (data.get('utilisateur') or '').strip(),
            (data.get('notes') or '').strip(),
        ))
        db.execute(
            'UPDATE stock_articles SET quantite_actuelle=?, date_modification=? WHERE id=?',
            (apres, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), article_id)
        )
        db.commit()

        if request.is_json:
            return jsonify({'success': True, 'quantite_avant': avant, 'quantite_apres': apres})
        flash(f"{'Entrée' if type_mvt == 'entree' else 'Sortie'} enregistrée", 'success')
        return redirect(url_for('stock.stock_mouvements'))
    finally:
        db.close()


@bp.route('/api/mouvements/rapide', methods=['POST'])
def api_stock_mouvement_rapide():
    """Mouvement rapide en JSON (depuis modal stock)."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'Données manquantes'}), 400
    # Délègue au handler principal
    return api_stock_add_mouvement()


# ============================================================
#  API JSON — Inventaire physique
# ============================================================

@bp.route('/api/inventaire/valider', methods=['POST'])
def api_stock_validate_inventaire():
    """Valide un inventaire physique — crée des ajustements pour les écarts."""
    db = get_db()
    try:
        data = request.get_json() if request.is_json else request.form
        articles = db.execute(
            'SELECT id, nom, quantite_actuelle FROM stock_articles WHERE actif=1'
        ).fetchall()

        ajustements = 0
        for a in articles:
            key = f"compte_{a['id']}"
            val = data.get(key)
            if val is None or val == '':
                continue
            compte = float(val)
            ecart = compte - a['quantite_actuelle']
            if abs(ecart) < 0.001:
                continue

            db.execute('''
                INSERT INTO stock_mouvements
                (article_id, type, quantite, quantite_avant, quantite_apres, source, notes)
                VALUES (?, 'ajustement', ?, ?, ?, 'inventaire', ?)
            ''', (
                a['id'], abs(ecart), a['quantite_actuelle'], compte,
                f"Inventaire physique — écart : {'+'if ecart>0 else ''}{ecart:.2f}"
            ))
            db.execute(
                'UPDATE stock_articles SET quantite_actuelle=?, date_modification=? WHERE id=?',
                (compte, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), a['id'])
            )
            ajustements += 1

        db.commit()
        if request.is_json:
            return jsonify({'success': True, 'ajustements': ajustements})
        flash(f'Inventaire validé — {ajustements} ajustement(s)', 'success')
        return redirect(url_for('stock.stock_index'))
    finally:
        db.close()


# ============================================================
#  API JSON — Catégories
# ============================================================

@bp.route('/api/categories', methods=['GET'])
def api_stock_categories():
    db = get_db()
    try:
        rows = db.execute('SELECT * FROM stock_categories ORDER BY ordre, nom').fetchall()
        return jsonify(_rows_to_list(rows))
    finally:
        db.close()


@bp.route('/api/categories', methods=['POST'])
def api_stock_add_categorie():
    db = get_db()
    try:
        data = request.get_json() if request.is_json else request.form
        nom = (data.get('nom') or '').strip()
        if not nom:
            return jsonify({'success': False, 'error': 'Nom requis'}), 400
        db.execute(
            'INSERT INTO stock_categories (nom, couleur, icone, ordre) VALUES (?,?,?,?)',
            (nom, data.get('couleur', '#198754'), data.get('icone', 'bi-box'),
             int(data.get('ordre', 0)))
        )
        db.commit()
        if request.is_json:
            return jsonify({'success': True})
        flash('Catégorie ajoutée', 'success')
        return redirect(url_for('stock.stock_categories'))
    finally:
        db.close()


@bp.route('/api/categories/<int:cat_id>', methods=['PUT', 'POST'])
def api_stock_update_categorie(cat_id):
    db = get_db()
    try:
        data = request.get_json() if request.is_json else request.form
        db.execute(
            'UPDATE stock_categories SET nom=?, couleur=?, icone=?, ordre=? WHERE id=?',
            ((data.get('nom') or '').strip(), data.get('couleur', '#198754'),
             data.get('icone', 'bi-box'), int(data.get('ordre', 0)), cat_id)
        )
        db.commit()
        if request.is_json:
            return jsonify({'success': True})
        flash('Catégorie mise à jour', 'success')
        return redirect(url_for('stock.stock_categories'))
    finally:
        db.close()


@bp.route('/api/categories/<int:cat_id>/supprimer', methods=['POST'])
def api_stock_delete_categorie(cat_id):
    db = get_db()
    try:
        linked = db.execute(
            'SELECT COUNT(*) AS cnt FROM stock_articles WHERE categorie_id=? AND actif=1',
            (cat_id,)
        ).fetchone()['cnt']
        if linked > 0:
            if request.is_json:
                return jsonify({'success': False, 'error': f'{linked} article(s) liés'}), 400
            flash(f'Impossible : {linked} article(s) liés à cette catégorie', 'danger')
            return redirect(url_for('stock.stock_categories'))
        db.execute('DELETE FROM stock_categories WHERE id=?', (cat_id,))
        db.commit()
        if request.is_json:
            return jsonify({'success': True})
        flash('Catégorie supprimée', 'success')
        return redirect(url_for('stock.stock_categories'))
    finally:
        db.close()


# ============================================================
#  API JSON — Fournisseurs
# ============================================================

@bp.route('/api/fournisseurs', methods=['GET'])
def api_stock_fournisseurs():
    db = get_db()
    try:
        rows = db.execute('SELECT * FROM stock_fournisseurs WHERE actif=1 ORDER BY nom').fetchall()
        return jsonify(_rows_to_list(rows))
    finally:
        db.close()


@bp.route('/api/fournisseurs/<int:fourn_id>', methods=['GET'])
def api_stock_fournisseur(fourn_id):
    db = get_db()
    try:
        f = db.execute('SELECT * FROM stock_fournisseurs WHERE id=?', (fourn_id,)).fetchone()
        if not f:
            return jsonify({'error': 'Fournisseur introuvable'}), 404
        return jsonify(dict(f))
    finally:
        db.close()


@bp.route('/api/fournisseurs', methods=['POST'])
def api_stock_add_fournisseur():
    db = get_db()
    try:
        data = request.get_json() if request.is_json else request.form
        nom = (data.get('nom') or '').strip()
        if not nom:
            return jsonify({'success': False, 'error': 'Nom requis'}), 400
        db.execute('''
            INSERT INTO stock_fournisseurs
            (nom, contact, email, telephone, telephone2, url_google, specialites, notes)
            VALUES (?,?,?,?,?,?,?,?)
        ''', (
            nom,
            (data.get('contact') or '').strip(),
            (data.get('email') or '').strip(),
            (data.get('telephone') or '').strip(),
            (data.get('telephone2') or '').strip(),
            (data.get('url_google') or '').strip(),
            (data.get('specialites') or '').strip(),
            (data.get('notes') or '').strip(),
        ))
        db.commit()
        if request.is_json:
            return jsonify({'success': True})
        flash('Fournisseur ajouté', 'success')
        return redirect(url_for('stock.stock_fournisseurs'))
    finally:
        db.close()


@bp.route('/api/fournisseurs/<int:fourn_id>', methods=['PUT', 'POST'])
def api_stock_update_fournisseur(fourn_id):
    db = get_db()
    try:
        data = request.get_json() if request.is_json else request.form
        db.execute('''
            UPDATE stock_fournisseurs SET
                nom=?, contact=?, email=?, telephone=?, telephone2=?,
                url_google=?, specialites=?, notes=?
            WHERE id=?
        ''', (
            (data.get('nom') or '').strip(),
            (data.get('contact') or '').strip(),
            (data.get('email') or '').strip(),
            (data.get('telephone') or '').strip(),
            (data.get('telephone2') or '').strip(),
            (data.get('url_google') or '').strip(),
            (data.get('specialites') or '').strip(),
            (data.get('notes') or '').strip(),
            fourn_id,
        ))
        db.commit()
        if request.is_json:
            return jsonify({'success': True})
        flash('Fournisseur mis à jour', 'success')
        return redirect(url_for('stock.stock_fournisseurs'))
    finally:
        db.close()


@bp.route('/api/fournisseurs/<int:fourn_id>/archiver', methods=['POST'])
def api_stock_archive_fournisseur(fourn_id):
    db = get_db()
    try:
        linked = db.execute(
            'SELECT COUNT(*) AS cnt FROM stock_articles WHERE fournisseur_id=? AND actif=1',
            (fourn_id,)
        ).fetchone()['cnt']
        if linked > 0:
            if request.is_json:
                return jsonify({'success': False, 'error': f'{linked} article(s) liés'}), 400
            flash(f'Impossible : {linked} article(s) liés à ce fournisseur', 'danger')
            return redirect(url_for('stock.stock_fournisseurs'))
        db.execute('UPDATE stock_fournisseurs SET actif=0 WHERE id=?', (fourn_id,))
        db.commit()
        if request.is_json:
            return jsonify({'success': True})
        flash('Fournisseur archivé', 'success')
        return redirect(url_for('stock.stock_fournisseurs'))
    finally:
        db.close()


# ============================================================
#  API JSON — Unités
# ============================================================

@bp.route('/api/unites', methods=['GET'])
def api_stock_unites():
    db = get_db()
    try:
        rows = db.execute('SELECT * FROM stock_unites ORDER BY ordre, nom').fetchall()
        return jsonify(_rows_to_list(rows))
    finally:
        db.close()


# ============================================================
#  UTILITAIRES
# ============================================================

def _to_float(val):
    """Convertit une valeur en float ou retourne None."""
    if val is None or val == '':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
