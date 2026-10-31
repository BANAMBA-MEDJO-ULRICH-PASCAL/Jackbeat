import json
import re
from datetime import datetime, timezone

from flask_babel import lazy_gettext as _l
from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

# ─────────────────────────────────────────────
#  CONSTANTES MÉTIER
#  Les valeurs (1er élément) sont stockées en base et ne changent jamais ;
#  les libellés (2e élément) sont traduits à l'affichage (FR / EN).
# ─────────────────────────────────────────────

REGIONS_CAMEROUN = [
    ('Adamaoua', _l('Adamaoua')), ('Centre', _l('Centre')), ('Est', _l('Est')),
    ('Extrême-Nord', _l('Extrême-Nord')), ('Littoral', _l('Littoral')), ('Nord', _l('Nord')),
    ('Nord-Ouest', _l('Nord-Ouest')), ('Ouest', _l('Ouest')), ('Sud', _l('Sud')),
    ('Sud-Ouest', _l('Sud-Ouest')), ('Diaspora', _l('Diaspora / International')),
]

GENRES_MUSICAUX = [
    ('Makossa', 'Makossa'), ('Bikutsi', 'Bikutsi'), ('Bend-Skin', 'Bend-Skin'),
    ('Assiko', 'Assiko'), ('Mangambeu', 'Mangambeu'), ('Ambasse Bey', 'Ambasse Bey'),
    ('Gospel', 'Gospel'), ('Afrobeat', 'Afrobeat / Afropop'), ('Hip-hop', 'Hip-hop / Rap'),
    ('R&B', 'R&B / Soul'), ('Jazz', 'Jazz'), ('Rumba', 'Rumba'),
    ('Traditionnel', _l('Musique Traditionnelle')), ('Autres', _l('Autres')),
]

LANGUES = [
    ('Français', _l('Français')), ('Anglais', _l('Anglais')), ('Ewondo', 'Ewondo'),
    ('Bassa', 'Bassa'), ('Duala', 'Duala'), ('Fulfulde', 'Fulfulde'),
    ('Bamileke', _l('Bamiléké')), ('Pidgin', _l('Pidgin English')), ('Arabe-Choa', _l('Arabe Choa')),
    ('Autres', _l('Autres Langues')), ('Multilingue', _l('Multilingue')),
]

POPULARITES = [
    ('Locale', _l('Locale (ville / région)')), ('Nationale', _l('Nationale (tout le Cameroun)')),
    ('Continentale', _l('Continentale (Afrique)')), ('Internationale', _l('Internationale (Monde)')),
]

# Libellés courts (graphiques, badges)
POPULARITES_COURTES = [
    ('Locale', _l('Locale')), ('Nationale', _l('Nationale')),
    ('Continentale', _l('Continentale')), ('Internationale', _l('Internationale')),
]

TYPES_ARTISTE = [
    ('Soliste_H', _l('Artiste Solo (Homme)')),
    ('Soliste_F', _l('Artiste Solo (Femme)')),
    ('Groupe', _l('Groupe / Band')),
]

TYPES_OEUVRE = [
    ('Chanson', _l('Chanson')), ('Album', _l('Album')),
    ('EP', _l('EP')), ('Live', _l('Live / Concert')),
]

STATUTS = [('en_attente', _l('En attente')), ('approuve', _l('Approuvé')), ('rejete', _l('Rejeté'))]

RAISONS_SIGNALEMENT = [
    ('information_incorrecte', _l('Information incorrecte')),
    ('mauvaise_photo',         _l('Photo / lien YouTube incorrect')),
    ('doublon',                _l('Doublon — entrée déjà existante')),
    ('contenu_inapproprie',    _l('Contenu inapproprié')),
    ('annee_incorrecte',       _l('Année de sortie incorrecte')),
    ('autre',                  _l('Autre raison')),
]

STATUTS_SIGNALEMENT = [
    ('nouveau', _l('Nouveau')), ('en_cours', _l('En cours')),
    ('resolu', _l('Résolu')), ('rejete', _l('Rejeté')),
]

# Table de correspondance utilisée par le filtre de template |libelle
LIBELLES = {
    'region':      dict(REGIONS_CAMEROUN),
    'genre':       dict(GENRES_MUSICAUX),
    'langue':      dict(LANGUES),
    'popularite':  dict(POPULARITES_COURTES),
    'type_artiste': dict(TYPES_ARTISTE),
    'type_oeuvre': dict(TYPES_OEUVRE),
    'statut':      dict(STATUTS),
    'raison':      dict(RAISONS_SIGNALEMENT),
    'statut_signalement': dict(STATUTS_SIGNALEMENT),
}


