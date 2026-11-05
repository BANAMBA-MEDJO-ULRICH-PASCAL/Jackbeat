"""
forms.py — Formulaires WTForms (contributions publiques + édition admin).

Tous les formulaires héritent de FlaskForm : jeton CSRF inclus et validé
côté serveur. Les libellés sont traduits (FR / EN).
"""
from datetime import date

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import (StringField, SelectField, IntegerField, TextAreaField,
                     PasswordField, BooleanField, validators, ValidationError)

from models import (REGIONS_CAMEROUN, GENRES_MUSICAUX, LANGUES, POPULARITES,
                    TYPES_ARTISTE, TYPES_OEUVRE, extract_youtube_id)
from security import is_http_url


def _choices(liste, vide=None):
    base = [(v, l) for v, l in liste]
    return ([('', vide)] + base) if vide is not None else base


def annee_max():
    return date.today().year + 1


class AnneeValide:
    def __init__(self, minimum):
        self.minimum = minimum

    def __call__(self, form, field):
        if field.data is None:
            return
        if not (self.minimum <= field.data <= annee_max()):
            raise ValidationError(_l('Année entre %(a)d et %(b)d.', a=self.minimum, b=annee_max()))


def lien_youtube_valide(form, field):
    if field.data and not extract_youtube_id(field.data):
        raise ValidationError(_l('Lien YouTube invalide (ex : https://www.youtube.com/watch?v=…).'))


def url_https_valide(form, field):
    if field.data and not is_http_url(field.data, https_only=True):
        raise ValidationError(_l('Adresse invalide : elle doit commencer par https://'))


def url_web_valide(form, field):
    if field.data and not is_http_url(field.data):
        raise ValidationError(_l('Adresse invalide : elle doit commencer par http:// ou https://'))


def strip(value):
    return value.strip() if isinstance(value, str) else value


def none_if_empty(value):
    value = strip(value)
    return value or None


class HoneypotMixin:
    # Champ invisible pour les humains : les robots le remplissent.
    website = StringField('Website', filters=[strip])

    def is_bot(self):
        return bool(self.website.data)


class FinApresDebut:
    def __call__(self, form, field):
        debut = form.annee_debut.data
        if field.data is not None and debut is not None and field.data < debut:
            raise ValidationError(_l("L'année de fin doit être postérieure à l'année de début."))


# ════════════════════════════════════════════════
#  CONTRIBUTIONS PUBLIQUES
# ════════════════════════════════════════════════

class ArtisteForm(HoneypotMixin, FlaskForm):
    nom = StringField(_l("Nom d'artiste / Pseudonyme *"),
                      [validators.DataRequired(message=_l('Ce champ est obligatoire.')),
                       validators.Length(min=2, max=150)], filters=[strip])
    nom_reel = StringField(_l('Nom réel (optionnel)'),
                           [validators.Optional(), validators.Length(max=150)], filters=[none_if_empty])
    region_origine = SelectField(_l("Région d'origine *"),
                                 choices=_choices(REGIONS_CAMEROUN, _l('— Choisir une région —')),
                                 validators=[validators.DataRequired(message=_l('Ce champ est obligatoire.'))])
    type_artiste = SelectField(_l('Type *'), choices=_choices(TYPES_ARTISTE, _l('— Choisir —')),
                               validators=[validators.DataRequired(message=_l('Ce champ est obligatoire.'))])
    annee_debut = IntegerField(_l('Année de début de carrière'),
                               [validators.Optional(), AnneeValide(1900)])
    annee_fin = IntegerField(_l('Année de fin (laisser vide si encore actif)'),
                             [validators.Optional(), AnneeValide(1900), FinApresDebut()])
    biographie = TextAreaField(_l('Biographie / Note (optionnel)'),
                               [validators.Optional(), validators.Length(max=2000)], filters=[none_if_empty])
    soumis_par = StringField(_l('Votre nom (optionnel)'),
                             [validators.Optional(), validators.Length(max=100)], filters=[none_if_empty])
    soumis_email = StringField(_l('Votre email (optionnel)'),
                               [validators.Optional(), validators.Email(message=_l('Adresse email invalide.')),
                                validators.Length(max=150)], filters=[none_if_empty])


