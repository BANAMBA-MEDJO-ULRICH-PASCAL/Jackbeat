import json

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_babel import gettext as _

from forms import ArtisteForm, OeuvreForm
from models import db, Artiste, Oeuvre
from security import rate_limit

collecte_bp = Blueprint('collecte_bp', __name__)

# Limite anti-abus : 10 soumissions / heure / IP
LIMITE_SOUMISSIONS = dict(limit=10, period=3600, scope='soumission')


def _snapshot(form, champs):
    """Copie figée de ce que le contributeur a envoyé (visible par l'admin)."""
    return json.dumps({c: getattr(form, c).data for c in champs}, ensure_ascii=False, default=str)


@collecte_bp.route('/')
def index():
    return render_template('collecte/index.html')


@collecte_bp.route('/artiste', methods=['GET', 'POST'])
@rate_limit(**LIMITE_SOUMISSIONS)
def soumettre_artiste():
    form = ArtisteForm()
    if form.validate_on_submit():
        if form.is_bot():
            return redirect(url_for('collecte_bp.merci'))
        champs = ('nom', 'nom_reel', 'region_origine', 'type_artiste',
                  'annee_debut', 'annee_fin', 'biographie')
        artiste = Artiste(
            nom=form.nom.data,
            nom_reel=form.nom_reel.data,
            region_origine=form.region_origine.data,
            type_artiste=form.type_artiste.data,
            annee_debut=form.annee_debut.data,
            annee_fin=form.annee_fin.data,
            biographie=form.biographie.data,
            soumis_par=form.soumis_par.data,
            soumis_email=form.soumis_email.data,
            donnees_soumises=_snapshot(form, champs),
            statut='en_attente',
        )
        db.session.add(artiste)
        db.session.commit()
        flash(_('Artiste soumis avec succès ! Il sera visible après validation.'), 'success')
        return redirect(url_for('collecte_bp.merci'))
    return render_template('collecte/artiste.html', form=form)


@collecte_bp.route('/oeuvre', methods=['GET', 'POST'])
@rate_limit(**LIMITE_SOUMISSIONS)
def soumettre_oeuvre():
    form = OeuvreForm()
    if form.validate_on_submit():
        if form.is_bot():
            return redirect(url_for('collecte_bp.merci'))

        # Chercher l'artiste (insensible à la casse) parmi les fiches non rejetées,
        # en privilégiant une fiche déjà approuvée — évite les doublons en attente.
        artiste_nom = form.artiste_nom.data
        artiste = (Artiste.query
                   .filter(db.func.lower(Artiste.nom) == artiste_nom.lower(),
                           Artiste.statut != 'rejete')
                   .order_by(db.case((Artiste.statut == 'approuve', 0), else_=1), Artiste.id)
                   .first())

        if not artiste:
            region = form.artiste_region.data or None
            type_a = form.artiste_type.data or None
            artiste = Artiste(
                nom=artiste_nom,
                # Valeurs provisoires si le contributeur ne les connaît pas :
                # la fiche est marquée « à compléter » et n'est jamais publiée
                # automatiquement tant que l'admin ne l'a pas vérifiée.
                region_origine=region or 'Centre',
                type_artiste=type_a or 'Soliste_H',
                profil_incomplet=not (region and type_a),
                statut='en_attente',
                soumis_par=form.soumis_par.data,
                soumis_email=form.soumis_email.data,
                donnees_soumises=json.dumps({'nom': artiste_nom, 'region_origine': region,
                                             'type_artiste': type_a}, ensure_ascii=False),
            )
            db.session.add(artiste)
            db.session.flush()

        champs = ('titre', 'artiste_nom', 'type_oeuvre', 'genre_musical', 'langue', 'annee_sortie',
                  'popularite', 'distinction', 'description', 'lien_youtube')
        oeuvre = Oeuvre(
            titre=form.titre.data,
            artiste_id=artiste.id,
            type_oeuvre=form.type_oeuvre.data,
            genre_musical=form.genre_musical.data,
            langue=form.langue.data,
            annee_sortie=form.annee_sortie.data,
            popularite=form.popularite.data or None,
            distinction=form.distinction.data,
            description=form.description.data,
            lien_youtube=form.lien_youtube.data,
            soumis_par=form.soumis_par.data,
            soumis_email=form.soumis_email.data,
            donnees_soumises=_snapshot(form, champs),
            statut='en_attente',
        )
        db.session.add(oeuvre)
        db.session.commit()
        flash(_('Œuvre soumise avec succès ! Elle sera visible après validation.'), 'success')
        return redirect(url_for('collecte_bp.merci'))
    return render_template('collecte/oeuvre.html', form=form)


@collecte_bp.route('/merci')
def merci():
    return render_template('collecte/merci.html')