def libelle(categorie, valeur):
    """Libellé traduit d'une valeur stockée (ex : libelle('region', 'Sud-Ouest'))."""
    if valeur is None:
        return ''
    return str(LIBELLES.get(categorie, {}).get(valeur, valeur))


YOUTUBE_ID_RE = re.compile(
    r'^(?:https?://)?(?:www\.|m\.|music\.)?'
    r'(?:youtube\.com/(?:watch\?(?:.*&)?v=|embed/|shorts/|live/)|youtu\.be/)'
    r'([a-zA-Z0-9_-]{11})(?:[?&#].*)?$'
)


def extract_youtube_id(url):
    """Extrait l'ID YouTube d'une URL YouTube (et uniquement YouTube)."""
    if not url:
        return None
    m = YOUTUBE_ID_RE.match(url.strip())
    return m.group(1) if m else None


def _now():
    """Heure UTC « naïve » (cohérente avec les colonnes DateTime existantes)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ─────────────────────────────────────────────
#  MODÈLE ARTISTE
# ─────────────────────────────────────────────

class Artiste(db.Model):
    __tablename__ = 'artistes'

    id              = db.Column(db.Integer, primary_key=True)
    nom             = db.Column(db.String(150), nullable=False, index=True)
    nom_reel        = db.Column(db.String(150), nullable=True)
    region_origine  = db.Column(db.String(60),  nullable=False, index=True)
    type_artiste    = db.Column(db.String(20),  nullable=False)
    annee_debut     = db.Column(db.Integer, nullable=True)
    annee_fin       = db.Column(db.Integer, nullable=True)
    biographie      = db.Column(db.Text, nullable=True)
    biographie_en   = db.Column(db.Text, nullable=True)          # version anglaise
    photo_url       = db.Column(db.String(500), nullable=True)
    site_web        = db.Column(db.String(300), nullable=True)
    statut          = db.Column(db.String(20), default='en_attente', index=True)
    # True quand l'artiste a été créé automatiquement depuis une soumission
    # d'œuvre sans région / type fournis : l'admin doit compléter la fiche.
    profil_incomplet = db.Column(db.Boolean, default=False, nullable=False)
    nb_vues         = db.Column(db.Integer, default=0)
    soumis_par      = db.Column(db.String(100), nullable=True)
    soumis_email    = db.Column(db.String(150), nullable=True)
    donnees_soumises = db.Column(db.Text, nullable=True)         # JSON : la contribution d'origine
    created_at      = db.Column(db.DateTime, default=_now)
    updated_at      = db.Column(db.DateTime, nullable=True)

    oeuvres  = db.relationship('Oeuvre', backref='artiste', lazy='dynamic',
                                cascade='all, delete-orphan')
    likes    = db.relationship('Like', backref='artiste', lazy='dynamic',
                                cascade='all, delete-orphan')
    comments = db.relationship('Commentaire', backref='artiste', lazy='dynamic',
                                cascade='all, delete-orphan')

    CHAMPS_EDITABLES = ('nom', 'nom_reel', 'region_origine', 'type_artiste', 'annee_debut',
                        'annee_fin', 'biographie', 'biographie_en', 'photo_url', 'site_web')

    def __repr__(self):
        return f'<Artiste {self.nom}>'

    @property
    def encore_actif(self):
        return self.annee_fin is None

    @property
    def oeuvres_approuvees(self):
        return self.oeuvres.filter_by(statut='approuve').order_by(Oeuvre.annee_sortie.desc()).all()

    @property
    def nb_likes(self):
        return self.likes.count()

    @property
    def nb_commentaires(self):
        return self.comments.filter_by(approuve=True).count()

    @property
    def soumission_originale(self):
        return json.loads(self.donnees_soumises) if self.donnees_soumises else None

    def biographie_pour(self, langue):
        """(texte, langue_du_texte) — l'anglais si demandé et disponible, sinon le français."""
        if langue == 'en' and self.biographie_en:
            return self.biographie_en, 'en'
        if self.biographie:
            return self.biographie, 'fr'
        if self.biographie_en:
            return self.biographie_en, 'en'
        return None, None

    def snapshot(self):
        return {c: getattr(self, c) for c in self.CHAMPS_EDITABLES}


# ─────────────────────────────────────────────
#  MODÈLE ŒUVRE
# ─────────────────────────────────────────────

