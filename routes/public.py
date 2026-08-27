"""
routes/public.py — Exploration publique : artistes, œuvres, recherche,
                   lecteur YouTube, likes, commentaires.
"""
import hashlib, re
from flask import (Blueprint, render_template, redirect, url_for,
                   request, jsonify, abort, flash)
from models import db, Artiste, Oeuvre, Like, Commentaire
from sqlalchemy import func, or_

public_bp = Blueprint('public_bp', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_ip_hash(req):
    """Retourne un hash SHA-256 de l'IP du visiteur (anonymisation RGPD)."""
    ip = req.headers.get('X-Forwarded-For', req.remote_addr or '0.0.0.0')
    ip = ip.split(',')[0].strip()
    return hashlib.sha256(ip.encode()).hexdigest()


def sanitize(text, max_len=500):
    """Nettoie et tronque un texte saisi par l'utilisateur."""
    if not text:
        return ''
    # Supprimer les balises HTML basiques
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()[:max_len]


# ── CATALOGUE ARTISTES ────────────────────────────────────────────────────────

@public_bp.route('/artistes')
def artistes():
    """Liste paginée de tous les artistes approuvés."""
    page    = request.args.get('page',   1,   type=int)
    region  = request.args.get('region', '')
    genre   = request.args.get('genre',  '')
    tri     = request.args.get('tri',    'nom')   # nom | vues | recent

    q = Artiste.query.filter_by(statut='approuve')

    if region:
        q = q.filter(Artiste.region_origine == region)

    # Tri
    if tri == 'vues':
        q = q.order_by(Artiste.nb_vues.desc())
    elif tri == 'recent':
        q = q.order_by(Artiste.created_at.desc())
    else:
        q = q.order_by(Artiste.nom.asc())

    artistes_page = q.paginate(page=page, per_page=12, error_out=False)

    # Données pour les filtres
    regions = [r[0] for r in db.session.query(Artiste.region_origine)
               .filter_by(statut='approuve').distinct().order_by(Artiste.region_origine)]

    # Statistiques rapides
    total = Artiste.query.filter_by(statut='approuve').count()

    return render_template('public/artistes.html',
                           artistes=artistes_page,
                           regions=regions,
                           actifs=dict(region=region, genre=genre, tri=tri),
                           total=total)


# ── FICHE ARTISTE ─────────────────────────────────────────────────────────────

@public_bp.route('/artiste/<int:id>')
@public_bp.route('/artiste/<int:id>/<slug>')
def artiste_detail(id, slug=None):
    """Page publique complète d'un artiste."""
    artiste = Artiste.query.filter_by(id=id, statut='approuve').first_or_404()

    # Incrémenter les vues
    artiste.nb_vues = (artiste.nb_vues or 0) + 1
    db.session.commit()

    oeuvres      = artiste.oeuvres_approuvees
    commentaires = (Commentaire.query
                    .filter_by(artiste_id=id, approuve=True)
                    .order_by(Commentaire.created_at.desc())
                    .limit(20).all())

    # L'utilisateur a-t-il déjà liké cet artiste ?
    ip_hash    = get_ip_hash(request)
    deja_like  = Like.query.filter_by(artiste_id=id, ip_hash=ip_hash).first() is not None

    # Artistes similaires (même région, autre artiste)
    similaires = (Artiste.query
                  .filter_by(statut='approuve', region_origine=artiste.region_origine)
                  .filter(Artiste.id != artiste.id)
                  .order_by(func.random())
                  .limit(4).all())

    return render_template('public/artiste_detail.html',
                           artiste=artiste,
                           oeuvres=oeuvres,
                           commentaires=commentaires,
                           deja_like=deja_like,
                           similaires=similaires,
                           nb_likes=artiste.nb_likes)


# ── FICHE ŒUVRE ───────────────────────────────────────────────────────────────

@public_bp.route('/oeuvre/<int:id>')
@public_bp.route('/oeuvre/<int:id>/<slug>')
def oeuvre_detail(id, slug=None):
    """Page publique complète d'une œuvre avec lecteur YouTube."""
    oeuvre = Oeuvre.query.filter_by(id=id, statut='approuve').first_or_404()

    # Incrémenter les vues
    oeuvre.nb_vues = (oeuvre.nb_vues or 0) + 1
    db.session.commit()

    commentaires = (Commentaire.query
                    .filter_by(oeuvre_id=id, approuve=True)
                    .order_by(Commentaire.created_at.desc())
                    .limit(20).all())

    ip_hash   = get_ip_hash(request)
    deja_like = Like.query.filter_by(oeuvre_id=id, ip_hash=ip_hash).first() is not None

    # Autres œuvres du même artiste
    autres_oeuvres = (Oeuvre.query
                      .filter_by(artiste_id=oeuvre.artiste_id, statut='approuve')
                      .filter(Oeuvre.id != oeuvre.id)
                      .order_by(Oeuvre.annee_sortie.desc())
                      .limit(5).all())

    # Œuvres du même genre
    meme_genre = (Oeuvre.query
                  .filter_by(genre_musical=oeuvre.genre_musical, statut='approuve')
                  .filter(Oeuvre.id != oeuvre.id)
                  .order_by(func.random())
                  .limit(4).all())

    return render_template('public/oeuvre_detail.html',
                           oeuvre=oeuvre,
                           commentaires=commentaires,
                           deja_like=deja_like,
                           autres_oeuvres=autres_oeuvres,
                           meme_genre=meme_genre,
                           nb_likes=oeuvre.nb_likes)


# ── RECHERCHE GLOBALE ─────────────────────────────────────────────────────────

@public_bp.route('/recherche')
def recherche():
    """Recherche plein texte sur artistes et œuvres."""
    q    = sanitize(request.args.get('q', ''), 100)
    page = request.args.get('page', 1, type=int)

    if not q or len(q) < 2:
        return render_template('public/recherche.html',
                               query='', artistes=[], oeuvres=[], total=0)

    terme = f'%{q}%'

    artistes_res = (Artiste.query
                    .filter_by(statut='approuve')
                    .filter(or_(
                        Artiste.nom.ilike(terme),
                        Artiste.nom_reel.ilike(terme),
                        Artiste.biographie.ilike(terme),
                    ))
                    .order_by(Artiste.nb_vues.desc())
                    .limit(8).all())

    oeuvres_res = (Oeuvre.query
                   .filter_by(statut='approuve')
                   .filter(or_(
                       Oeuvre.titre.ilike(terme),
                       Oeuvre.genre_musical.ilike(terme),
                       Oeuvre.description.ilike(terme),
                       Oeuvre.distinction.ilike(terme),
                   ))
                   .order_by(Oeuvre.nb_vues.desc())
                   .limit(12).all())

    total = len(artistes_res) + len(oeuvres_res)

    return render_template('public/recherche.html',
                           query=q,
                           artistes=artistes_res,
                           oeuvres=oeuvres_res,
                           total=total)


@public_bp.route('/recherche/suggestions')
def recherche_suggestions():
    """API JSON — suggestions instantanées pour la barre de recherche."""
    q = sanitize(request.args.get('q', ''), 60)
    if not q or len(q) < 2:
        return jsonify([])

    terme = f'%{q}%'

    artistes = (Artiste.query
                .filter_by(statut='approuve')
                .filter(Artiste.nom.ilike(terme))
                .limit(4).all())

    oeuvres = (Oeuvre.query
               .filter_by(statut='approuve')
               .filter(Oeuvre.titre.ilike(terme))
               .limit(4).all())

    results = []
    for a in artistes:
        results.append({
            'type':  'artiste',
            'id':    a.id,
            'label': a.nom,
            'sub':   a.region_origine,
            'url':   url_for('public_bp.artiste_detail', id=a.id),
        })
    for o in oeuvres:
        results.append({
            'type':  'oeuvre',
            'id':    o.id,
            'label': o.titre,
            'sub':   f'{o.artiste.nom if o.artiste else ""} · {o.annee_sortie}',
            'url':   url_for('public_bp.oeuvre_detail', id=o.id),
            'thumb': o.youtube_thumb,
        })

    return jsonify(results)


# ── LIKES ─────────────────────────────────────────────────────────────────────

@public_bp.route('/like/oeuvre/<int:id>', methods=['POST'])
def like_oeuvre(id):
    """Toggle like sur une œuvre — 1 like par IP."""
    oeuvre = Oeuvre.query.filter_by(id=id, statut='approuve').first_or_404()
    ip_hash = get_ip_hash(request)

    existing = Like.query.filter_by(oeuvre_id=id, ip_hash=ip_hash).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(Like(oeuvre_id=id, ip_hash=ip_hash))
        liked = True

    db.session.commit()
    nb = Like.query.filter_by(oeuvre_id=id).count()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'liked': liked, 'nb': nb})
    return redirect(url_for('public_bp.oeuvre_detail', id=id))