class OeuvreForm(HoneypotMixin, FlaskForm):
    titre = StringField(_l("Titre de l'œuvre *"),
                        [validators.DataRequired(message=_l('Le titre est obligatoire.')),
                         validators.Length(min=1, max=200)], filters=[strip])
    artiste_nom = StringField(_l("Nom de l'artiste *"),
                              [validators.DataRequired(message=_l('Ce champ est obligatoire.')),
                               validators.Length(min=2, max=150)], filters=[strip])
    artiste_region = SelectField(_l("Région d'origine de l'artiste"),
                                 choices=_choices(REGIONS_CAMEROUN, _l('— Je ne sais pas —')),
                                 validators=[validators.Optional()])
    artiste_type = SelectField(_l("Type d'artiste"),
                               choices=_choices(TYPES_ARTISTE, _l('— Je ne sais pas —')),
                               validators=[validators.Optional()])
    type_oeuvre = SelectField(_l("Type d'œuvre *"), choices=_choices(TYPES_OEUVRE),
                              validators=[validators.DataRequired()])
    genre_musical = SelectField(_l('Genre musical *'),
                                choices=_choices(GENRES_MUSICAUX, _l('— Choisir un genre —')),
                                validators=[validators.DataRequired(message=_l('Ce champ est obligatoire.'))])
    langue = SelectField(_l('Langue principale *'),
                         choices=_choices(LANGUES, _l('— Choisir une langue —')),
                         validators=[validators.DataRequired(message=_l('Ce champ est obligatoire.'))])
    annee_sortie = IntegerField(_l('Année de sortie *'),
                                [validators.DataRequired(message=_l('Ce champ est obligatoire.')),
                                 AnneeValide(1960)])
    popularite = SelectField(_l('Niveau de popularité'),
                             choices=_choices(POPULARITES, _l('— Optionnel —')),
                             validators=[validators.Optional()], filters=[none_if_empty])
    distinction = StringField(_l('Distinction / Prix (optionnel)'),
                              [validators.Optional(), validators.Length(max=200)], filters=[none_if_empty])
    description = TextAreaField(_l('Description (optionnel)'),
                                [validators.Optional(), validators.Length(max=1000)], filters=[none_if_empty])
    lien_youtube = StringField(_l('Lien YouTube (optionnel)'),
                               [validators.Optional(), validators.Length(max=300), lien_youtube_valide],
                               filters=[none_if_empty])
    soumis_par = StringField(_l('Votre nom (optionnel)'),
                             [validators.Optional(), validators.Length(max=100)], filters=[none_if_empty])
    soumis_email = StringField(_l('Votre email (optionnel)'),
                               [validators.Optional(), validators.Email(message=_l('Adresse email invalide.')),
                                validators.Length(max=150)], filters=[none_if_empty])


# ════════════════════════════════════════════════
#  ÉDITION ADMIN
# ════════════════════════════════════════════════

