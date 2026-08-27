from flask import Blueprint, render_template, redirect, url_for, flash, request
from models import db, Artiste, Oeuvre, REGIONS_CAMEROUN, GENRES_MUSICAUX, LANGUES, POPULARITES
from wtforms import StringField, SelectField, IntegerField, TextAreaField, validators
from flask_wtf import FlaskForm

collecte_bp = Blueprint('collecte_bp', __name__)


# ─────────────────────────────────────────────
#  FORMULAIRES WTForms
# ─────────────────────────────────────────────

class ArtisteForm(FlaskForm):
    nom = StringField('Nom d\'artiste / Pseudonyme *',
                      [validators.DataRequired(message='Ce champ est obligatoire.'),
                       validators.Length(min=2, max=150)])
    nom_reel = StringField('Nom réel (optionnel)', [validators.Optional(), validators.Length(max=150)])
    region_origine = SelectField('Région d\'origine *',
                                 choices=[('', '— Choisir une région —')] + list(REGIONS_CAMEROUN),
                                 validators=[validators.DataRequired()])
    type_artiste = SelectField('Type *',
                               choices=[('', '— Choisir —'),
                                        ('Soliste_H', 'Artiste Solo (Homme)'),
                                        ('Soliste_F', 'Artiste Solo (Femme)'),
                                        ('Groupe', 'Groupe / Band')],
                               validators=[validators.DataRequired()])
    annee_debut = IntegerField('Année de début de carrière',
                               [validators.Optional(),
                                validators.NumberRange(min=1900, max=2030)])
    annee_fin = IntegerField('Année de fin (laisser vide si encore actif)',
                             [validators.Optional(),
                              validators.NumberRange(min=1900, max=2030)])
    biographie = TextAreaField('Biographie / Note (optionnel)',
                               [validators.Optional(), validators.Length(max=1000)])
    soumis_par = StringField('Votre nom (optionnel)', [validators.Optional(), validators.Length(max=100)])
    soumis_email = StringField('Votre email (optionnel)',
                               [validators.Optional(), validators.Email()])


class OeuvreForm(FlaskForm):
    titre = StringField('Titre de l\'œuvre *',
                        [validators.DataRequired(message='Le titre est obligatoire.'),
                         validators.Length(min=1, max=200)])
    artiste_nom = StringField('Nom de l\'artiste *',
                              [validators.DataRequired(), validators.Length(min=2, max=150)])
    type_oeuvre = SelectField('Type d\'œuvre *',
                              choices=[('Chanson', 'Chanson'), ('Album', 'Album'),
                                       ('EP', 'EP'), ('Live', 'Live / Concert')],
                              validators=[validators.DataRequired()])
    genre_musical = SelectField('Genre musical *',
                                choices=[('', '— Choisir un genre —')] + list(GENRES_MUSICAUX),
                                validators=[validators.DataRequired()])
    langue = SelectField('Langue principale *',
                         choices=[('', '— Choisir une langue —')] + list(LANGUES),
                         validators=[validators.DataRequired()])
    annee_sortie = IntegerField('Année de sortie *',
                                [validators.DataRequired(),
                                 validators.NumberRange(min=1960, max=2030,
                                                        message='Année entre 1960 et 2030')])
    popularite = SelectField('Niveau de popularité',
                             choices=[('', '— Optionnel —')] + list(POPULARITES),
                             validators=[validators.Optional()])
    distinction = StringField('Distinction / Prix (optionnel)',
                              [validators.Optional(), validators.Length(max=200)])
    description = TextAreaField('Description (optionnel)',
                                [validators.Optional(), validators.Length(max=500)])
    lien_youtube = StringField('Lien YouTube (optionnel)',
                               [validators.Optional(), validators.Length(max=300)])
    soumis_par = StringField('Votre nom (optionnel)', [validators.Optional(), validators.Length(max=100)])
    soumis_email = StringField('Votre email (optionnel)',
                               [validators.Optional(), validators.Email()])


# ─────────────────────────────────────────────
#  ROUTES
# ─────────────────────────────────────────────

@collecte_bp.route('/')
def index():
    return render_template('collecte/index.html')


@collecte_bp.route('/artiste', methods=['GET', 'POST'])
def soumettre_artiste():
    form = ArtisteForm()
    if form.validate_on_submit():
        artiste = Artiste(
            nom=form.nom.data.strip(),
            nom_reel=form.nom_reel.data.strip() if form.nom_reel.data else None,
            region_origine=form.region_origine.data,
            type_artiste=form.type_artiste.data,
            annee_debut=form.annee_debut.data,
            annee_fin=form.annee_fin.data,
            biographie=form.biographie.data,
            soumis_par=form.soumis_par.data,
            soumis_email=form.soumis_email.data,
            statut='en_attente'
        )
        db.session.add(artiste)
        db.session.commit()
        flash('✅ Artiste soumis avec succès ! Il sera visible après validation.', 'success')
        return redirect(url_for('collecte_bp.merci'))
    return render_template('collecte/artiste.html', form=form)


@collecte_bp.route('/oeuvre', methods=['GET', 'POST'])
def soumettre_oeuvre():
    form = OeuvreForm()
    if form.validate_on_submit():
        # Chercher ou créer l'artiste
        artiste_nom = form.artiste_nom.data.strip()
        artiste = Artiste.query.filter(
            db.func.lower(Artiste.nom) == artiste_nom.lower(),
            Artiste.statut == 'approuve'
        ).first()

        if not artiste:
            # Créer un artiste temporaire en attente
            artiste = Artiste(
                nom=artiste_nom,
                region_origine='Centre',   # Valeur par défaut temporaire
                type_artiste='Soliste_H',
                statut='en_attente',
                soumis_par=form.soumis_par.data
            )
            db.session.add(artiste)
            db.session.flush()

        oeuvre = Oeuvre(
            titre=form.titre.data.strip(),
            artiste_id=artiste.id,
            type_oeuvre=form.type_oeuvre.data,
            genre_musical=form.genre_musical.data,
            langue=form.langue.data,
            annee_sortie=form.annee_sortie.data,
            popularite=form.popularite.data if form.popularite.data else None,
            distinction=form.distinction.data,
            description=form.description.data,
            lien_youtube=form.lien_youtube.data,
            soumis_par=form.soumis_par.data,
            soumis_email=form.soumis_email.data,
            statut='en_attente'
        )
        db.session.add(oeuvre)
        db.session.commit()
        flash('✅ Œuvre soumise avec succès ! Elle sera visible après validation.', 'success')
        return redirect(url_for('collecte_bp.merci'))
    return render_template('collecte/oeuvre.html', form=form)


@collecte_bp.route('/merci')
def merci():
    return render_template('collecte/merci.html')