@public_bp.route('/like/artiste/<int:id>', methods=['POST'])
def like_artiste(id):
    """Toggle like sur un artiste — 1 like par IP."""
    artiste = Artiste.query.filter_by(id=id, statut='approuve').first_or_404()
    ip_hash = get_ip_hash(request)

    existing = Like.query.filter_by(artiste_id=id, ip_hash=ip_hash).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(Like(artiste_id=id, ip_hash=ip_hash))
        liked = True

    db.session.commit()
    nb = Like.query.filter_by(artiste_id=id).count()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'liked': liked, 'nb': nb})
    return redirect(url_for('public_bp.artiste_detail', id=id))


# ── COMMENTAIRES ──────────────────────────────────────────────────────────────

@public_bp.route('/commenter/oeuvre/<int:id>', methods=['POST'])
def commenter_oeuvre(id):
    """Soumettre un commentaire sur une œuvre."""
    oeuvre = Oeuvre.query.filter_by(id=id, statut='approuve').first_or_404()

    auteur = sanitize(request.form.get('auteur', ''), 80)
    texte  = sanitize(request.form.get('texte', ''),  500)

    if not auteur or len(auteur) < 2:
        flash('Veuillez entrer votre prénom.', 'warning')
        return redirect(url_for('public_bp.oeuvre_detail', id=id))

    if not texte or len(texte) < 5:
        flash('Le commentaire est trop court.', 'warning')
        return redirect(url_for('public_bp.oeuvre_detail', id=id))

    # Anti-spam : max 3 commentaires par IP par œuvre
    ip_hash = get_ip_hash(request)
    nb_spam = Commentaire.query.filter_by(oeuvre_id=id, ip_hash=ip_hash).count()
    if nb_spam >= 3:
        flash('Vous avez déjà posté plusieurs commentaires sur cette œuvre.', 'warning')
        return redirect(url_for('public_bp.oeuvre_detail', id=id))

    c = Commentaire(oeuvre_id=id, auteur=auteur, texte=texte,
                    ip_hash=ip_hash, approuve=False)
    db.session.add(c)
    db.session.commit()
    flash('✅ Commentaire soumis — il sera visible après modération.', 'success')
    return redirect(url_for('public_bp.oeuvre_detail', id=id))