class AdminArtisteForm(FlaskForm):
    nom = StringField(_l("Nom d'artiste *"),
                      [validators.DataRequired(), validators.Length(min=1, max=150)], filters=[strip])
    nom_reel = StringField(_l('Nom réel'), [validators.Optional(), validators.Length(max=150)],
                           filters=[none_if_empty])
    region_origine = SelectField(_l("Région d'origine *"), choices=_choices(REGIONS_CAMEROUN),
                                 validators=[validators.DataRequired()])
    type_artiste = SelectField(_l('Type *'), choices=_choices(TYPES_ARTISTE),
                               validators=[validators.DataRequired()])
    annee_debut = IntegerField(_l('Année de début'), [validators.Optional(), AnneeValide(1900)])
    annee_fin = IntegerField(_l('Année de fin'), [validators.Optional(), AnneeValide(1900), FinApresDebut()])
    biographie = TextAreaField(_l('Biographie (français)'), [validators.Optional(), validators.Length(max=5000)],
                               filters=[none_if_empty])
    biographie_en = TextAreaField(_l('Biographie (anglais)'), [validators.Optional(), validators.Length(max=5000)],
                                  filters=[none_if_empty])
    photo_url = StringField(_l('Photo (URL https)'), [validators.Optional(), validators.Length(max=500),
                                                      url_https_valide], filters=[none_if_empty])
    site_web = StringField(_l('Site officiel'), [validators.Optional(), validators.Length(max=300),
                                                 url_web_valide], filters=[none_if_empty])


class AdminOeuvreForm(FlaskForm):
    titre = StringField(_l('Titre *'), [validators.DataRequired(), validators.Length(min=1, max=200)],
                        filters=[strip])
    artiste_id = SelectField(_l('Artiste *'), coerce=int, validators=[validators.DataRequired()])
    type_oeuvre = SelectField(_l('Type'), choices=_choices(TYPES_OEUVRE), validators=[validators.DataRequired()])
    genre_musical = SelectField(_l('Genre musical *'), choices=_choices(GENRES_MUSICAUX),
                                validators=[validators.DataRequired()])
    langue = SelectField(_l('Langue *'), choices=_choices(LANGUES), validators=[validators.DataRequired()])
    annee_sortie = IntegerField(_l('Année de sortie *'), [validators.DataRequired(), AnneeValide(1900)])
    popularite = SelectField(_l('Popularité'), choices=_choices(POPULARITES, _l('— Non renseignée —')),
                             validators=[validators.Optional()], filters=[none_if_empty])
    distinction = StringField(_l('Distinction / Prix'), [validators.Optional(), validators.Length(max=200)],
                              filters=[none_if_empty])
    description = TextAreaField(_l('Description (français)'), [validators.Optional(), validators.Length(max=3000)],
                                filters=[none_if_empty])
    description_en = TextAreaField(_l('Description (anglais)'), [validators.Optional(), validators.Length(max=3000)],
                                   filters=[none_if_empty])
    lien_youtube = StringField(_l('Lien YouTube'), [validators.Optional(), validators.Length(max=300),
                                                    lien_youtube_valide], filters=[none_if_empty])


# ════════════════════════════════════════════════
#  AUTHENTIFICATION & SÉCURITÉ DU COMPTE
# ════════════════════════════════════════════════

class LoginForm(FlaskForm):
    username = StringField(_l('Identifiant'), [validators.DataRequired(), validators.Length(max=80)],
                           filters=[strip])
    password = PasswordField(_l('Mot de passe'), [validators.DataRequired(), validators.Length(max=256)])


class TotpForm(FlaskForm):
    code = StringField(_l('Code de vérification'), [validators.DataRequired(), validators.Length(max=20)],
                       filters=[strip])


class PasswordChangeForm(FlaskForm):
    current_password = PasswordField(_l('Mot de passe actuel'), [validators.DataRequired()])
    new_password = PasswordField(_l('Nouveau mot de passe'), [validators.DataRequired(),
                                                             validators.Length(max=256)])
    confirm = PasswordField(_l('Confirmer le nouveau mot de passe'),
                            [validators.DataRequired(),
                             validators.EqualTo('new_password', message=_l('Les mots de passe ne correspondent pas.'))])


class TotpSetupForm(FlaskForm):
    code = StringField(_l("Code affiché dans l'application"), [validators.DataRequired(),
                                                               validators.Length(max=10)], filters=[strip])


class TotpDisableForm(FlaskForm):
    password = PasswordField(_l('Mot de passe actuel'), [validators.DataRequired()])
    confirm = BooleanField(_l('Je comprends que mon compte sera moins protégé'),
                           [validators.DataRequired()])