class Oeuvre(db.Model):
    __tablename__ = 'oeuvres'

    id              = db.Column(db.Integer, primary_key=True)
    titre           = db.Column(db.String(200), nullable=False, index=True)
    artiste_id      = db.Column(db.Integer, db.ForeignKey('artistes.id'), nullable=False)
    type_oeuvre     = db.Column(db.String(20), default='Chanson')
    genre_musical   = db.Column(db.String(50), nullable=False, index=True)
    langue          = db.Column(db.String(50), nullable=False)
    annee_sortie    = db.Column(db.Integer, nullable=False, index=True)
    popularite      = db.Column(db.String(30), nullable=True)
    distinction     = db.Column(db.String(200), nullable=True)
    description     = db.Column(db.Text, nullable=True)
    description_en  = db.Column(db.Text, nullable=True)          # version anglaise
    lien_youtube    = db.Column(db.String(300), nullable=True)
    statut          = db.Column(db.String(20), default='en_attente', index=True)
    nb_vues         = db.Column(db.Integer, default=0)
    soumis_par      = db.Column(db.String(100), nullable=True)
    soumis_email    = db.Column(db.String(150), nullable=True)
    donnees_soumises = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=_now)
    updated_at      = db.Column(db.DateTime, nullable=True)

    likes    = db.relationship('Like', backref='oeuvre', lazy='dynamic',
                                cascade='all, delete-orphan')
    comments = db.relationship('Commentaire', backref='oeuvre', lazy='dynamic',
                                cascade='all, delete-orphan')

    CHAMPS_EDITABLES = ('titre', 'artiste_id', 'type_oeuvre', 'genre_musical', 'langue',
                        'annee_sortie', 'popularite', 'distinction', 'description',
                        'description_en', 'lien_youtube')

    def __repr__(self):
        return f'<Oeuvre {self.titre}>'

    @classmethod
    def publiees(cls):
        """Œuvres visibles publiquement : approuvées ET dont l'artiste est approuvé."""
        return (cls.query.join(Artiste, cls.artiste_id == Artiste.id)
                .filter(cls.statut == 'approuve', Artiste.statut == 'approuve'))

    @property
    def est_publiee(self):
        return self.statut == 'approuve' and self.artiste is not None and self.artiste.statut == 'approuve'

    @property
    def decennie(self):
        return (self.annee_sortie // 10) * 10 if self.annee_sortie else None

    @property
    def youtube_id(self):
        return extract_youtube_id(self.lien_youtube)

    @property
    def youtube_url(self):
        yid = self.youtube_id
        return f'https://www.youtube.com/watch?v={yid}' if yid else None

    @property
    def youtube_embed_url(self):
        yid = self.youtube_id
        if yid:
            return f'https://www.youtube-nocookie.com/embed/{yid}?rel=0&modestbranding=1'
        return None

    @property
    def youtube_thumb(self):
        yid = self.youtube_id
        return f'https://img.youtube.com/vi/{yid}/mqdefault.jpg' if yid else None

    @property
    def nb_likes(self):
        return self.likes.count()

    @property
    def nb_commentaires(self):
        return self.comments.filter_by(approuve=True).count()

    @property
    def soumission_originale(self):
        return json.loads(self.donnees_soumises) if self.donnees_soumises else None

    def description_pour(self, langue):
        if langue == 'en' and self.description_en:
            return self.description_en, 'en'
        if self.description:
            return self.description, 'fr'
        if self.description_en:
            return self.description_en, 'en'
        return None, None

    def snapshot(self):
        return {c: getattr(self, c) for c in self.CHAMPS_EDITABLES}


# ─────────────────────────────────────────────
#  MODÈLE LIKE (artiste OU oeuvre)
# ─────────────────────────────────────────────

class Like(db.Model):
    __tablename__ = 'likes'

    id          = db.Column(db.Integer, primary_key=True)
    artiste_id  = db.Column(db.Integer, db.ForeignKey('artistes.id'), nullable=True)
    oeuvre_id   = db.Column(db.Integer, db.ForeignKey('oeuvres.id'),  nullable=True)
    ip_hash     = db.Column(db.String(64), nullable=False)   # HMAC de l'IP (anonymisé)
    created_at  = db.Column(db.DateTime, default=_now)

    __table_args__ = (
        db.UniqueConstraint('oeuvre_id',  'ip_hash', name='uq_like_oeuvre_ip'),
        db.UniqueConstraint('artiste_id', 'ip_hash', name='uq_like_artiste_ip'),
    )


# ─────────────────────────────────────────────
#  MODÈLE COMMENTAIRE
# ─────────────────────────────────────────────

class Commentaire(db.Model):
    __tablename__ = 'commentaires'

    id          = db.Column(db.Integer, primary_key=True)
    artiste_id  = db.Column(db.Integer, db.ForeignKey('artistes.id'), nullable=True)
    oeuvre_id   = db.Column(db.Integer, db.ForeignKey('oeuvres.id'),  nullable=True)
    auteur      = db.Column(db.String(80),  nullable=False)
    texte       = db.Column(db.Text,        nullable=False)
    approuve    = db.Column(db.Boolean,     default=False)   # Modéré avant publication
    ip_hash     = db.Column(db.String(64),  nullable=True)
    created_at  = db.Column(db.DateTime, default=_now)

    def __repr__(self):
        return f'<Commentaire by {self.auteur}>'


# ─────────────────────────────────────────────
#  MODÈLE ADMIN
# ─────────────────────────────────────────────

class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'

    id            = db.Column(db.Integer, primary_key=True)
    username      = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at    = db.Column(db.DateTime, default=_now)
    # Sécurité du compte
    password_changed_at = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    totp_secret   = db.Column(db.String(64), nullable=True)
    totp_enabled  = db.Column(db.Boolean, default=False, nullable=False)
    totp_last_step = db.Column(db.Integer, nullable=True)    # anti-rejeu
    backup_codes  = db.Column(db.Text, nullable=True)       # JSON : hashes des codes de secours
    # Incrémenté à chaque changement de mot de passe / 2FA : invalide les sessions existantes
    session_version = db.Column(db.Integer, default=1, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method='scrypt')
        self.password_changed_at = _now()
        self.session_version = (self.session_version or 1) + 1

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_id(self):
        # Le jeton de session lie l'ID à la version : changer de mot de passe
        # déconnecte immédiatement toutes les autres sessions.
        return f'{self.id}:{self.session_version or 1}'


# ─────────────────────────────────────────────
#  SÉCURITÉ : TENTATIVES DE CONNEXION & JOURNAL D'AUDIT
# ─────────────────────────────────────────────

class LoginAttempt(db.Model):
    __tablename__ = 'login_attempts'

    id         = db.Column(db.Integer, primary_key=True)
    username   = db.Column(db.String(80), nullable=True, index=True)
    ip_hash    = db.Column(db.String(64), nullable=False, index=True)
    success    = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=_now, index=True)


