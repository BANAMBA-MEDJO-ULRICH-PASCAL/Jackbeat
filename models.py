from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import re

db = SQLAlchemy()

# ─────────────────────────────────────────────
#  CONSTANTES MÉTIER
# ─────────────────────────────────────────────

REGIONS_CAMEROUN = [
    ('Adamaoua', 'Adamaoua'), ('Centre', 'Centre'), ('Est', 'Est'),
    ('Extrême-Nord', 'Extrême-Nord'), ('Littoral', 'Littoral'), ('Nord', 'Nord'),
    ('Nord-Ouest', 'Nord-Ouest'), ('Ouest', 'Ouest'), ('Sud', 'Sud'),
    ('Sud-Ouest', 'Sud-Ouest'), ('Diaspora', 'Diaspora / International'),
]

GENRES_MUSICAUX = [
    ('Makossa', 'Makossa'), ('Bikutsi', 'Bikutsi'), ('Bend-Skin', 'Bend-Skin'),
    ('Assiko', 'Assiko'), ('Mangambeu', 'Mangambeu'), ('Ambasse Bey', 'Ambasse Bey'),
    ('Gospel', 'Gospel'), ('Afrobeat', 'Afrobeat / Afropop'), ('Hip-hop', 'Hip-hop / Rap'),
    ('R&B', 'R&B / Soul'), ('Jazz', 'Jazz'), ('Rumba', 'Rumba'),
    ('Traditionnel', 'Musique Traditionnelle'), ('Autres', 'Autres'),
]

LANGUES = [
    ('Français', 'Français'), ('Anglais', 'Anglais'), ('Ewondo', 'Ewondo'),
    ('Bassa', 'Bassa'), ('Duala', 'Duala'), ('Fulfulde', 'Fulfulde'),
    ('Bamileke', 'Bamiléké'), ('Pidgin', 'Pidgin English'), ('Arabe-Choa', 'Arabe Choa'),
    ('Autres', 'Autres Langues'), ('Multilingue', 'Multilingue'),
]

POPULARITES = [
    ('Locale', 'Locale (ville / région)'), ('Nationale', 'Nationale (tout le Cameroun)'),
    ('Continentale', 'Continentale (Afrique)'), ('Internationale', 'Internationale (Monde)'),
]

STATUTS = [('en_attente', 'En attente'), ('approuve', 'Approuvé'), ('rejete', 'Rejeté')]


def extract_youtube_id(url):
    """Extrait l'ID YouTube depuis n'importe quel format d'URL."""
    if not url:
        return None
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/shorts/([a-zA-Z0-9_-]{11})',
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


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
    photo_url       = db.Column(db.String(500), nullable=True)   # NEW: photo de profil
    site_web        = db.Column(db.String(300), nullable=True)   # NEW: site officiel
    statut          = db.Column(db.String(20), default='en_attente', index=True)
    nb_vues         = db.Column(db.Integer, default=0)           # NEW: compteur de vues
    soumis_par      = db.Column(db.String(100), nullable=True)
    soumis_email    = db.Column(db.String(150), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    oeuvres  = db.relationship('Oeuvre', backref='artiste', lazy='dynamic',
                                cascade='all, delete-orphan')
    likes    = db.relationship('Like', backref='artiste', lazy='dynamic',
                                cascade='all, delete-orphan')
    comments = db.relationship('Commentaire', backref='artiste', lazy='dynamic',
                                cascade='all, delete-orphan')

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

    def incrementer_vues(self):
        self.nb_vues = (self.nb_vues or 0) + 1
        db.session.commit()


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
    lien_youtube    = db.Column(db.String(300), nullable=True)
    statut          = db.Column(db.String(20), default='en_attente', index=True)
    nb_vues         = db.Column(db.Integer, default=0)            # NEW
    soumis_par      = db.Column(db.String(100), nullable=True)
    soumis_email    = db.Column(db.String(150), nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    likes    = db.relationship('Like', backref='oeuvre', lazy='dynamic',
                                cascade='all, delete-orphan')
    comments = db.relationship('Commentaire', backref='oeuvre', lazy='dynamic',
                                cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Oeuvre {self.titre}>'

    @property
    def decennie(self):
        return (self.annee_sortie // 10) * 10 if self.annee_sortie else None

    @property
    def youtube_id(self):
        return extract_youtube_id(self.lien_youtube)

    @property
    def youtube_embed_url(self):
        yid = self.youtube_id
        if yid:
            # Paramètres sécurisés : pas d'autoplay, pas de suggestions externes
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

    def incrementer_vues(self):
        self.nb_vues = (self.nb_vues or 0) + 1
        db.session.commit()


# ─────────────────────────────────────────────
#  MODÈLE LIKE (artiste OU oeuvre)
# ─────────────────────────────────────────────

class Like(db.Model):
    __tablename__ = 'likes'

    id          = db.Column(db.Integer, primary_key=True)
    artiste_id  = db.Column(db.Integer, db.ForeignKey('artistes.id'), nullable=True)
    oeuvre_id   = db.Column(db.Integer, db.ForeignKey('oeuvres.id'),  nullable=True)
    ip_hash     = db.Column(db.String(64), nullable=False)   # Hash SHA256 de l'IP (anonymisé)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# ─────────────────────────────────────────────
#  MODÈLE SIGNALEMENT (Phase 2)
# ─────────────────────────────────────────────

RAISONS_SIGNALEMENT = [
    ('information_incorrecte', 'Information incorrecte'),
    ('mauvaise_photo',         'Photo / lien YouTube incorrect'),
    ('doublon',                'Doublon — entrée déjà existante'),
    ('contenu_inapproprie',    'Contenu inapproprié'),
    ('annee_incorrecte',       'Année de sortie incorrecte'),
    ('autre',                  'Autre raison'),
]

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
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    artiste = db.relationship('Artiste', backref='signalements', foreign_keys=[artiste_id])
    oeuvre  = db.relationship('Oeuvre',  backref='signalements', foreign_keys=[oeuvre_id])

    @property
    def cible_nom(self):
        if self.artiste: return self.artiste.nom
        if self.oeuvre:  return self.oeuvre.titre
        return '—'

    @property
    def cible_url(self):
        from flask import url_for
        if self.artiste: return url_for('public_bp.artiste_detail', id=self.artiste_id)
        if self.oeuvre:  return url_for('public_bp.oeuvre_detail',  id=self.oeuvre_id)
        return '#'
