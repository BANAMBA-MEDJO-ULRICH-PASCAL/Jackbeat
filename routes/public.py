"""
routes/public.py — Exploration publique : artistes, œuvres, recherche,
                   lecteur YouTube, likes, commentaires, signalements.
"""
import re

from flask import (Blueprint, render_template, redirect, url_for,
                   request, jsonify, abort, flash, session, g)
from flask_babel import gettext as _
from sqlalchemy import func, or_

from models import (db, Artiste, Oeuvre, Like, Commentaire, Signalement,
                    RAISONS_SIGNALEMENT, libelle)
from security import ip_hash, rate_limit

public_bp = Blueprint('public_bp', __name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def sanitize(text, max_len=500):
    """Nettoie et tronque un texte saisi par l'utilisateur (l'échappement HTML
    est de toute façon garanti par Jinja à l'affichage)."""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)   # caractères de contrôle
    return text.strip()[:max_len]


def compter_vue(kind, obj):
    """Une vue par visiteur (session) et par fiche — limite le gonflement artificiel."""
    key = f'{kind}{obj.id}'
    vues = session.get('vues', [])
    if key in vues:
        return
    obj.nb_vues = (obj.nb_vues or 0) + 1
    db.session.commit()
    session['vues'] = (vues + [key])[-60:]


def escape_like(term):
    return term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')


# ── CATALOGUE ARTISTES ────────────────────────────────────────────────────────

@public_bp.route('/artistes')
def artistes():
    """Liste paginée de tous les artistes approuvés."""
    page    = request.args.get('page',   1,   type=int)
    region  = request.args.get('region', '')
    tri     = request.args.get('tri',    'nom')   # nom | vues | recent

    q = Artiste.query.filter_by(statut='approuve')
    if region:
        q = q.filter(Artiste.region_origine == region)

    if tri == 'vues':
        q = q.order_by(Artiste.nb_vues.desc())
    elif tri == 'recent':
        q = q.order_by(Artiste.created_at.desc())
    else:
        q = q.order_by(Artiste.nom.asc())

    artistes_page = q.paginate(page=page, per_page=12, error_out=False)

    regions = [r[0] for r in db.session.query(Artiste.region_origine)
               .filter_by(statut='approuve').distinct().order_by(Artiste.region_origine)]
    total = Artiste.query.filter_by(statut='approuve').count()

    return render_template('public/artistes.html',
                           artistes=artistes_page,
                           regions=regions,
                           actifs=dict(region=region, tri=tri),
                           total=total)


# ── FICHE ARTISTE ─────────────────────────────────────────────────────────────

@public_bp.route('/artiste/<int:id>')
@public_bp.route('/artiste/<int:id>/<slug>')
def artiste_detail(id, slug=None):
    artiste = Artiste.query.filter_by(id=id, statut='approuve').first_or_404()
    compter_vue('a', artiste)

    oeuvres      = artiste.oeuvres_approuvees
    commentaires = (Commentaire.query
                    .filter_by(artiste_id=id, approuve=True)
                    .order_by(Commentaire.created_at.desc())
                    .limit(20).all())
    deja_like  = Like.query.filter_by(artiste_id=id, ip_hash=ip_hash()).first() is not None
    similaires = (Artiste.query
                  .filter_by(statut='approuve', region_origine=artiste.region_origine)
                  .filter(Artiste.id != artiste.id)
                  .order_by(func.random())
                  .limit(4).all())
    bio, bio_lang = artiste.biographie_pour(g.lang)

    return render_template('public/artiste_detail.html',
                           artiste=artiste, oeuvres=oeuvres, commentaires=commentaires,
                           deja_like=deja_like, similaires=similaires,
                           nb_likes=artiste.nb_likes, bio=bio, bio_lang=bio_lang)


# ── FICHE ŒUVRE ───────────────────────────────────────────────────────────────

@public_bp.route('/oeuvre/<int:id>')
@public_bp.route('/oeuvre/<int:id>/<slug>')
def oeuvre_detail(id, slug=None):
    oeuvre = Oeuvre.publiees().filter(Oeuvre.id == id).first_or_404()
    compter_vue('o', oeuvre)

    commentaires = (Commentaire.query
                    .filter_by(oeuvre_id=id, approuve=True)
                    .order_by(Commentaire.created_at.desc())
                    .limit(20).all())
    deja_like = Like.query.filter_by(oeuvre_id=id, ip_hash=ip_hash()).first() is not None
    autres_oeuvres = (Oeuvre.publiees()
                      .filter(Oeuvre.artiste_id == oeuvre.artiste_id, Oeuvre.id != oeuvre.id)
                      .order_by(Oeuvre.annee_sortie.desc())
                      .limit(5).all())
    meme_genre = (Oeuvre.publiees()
                  .filter(Oeuvre.genre_musical == oeuvre.genre_musical, Oeuvre.id != oeuvre.id)
                  .order_by(func.random())
                  .limit(4).all())
    desc, desc_lang = oeuvre.description_pour(g.lang)

    return render_template('public/oeuvre_detail.html',
                           oeuvre=oeuvre, commentaires=commentaires, deja_like=deja_like,
                           autres_oeuvres=autres_oeuvres, meme_genre=meme_genre,
                           nb_likes=oeuvre.nb_likes, desc=desc, desc_lang=desc_lang)


