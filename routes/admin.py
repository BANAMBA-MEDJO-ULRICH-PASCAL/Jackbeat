from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, Response, jsonify)
from flask_login import login_user, logout_user, login_required, current_user
from flask_wtf.csrf import generate_csrf
from models import db, Admin, Artiste, Oeuvre
from datetime import datetime, timedelta
import csv, io

admin_bp = Blueprint('admin_bp', __name__)


# ════════════════════════════════════════════════
#  AUTHENTIFICATION
# ════════════════════════════════════════════════

@admin_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_bp.dashboard'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        admin    = Admin.query.filter_by(username=username).first()

        if admin and admin.check_password(password):
            login_user(admin, remember=True)
            flash('Connexion réussie. Bienvenue dans l\'espace admin Jackbeat.', 'success')
            return redirect(request.args.get('next') or url_for('admin_bp.dashboard'))
        else:
            error = 'Identifiants incorrects. Veuillez réessayer.'

    return render_template('admin/login.html',
                           csrf_token=generate_csrf(),
                           error=error)


@admin_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Vous avez été déconnecté.', 'info')
    return redirect(url_for('main_bp.index'))


# ════════════════════════════════════════════════
#  TABLEAU DE BORD ADMIN
# ════════════════════════════════════════════════

@admin_bp.route('/')
@login_required
def dashboard():
    # Compteurs par statut
    stats = {
        'artistes_attente':   Artiste.query.filter_by(statut='en_attente').count(),
        'artistes_approuves': Artiste.query.filter_by(statut='approuve').count(),
        'artistes_rejetes':   Artiste.query.filter_by(statut='rejete').count(),
        'oeuvres_attente':    Oeuvre.query.filter_by(statut='en_attente').count(),
        'oeuvres_approuvees': Oeuvre.query.filter_by(statut='approuve').count(),
        'oeuvres_rejetees':   Oeuvre.query.filter_by(statut='rejete').count(),
    }
    stats['total_attente'] = stats['artistes_attente'] + stats['oeuvres_attente']

    # Activité récente : soumissions des 7 derniers jours
    sept_jours = datetime.utcnow() - timedelta(days=7)
    stats['soumissions_semaine'] = (
        Artiste.query.filter(Artiste.created_at >= sept_jours).count() +
        Oeuvre.query.filter(Oeuvre.created_at >= sept_jours).count()
    )

    # File d'attente
    artistes_attente = (Artiste.query.filter_by(statut='en_attente')
                        .order_by(Artiste.created_at.asc()).all())
    oeuvres_attente  = (Oeuvre.query.filter_by(statut='en_attente')
                        .order_by(Oeuvre.created_at.asc()).all())

    # Dernières approbations
    dernieres_approbations = (Oeuvre.query.filter_by(statut='approuve')
                              .order_by(Oeuvre.created_at.desc()).limit(8).all())

    return render_template('admin/dashboard.html',
                           stats=stats,
                           artistes_attente=artistes_attente,
                           oeuvres_attente=oeuvres_attente,
                           dernieres_approbations=dernieres_approbations)


# ════════════════════════════════════════════════
#  ARTISTES — LISTE + DÉTAIL + ACTIONS
# ════════════════════════════════════════════════

@admin_bp.route('/artistes')
@login_required
def artistes():
    statut  = request.args.get('statut', 'en_attente')
    search  = request.args.get('q', '').strip()

    q = Artiste.query.filter_by(statut=statut)
    if search:
        q = q.filter(Artiste.nom.ilike(f'%{search}%'))
    artistes_list = q.order_by(Artiste.created_at.desc()).all()

    counts = {
        'en_attente': Artiste.query.filter_by(statut='en_attente').count(),
        'approuve':   Artiste.query.filter_by(statut='approuve').count(),
        'rejete':     Artiste.query.filter_by(statut='rejete').count(),
    }
    return render_template('admin/artistes.html',
                           artistes=artistes_list,
                           statut=statut,
                           search=search,
                           counts=counts)


@admin_bp.route('/artiste/<int:id>')
@login_required
def artiste_detail(id):
    artiste = Artiste.query.get_or_404(id)
    oeuvres = artiste.oeuvres.order_by(Oeuvre.annee_sortie.desc()).all()
    return render_template('admin/artiste_detail.html',
                           artiste=artiste, oeuvres=oeuvres)