class AuditLog(db.Model):
    """Trace de chaque action admin : qui, quoi, quand, et le détail des modifications."""
    __tablename__ = 'audit_log'

    id          = db.Column(db.Integer, primary_key=True)
    admin_id    = db.Column(db.Integer, nullable=True)
    admin_username = db.Column(db.String(80), nullable=True)
    action      = db.Column(db.String(40), nullable=False, index=True)
    cible_type  = db.Column(db.String(20), nullable=True, index=True)
    cible_id    = db.Column(db.Integer, nullable=True, index=True)
    cible_nom   = db.Column(db.String(200), nullable=True)
    details     = db.Column(db.Text, nullable=True)      # JSON {champ: [avant, après]}
    ip_hash     = db.Column(db.String(64), nullable=True)
    created_at  = db.Column(db.DateTime, default=_now, index=True)

    @property
    def details_dict(self):
        try:
            return json.loads(self.details) if self.details else {}
        except ValueError:
            return {}


# ─────────────────────────────────────────────
#  MODÈLE SIGNALEMENT
# ─────────────────────────────────────────────

class Signalement(db.Model):
    __tablename__ = 'signalements'

    id            = db.Column(db.Integer, primary_key=True)
    cible_type    = db.Column(db.String(20), nullable=False)   # 'artiste' | 'oeuvre'
    artiste_id    = db.Column(db.Integer, db.ForeignKey('artistes.id', ondelete='CASCADE'), nullable=True)
    oeuvre_id     = db.Column(db.Integer, db.ForeignKey('oeuvres.id',  ondelete='CASCADE'), nullable=True)
    raison        = db.Column(db.String(60), nullable=False)
    description   = db.Column(db.Text, nullable=True)
    email_contact = db.Column(db.String(150), nullable=True)
    ip_hash       = db.Column(db.String(64), nullable=True)
    statut        = db.Column(db.String(20), default='nouveau')  # nouveau|en_cours|resolu|rejete
    note_admin    = db.Column(db.Text, nullable=True)
    created_at    = db.Column(db.DateTime, default=_now)

    artiste = db.relationship('Artiste', backref=db.backref('signalements', cascade='all, delete-orphan'),
                              foreign_keys=[artiste_id])
    oeuvre  = db.relationship('Oeuvre',  backref=db.backref('signalements', cascade='all, delete-orphan'),
                              foreign_keys=[oeuvre_id])

    @property
    def cible_nom(self):
        if self.artiste: return self.artiste.nom
        if self.oeuvre:  return self.oeuvre.titre
        return '—'

    @property
    def cible_url(self):
        from flask import url_for
        if self.artiste: return url_for('admin_bp.artiste_detail', id=self.artiste_id)
        if self.oeuvre:  return url_for('admin_bp.oeuvre_detail',  id=self.oeuvre_id)
        return '#'