@public_bp.route('/commenter/artiste/<int:id>', methods=['POST'])
def commenter_artiste(id):
    """Soumettre un commentaire sur un artiste."""
    artiste = Artiste.query.filter_by(id=id, statut='approuve').first_or_404()

    auteur = sanitize(request.form.get('auteur', ''), 80)
    texte  = sanitize(request.form.get('texte',  ''), 500)

    if not auteur or len(auteur) < 2 or not texte or len(texte) < 5:
        flash('Veuillez remplir tous les champs correctement.', 'warning')
        return redirect(url_for('public_bp.artiste_detail', id=id))

    ip_hash = get_ip_hash(request)
    nb_spam = Commentaire.query.filter_by(artiste_id=id, ip_hash=ip_hash).count()
    if nb_spam >= 3:
        flash('Vous avez déjà posté plusieurs commentaires.', 'warning')
        return redirect(url_for('public_bp.artiste_detail', id=id))

    c = Commentaire(artiste_id=id, auteur=auteur, texte=texte,
                    ip_hash=ip_hash, approuve=False)
    db.session.add(c)
    db.session.commit()
    flash('✅ Commentaire soumis — il sera visible après modération.', 'success')
    return redirect(url_for('public_bp.artiste_detail', id=id))


# ── TOP CHARTS ────────────────────────────────────────────────────────────────