@admin_bp.route('/artiste/<int:id>/action/<action>')
@login_required
def action_artiste(id, action):
    artiste = Artiste.query.get_or_404(id)
    nom     = artiste.nom

    if action == 'approuver':
        artiste.statut = 'approuve'
        flash(f'✅ Artiste « {nom} » approuvé et publié.', 'success')
    elif action == 'rejeter':
        artiste.statut = 'rejete'
        flash(f'Artiste « {nom} » rejeté.', 'warning')
    elif action == 'remettre_attente':
        artiste.statut = 'en_attente'
        flash(f'Artiste « {nom} » remis en attente.', 'info')
    elif action == 'supprimer':
        db.session.delete(artiste)
        db.session.commit()
        flash(f'🗑 Artiste « {nom} » supprimé définitivement.', 'danger')
        return redirect(url_for('admin_bp.artistes'))

    db.session.commit()
    # Retour intelligent : page de détail si on vient de là
    referer = request.referrer or ''
    if f'/artiste/{id}' in referer:
        return redirect(url_for('admin_bp.artiste_detail', id=id))
    return redirect(referer or url_for('admin_bp.artistes'))


@admin_bp.route('/artiste/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def artiste_edit(id):
    from models import REGIONS_CAMEROUN
    artiste = Artiste.query.get_or_404(id)
    regions = REGIONS_CAMEROUN

    if request.method == 'POST':
        artiste.nom           = request.form.get('nom', '').strip()
        artiste.nom_reel      = request.form.get('nom_reel', '').strip() or None
        artiste.region_origine= request.form.get('region_origine', '')
        artiste.type_artiste  = request.form.get('type_artiste', '')
        annee_debut           = request.form.get('annee_debut', '')
        annee_fin             = request.form.get('annee_fin', '')
        artiste.annee_debut   = int(annee_debut) if annee_debut.isdigit() else None
        artiste.annee_fin     = int(annee_fin)   if annee_fin.isdigit()   else None
        artiste.biographie    = request.form.get('biographie', '').strip() or None
        db.session.commit()
        flash(f'✅ Artiste « {artiste.nom} » mis à jour.', 'success')
        return redirect(url_for('admin_bp.artiste_detail', id=id))

    return render_template('admin/artiste_edit.html',
                           artiste=artiste, regions=regions)


# ════════════════════════════════════════════════
#  ŒUVRES — LISTE + DÉTAIL + ACTIONS
# ════════════════════════════════════════════════

@admin_bp.route('/oeuvres')
@login_required
def oeuvres():
    statut = request.args.get('statut', 'en_attente')
    search = request.args.get('q', '').strip()

    q = Oeuvre.query.filter_by(statut=statut)
    if search:
        q = q.filter(
            db.or_(Oeuvre.titre.ilike(f'%{search}%'),
                   Oeuvre.genre_musical.ilike(f'%{search}%'))
        )
    oeuvres_list = q.order_by(Oeuvre.created_at.desc()).all()

    counts = {
        'en_attente': Oeuvre.query.filter_by(statut='en_attente').count(),
        'approuve':   Oeuvre.query.filter_by(statut='approuve').count(),
        'rejete':     Oeuvre.query.filter_by(statut='rejete').count(),
    }
    return render_template('admin/oeuvres.html',
                           oeuvres=oeuvres_list,
                           statut=statut,
                           search=search,
                           counts=counts)


@admin_bp.route('/oeuvre/<int:id>')
@login_required
def oeuvre_detail(id):
    oeuvre = Oeuvre.query.get_or_404(id)
    return render_template('admin/oeuvre_detail.html', oeuvre=oeuvre)


@admin_bp.route('/oeuvre/<int:id>/action/<action>')
@login_required
def action_oeuvre(id, action):
    oeuvre = Oeuvre.query.get_or_404(id)
    titre  = oeuvre.titre

    if action == 'approuver':
        # Auto-approuver l'artiste associé s'il est encore en attente
        if oeuvre.artiste and oeuvre.artiste.statut == 'en_attente':
            oeuvre.artiste.statut = 'approuve'
        oeuvre.statut = 'approuve'
        flash(f'✅ Œuvre « {titre} » approuvée et publiée.', 'success')
    elif action == 'rejeter':
        oeuvre.statut = 'rejete'
        flash(f'Œuvre « {titre} » rejetée.', 'warning')
    elif action == 'remettre_attente':
        oeuvre.statut = 'en_attente'
        flash(f'Œuvre « {titre} » remise en attente.', 'info')
    elif action == 'supprimer':
        db.session.delete(oeuvre)
        db.session.commit()
        flash(f'🗑 Œuvre « {titre} » supprimée définitivement.', 'danger')
        return redirect(url_for('admin_bp.oeuvres'))

    db.session.commit()
    referer = request.referrer or ''
    if f'/oeuvre/{id}' in referer:
        return redirect(url_for('admin_bp.oeuvre_detail', id=id))
    return redirect(referer or url_for('admin_bp.oeuvres'))


@admin_bp.route('/oeuvre/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def oeuvre_edit(id):
    from models import GENRES_MUSICAUX, LANGUES, POPULARITES
    oeuvre = Oeuvre.query.get_or_404(id)

    if request.method == 'POST':
        oeuvre.titre         = request.form.get('titre', '').strip()
        oeuvre.type_oeuvre   = request.form.get('type_oeuvre', '')
        oeuvre.genre_musical = request.form.get('genre_musical', '')
        oeuvre.langue        = request.form.get('langue', '')
        annee                = request.form.get('annee_sortie', '')
        oeuvre.annee_sortie  = int(annee) if annee.isdigit() else oeuvre.annee_sortie
        oeuvre.popularite    = request.form.get('popularite', '') or None
        oeuvre.distinction   = request.form.get('distinction', '').strip() or None
        oeuvre.description   = request.form.get('description', '').strip() or None
        oeuvre.lien_youtube  = request.form.get('lien_youtube', '').strip() or None
        db.session.commit()
        flash(f'✅ Œuvre « {oeuvre.titre} » mise à jour.', 'success')
        return redirect(url_for('admin_bp.oeuvre_detail', id=id))

    return render_template('admin/oeuvre_edit.html',
                           oeuvre=oeuvre,
                           genres=GENRES_MUSICAUX,
                           langues=LANGUES,
                           popularites=POPULARITES)


# ════════════════════════════════════════════════
#  ACTIONS EN LOT (BULK)
# ════════════════════════════════════════════════

@admin_bp.route('/bulk', methods=['POST'])
@login_required
def bulk_action():
    """Approuver ou rejeter plusieurs entrées en une seule action."""
    action     = request.form.get('action')
    model_type = request.form.get('model')  # 'artiste' ou 'oeuvre'
    ids_raw    = request.form.getlist('ids')

    if not ids_raw or action not in ('approuver', 'rejeter', 'supprimer'):
        flash('Action invalide.', 'danger')
        return redirect(request.referrer or url_for('admin_bp.dashboard'))

    ids = [int(i) for i in ids_raw if i.isdigit()]
    Model = Artiste if model_type == 'artiste' else Oeuvre
    items = Model.query.filter(Model.id.in_(ids)).all()

    count = 0
    for item in items:
        if action == 'approuver':
            item.statut = 'approuve'
            # Auto-approuver artiste lié si c'est une œuvre
            if model_type == 'oeuvre' and item.artiste and item.artiste.statut == 'en_attente':
                item.artiste.statut = 'approuve'
        elif action == 'rejeter':
            item.statut = 'rejete'
        elif action == 'supprimer':
            db.session.delete(item)
        count += 1

    db.session.commit()
    labels = {'approuver': 'approuvé(s)', 'rejeter': 'rejeté(s)', 'supprimer': 'supprimé(s)'}
    flash(f'✅ {count} entrée(s) {labels[action]}.', 'success')
    return redirect(request.referrer or url_for('admin_bp.dashboard'))


# ════════════════════════════════════════════════
#  EXPORT CSV
# ════════════════════════════════════════════════

@admin_bp.route('/export/oeuvres.csv')
@login_required
def export_csv():
    oeuvres = (Oeuvre.query.filter_by(statut='approuve')
               .order_by(Oeuvre.annee_sortie).all())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Titre', 'Artiste', 'Région', 'Type',
                     'Genre', 'Langue', 'Année', 'Décennie',
                     'Popularité', 'Distinction', 'Lien YouTube', 'Soumis par'])
    for o in oeuvres:
        writer.writerow([
            o.id, o.titre,
            o.artiste.nom            if o.artiste else '',
            o.artiste.region_origine if o.artiste else '',
            o.type_oeuvre, o.genre_musical, o.langue,
            o.annee_sortie, o.decennie or '',
            o.popularite or '', o.distinction or '',
            o.lien_youtube or '', o.soumis_par or '',
        ])
    output.seek(0)
    return Response(
        output.getvalue(), mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=jackbeat_donnees.csv'}
    )


# ════════════════════════════════════════════════
#  API ADMIN — résumé JSON (pour tests)
# ════════════════════════════════════════════════

@admin_bp.route('/api/summary')
@login_required
def api_summary():
    return jsonify({
        'artistes': {
            'en_attente': Artiste.query.filter_by(statut='en_attente').count(),
            'approuves':  Artiste.query.filter_by(statut='approuve').count(),
            'rejetes':    Artiste.query.filter_by(statut='rejete').count(),
        },
        'oeuvres': {
            'en_attente': Oeuvre.query.filter_by(statut='en_attente').count(),
            'approuvees': Oeuvre.query.filter_by(statut='approuve').count(),
            'rejetees':   Oeuvre.query.filter_by(statut='rejete').count(),
        },
        'timestamp': datetime.utcnow().isoformat()
    })