# ── RECHERCHE GLOBALE ─────────────────────────────────────────────────────────

def _rechercher(q, limite_a, limite_o, plein_texte=True):
    terme = f'%{escape_like(q)}%'
    champs_a = [Artiste.nom.ilike(terme, escape='\\'), Artiste.nom_reel.ilike(terme, escape='\\')]
    champs_o = [Oeuvre.titre.ilike(terme, escape='\\')]
    if plein_texte:
        champs_a += [Artiste.biographie.ilike(terme, escape='\\'),
                     Artiste.biographie_en.ilike(terme, escape='\\'),
                     Artiste.region_origine.ilike(terme, escape='\\')]
        champs_o += [Oeuvre.genre_musical.ilike(terme, escape='\\'),
                     Oeuvre.description.ilike(terme, escape='\\'),
                     Oeuvre.description_en.ilike(terme, escape='\\'),
                     Oeuvre.distinction.ilike(terme, escape='\\')]
    artistes_res = (Artiste.query.filter_by(statut='approuve').filter(or_(*champs_a))
                    .order_by(Artiste.nb_vues.desc()).limit(limite_a).all())
    oeuvres_res = (Oeuvre.publiees().filter(or_(*champs_o))
                   .order_by(Oeuvre.nb_vues.desc()).limit(limite_o).all())
    return artistes_res, oeuvres_res


@public_bp.route('/recherche')
def recherche():
    q = sanitize(request.args.get('q', ''), 100)
    if not q or len(q) < 2:
        return render_template('public/recherche.html', query='', artistes=[], oeuvres=[], total=0)
    artistes_res, oeuvres_res = _rechercher(q, 8, 12)
    return render_template('public/recherche.html', query=q, artistes=artistes_res,
                           oeuvres=oeuvres_res, total=len(artistes_res) + len(oeuvres_res))


@public_bp.route('/recherche/suggestions')
@rate_limit(120, 60, methods=('GET',))
def recherche_suggestions():
    """API JSON — suggestions instantanées (le client les insère en texte, jamais en HTML)."""
    q = sanitize(request.args.get('q', ''), 60)
    if not q or len(q) < 2:
        return jsonify([])
    artistes_res, oeuvres_res = _rechercher(q, 4, 4, plein_texte=False)
    results = [{
        'type': 'artiste', 'label': a.nom, 'sub': libelle('region', a.region_origine),
        'url': url_for('public_bp.artiste_detail', id=a.id),
    } for a in artistes_res]
    results += [{
        'type': 'oeuvre', 'label': o.titre,
        'sub': f'{o.artiste.nom if o.artiste else ""} · {o.annee_sortie}',
        'url': url_for('public_bp.oeuvre_detail', id=o.id), 'thumb': o.youtube_thumb,
    } for o in oeuvres_res]
    return jsonify(results)


# ── LIKES ─────────────────────────────────────────────────────────────────────

def _toggle_like(**cible):
    h = ip_hash()
    existing = Like.query.filter_by(ip_hash=h, **cible).first()
    if existing:
        db.session.delete(existing)
        liked = False
    else:
        db.session.add(Like(ip_hash=h, **cible))
        liked = True
    try:
        db.session.commit()
    except Exception:          # double clic simultané → contrainte d'unicité
        db.session.rollback()
        liked = True
    return liked, Like.query.filter_by(**cible).count()


@public_bp.route('/like/oeuvre/<int:id>', methods=['POST'])
@rate_limit(60, 60, scope='like')
def like_oeuvre(id):
    Oeuvre.publiees().filter(Oeuvre.id == id).first_or_404()
    liked, nb = _toggle_like(oeuvre_id=id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'liked': liked, 'nb': nb})
    return redirect(url_for('public_bp.oeuvre_detail', id=id))


@public_bp.route('/like/artiste/<int:id>', methods=['POST'])
@rate_limit(60, 60, scope='like')
def like_artiste(id):
    Artiste.query.filter_by(id=id, statut='approuve').first_or_404()
    liked, nb = _toggle_like(artiste_id=id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'liked': liked, 'nb': nb})
    return redirect(url_for('public_bp.artiste_detail', id=id))


# ── COMMENTAIRES ──────────────────────────────────────────────────────────────

