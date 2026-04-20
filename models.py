from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ─────────────────────────────────────────────
#  CONSTANTES MÉTIER
# ─────────────────────────────────────────────

REGIONS_CAMEROUN = [
    ('Adamaoua', 'Adamaoua'),
    ('Centre', 'Centre'),
    ('Est', 'Est'),
    ('Extrême-Nord', 'Extrême-Nord'),
    ('Littoral', 'Littoral'),
    ('Nord', 'Nord'),
    ('Nord-Ouest', 'Nord-Ouest'),
    ('Ouest', 'Ouest'),
    ('Sud', 'Sud'),
    ('Sud-Ouest', 'Sud-Ouest'),
    ('Diaspora', 'Diaspora / International'),
]

GENRES_MUSICAUX = [
    ('Makossa', 'Makossa'),
    ('Bikutsi', 'Bikutsi'),
    ('Bend-Skin', 'Bend-Skin'),
    ('Assiko', 'Assiko'),
    ('Mangambeu', 'Mangambeu'),
    ('Ambasse Bey', 'Ambasse Bey'),
    ('Gospel', 'Gospel'),
    ('Afrobeat', 'Afrobeat / Afropop'),
    ('Hip-hop', 'Hip-hop / Rap'),
    ('R&B', 'R&B / Soul'),
    ('Jazz', 'Jazz'),
    ('Rumba', 'Rumba'),
    ('Traditionnel', 'Musique Traditionnelle'),
    ('Autres', 'Autres'),
]

LANGUES = [
    ('Français', 'Français'),
    ('Anglais', 'Anglais'),
    ('Ewondo', 'Ewondo'),
    ('Bassa', 'Bassa'),
    ('Duala', 'Duala'),
    ('Fulfulde', 'Fulfulde'),
    ('Bamileke', 'Bamiléké'),
    ('Pidgin', 'Pidgin English'),
    ('Arabe-Choa', 'Arabe Choa'),
    ('Autres', 'Autres Langues'),
    ('Multilingue', 'Multilingue'),
]

POPULARITES = [
    ('Locale', 'Locale (ville / région)'),
    ('Nationale', 'Nationale (tout le Cameroun)'),
    ('Continentale', 'Continentale (Afrique)'),
    ('Internationale', 'Internationale (Monde)'),
]

STATUTS = [
    ('en_attente', 'En attente'),
    ('approuve', 'Approuvé'),
    ('rejete', 'Rejeté'),
]


# ─────────────────────────────────────────────
#  MODÈLE ARTISTE
# ─────────────────────────────────────────────

class Artiste(db.Model):
    __tablename__ = 'artistes'

    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(150), nullable=False)
    nom_reel = db.Column(db.String(150), nullable=True)          # Vrai nom si pseudonyme
    region_origine = db.Column(db.String(60), nullable=False)
    type_artiste = db.Column(db.String(20), nullable=False)       # Soliste_H / Soliste_F / Groupe
    annee_debut = db.Column(db.Integer, nullable=True)
    annee_fin = db.Column(db.Integer, nullable=True)              # Null si encore actif
    biographie = db.Column(db.Text, nullable=True)
    statut = db.Column(db.String(20), default='en_attente')       # en_attente / approuve / rejete
    soumis_par = db.Column(db.String(100), nullable=True)
    soumis_email = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relation avec les œuvres
    oeuvres = db.relationship('Oeuvre', backref='artiste', lazy='dynamic',
                               cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Artiste {self.nom}>'

    @property
    def encore_actif(self):
        return self.annee_fin is None

    @property
    def oeuvres_approuvees(self):
        return self.oeuvres.filter_by(statut='approuve').all()


# ─────────────────────────────────────────────
#  MODÈLE ŒUVRE (Chanson / Album)
# ─────────────────────────────────────────────

class Oeuvre(db.Model):
    __tablename__ = 'oeuvres'

    id = db.Column(db.Integer, primary_key=True)
    titre = db.Column(db.String(200), nullable=False)
    artiste_id = db.Column(db.Integer, db.ForeignKey('artistes.id'), nullable=False)
    type_oeuvre = db.Column(db.String(20), default='Chanson')    # Chanson / Album / EP / Live
    genre_musical = db.Column(db.String(50), nullable=False)
    langue = db.Column(db.String(50), nullable=False)
    annee_sortie = db.Column(db.Integer, nullable=False)
    popularite = db.Column(db.String(30), nullable=True)
    distinction = db.Column(db.String(200), nullable=True)        # Prix, récompenses
    description = db.Column(db.Text, nullable=True)
    lien_youtube = db.Column(db.String(300), nullable=True)
    statut = db.Column(db.String(20), default='en_attente')       # en_attente / approuve / rejete
    soumis_par = db.Column(db.String(100), nullable=True)
    soumis_email = db.Column(db.String(150), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Oeuvre {self.titre}>'

    @property
    def decennie(self):
        if self.annee_sortie:
            return (self.annee_sortie // 10) * 10
        return None


# ─────────────────────────────────────────────
#  MODÈLE ADMIN
# ─────────────────────────────────────────────

class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Admin {self.username}>'