@public_bp.route('/top')
def top_charts():
    """Page Top — œuvres et artistes les plus populaires."""
    top_oeuvres_vues = (Oeuvre.query.filter_by(statut='approuve')
                        .order_by(Oeuvre.nb_vues.desc()).limit(10).all())
    top_oeuvres_likes = (db.session.query(Oeuvre, func.count(Like.id).label('nb'))
                         .join(Like, Like.oeuvre_id == Oeuvre.id)
                         .filter(Oeuvre.statut == 'approuve')
                         .group_by(Oeuvre.id)
                         .order_by(func.count(Like.id).desc())
                         .limit(10).all())
    top_artistes = (Artiste.query.filter_by(statut='approuve')
                    .order_by(Artiste.nb_vues.desc()).limit(8).all())

    return render_template('public/top_charts.html',
                           top_oeuvres_vues=top_oeuvres_vues,
                           top_oeuvres_likes=top_oeuvres_likes,
                           top_artistes=top_artistes)


# ════════════════════════════════════════════════
#  SIGNALEMENTS (Phase 2)
# ════════════════════════════════════════════════

from models import Signalement, RAISONS_SIGNALEMENT

@public_bp.route('/signaler/<cible_type>/<int:id>', methods=['GET', 'POST'])
def signaler(cible_type, id):
    if cible_type not in ('artiste', 'oeuvre'):
        abort(404)

    if cible_type == 'artiste':
        cible = Artiste.query.filter_by(id=id, statut='approuve').first_or_404()
        retour_url = url_for('public_bp.artiste_detail', id=id)
    else:
        cible = Oeuvre.query.filter_by(id=id, statut='approuve').first_or_404()
        retour_url = url_for('public_bp.oeuvre_detail', id=id)

    if request.method == 'POST':
        raison      = request.form.get('raison', '').strip()
        description = sanitize(request.form.get('description', ''), 800)
        email       = sanitize(request.form.get('email', ''), 150)
        ip_hash     = get_ip_hash(request)

        if not raison or raison not in [r[0] for r in RAISONS_SIGNALEMENT]:
            flash('Veuillez sélectionner une raison.', 'warning')
            return redirect(request.url)

        # Anti-spam : max 3 signalements par IP par cible
        filtre = dict(ip_hash=ip_hash,
                      **(dict(artiste_id=id) if cible_type=='artiste' else dict(oeuvre_id=id)))
        if Signalement.query.filter_by(**filtre).count() >= 3:
            flash('Vous avez déjà signalé cette entrée plusieurs fois.', 'warning')
            return redirect(retour_url)

        s = Signalement(
            cible_type    = cible_type,
            artiste_id    = id if cible_type == 'artiste' else None,
            oeuvre_id     = id if cible_type == 'oeuvre'  else None,
            raison        = raison,
            description   = description or None,
            email_contact = email or None,
            ip_hash       = ip_hash,
            statut        = 'nouveau',
        )
        db.session.add(s)
        db.session.commit()
        flash('✅ Merci ! Votre signalement sera traité rapidement.', 'success')
        return redirect(retour_url)

    return render_template('public/signaler.html',
                           cible=cible,
                           cible_type=cible_type,
                           raisons=RAISONS_SIGNALEMENT,
                           retour_url=retour_url)