def _commenter(retour, **cible):
    if request.form.get('website'):             # pot de miel anti-robots
        flash(_('Commentaire soumis — il sera visible après modération.'), 'success')
        return redirect(retour)
    auteur = sanitize(request.form.get('auteur', ''), 80)
    texte  = sanitize(request.form.get('texte', ''),  1000)
    if len(auteur) < 2:
        flash(_('Veuillez entrer votre prénom.'), 'warning')
        return redirect(retour)
    if len(texte) < 5:
        flash(_('Le commentaire est trop court.'), 'warning')
        return redirect(retour)
    h = ip_hash()
    if Commentaire.query.filter_by(ip_hash=h, **cible).count() >= 3:
        flash(_('Vous avez déjà posté plusieurs commentaires ici.'), 'warning')
        return redirect(retour)
    db.session.add(Commentaire(auteur=auteur, texte=texte, ip_hash=h, approuve=False, **cible))
    db.session.commit()
    flash(_('Commentaire soumis — il sera visible après modération.'), 'success')
    return redirect(retour)


@public_bp.route('/commenter/oeuvre/<int:id>', methods=['POST'])
@rate_limit(5, 600, scope='commentaire')
def commenter_oeuvre(id):
    Oeuvre.publiees().filter(Oeuvre.id == id).first_or_404()
    return _commenter(url_for('public_bp.oeuvre_detail', id=id), oeuvre_id=id)


@public_bp.route('/commenter/artiste/<int:id>', methods=['POST'])
@rate_limit(5, 600, scope='commentaire')
def commenter_artiste(id):
    Artiste.query.filter_by(id=id, statut='approuve').first_or_404()
    return _commenter(url_for('public_bp.artiste_detail', id=id), artiste_id=id)


# ── TOP CHARTS ────────────────────────────────────────────────────────────────

@public_bp.route('/top')
def top_charts():
    top_oeuvres_vues = Oeuvre.publiees().order_by(Oeuvre.nb_vues.desc()).limit(10).all()
    top_oeuvres_likes = (db.session.query(Oeuvre, func.count(Like.id).label('nb'))
                         .join(Like, Like.oeuvre_id == Oeuvre.id)
                         .join(Artiste, Artiste.id == Oeuvre.artiste_id)
                         .filter(Oeuvre.statut == 'approuve', Artiste.statut == 'approuve')
                         .group_by(Oeuvre.id)
                         .order_by(func.count(Like.id).desc())
                         .limit(10).all())
    top_artistes = (Artiste.query.filter_by(statut='approuve')
                    .order_by(Artiste.nb_vues.desc()).limit(8).all())
    return render_template('public/top_charts.html',
                           top_oeuvres_vues=top_oeuvres_vues,
                           top_oeuvres_likes=top_oeuvres_likes,
                           top_artistes=top_artistes)


# ── SIGNALEMENTS ──────────────────────────────────────────────────────────────

@public_bp.route('/signaler/<cible_type>/<int:id>', methods=['GET', 'POST'])
@rate_limit(10, 3600, scope='signalement')
def signaler(cible_type, id):
    if cible_type not in ('artiste', 'oeuvre'):
        abort(404)
    if cible_type == 'artiste':
        cible = Artiste.query.filter_by(id=id, statut='approuve').first_or_404()
        retour_url = url_for('public_bp.artiste_detail', id=id)
    else:
        cible = Oeuvre.publiees().filter(Oeuvre.id == id).first_or_404()
        retour_url = url_for('public_bp.oeuvre_detail', id=id)

    if request.method == 'POST':
        if request.form.get('website'):
            flash(_('Merci ! Votre signalement sera traité rapidement.'), 'success')
            return redirect(retour_url)
        raison      = request.form.get('raison', '').strip()
        description = sanitize(request.form.get('description', ''), 800)
        email       = sanitize(request.form.get('email', ''), 150)
        h           = ip_hash()

        if raison not in [r[0] for r in RAISONS_SIGNALEMENT]:
            flash(_('Veuillez sélectionner une raison.'), 'warning')
            return redirect(request.path)
        if email and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
            email = ''

        filtre = dict(ip_hash=h, **({'artiste_id': id} if cible_type == 'artiste' else {'oeuvre_id': id}))
        if Signalement.query.filter_by(**filtre).count() >= 3:
            flash(_('Vous avez déjà signalé cette entrée plusieurs fois.'), 'warning')
            return redirect(retour_url)

        db.session.add(Signalement(
            cible_type    = cible_type,
            artiste_id    = id if cible_type == 'artiste' else None,
            oeuvre_id     = id if cible_type == 'oeuvre'  else None,
            raison        = raison,
            description   = description or None,
            email_contact = email or None,
            ip_hash       = h,
            statut        = 'nouveau',
        ))
        db.session.commit()
        flash(_('Merci ! Votre signalement sera traité rapidement.'), 'success')
        return redirect(retour_url)

    return render_template('public/signaler.html', cible=cible, cible_type=cible_type,
                           raisons=RAISONS_SIGNALEMENT, retour_url=retour_url)
