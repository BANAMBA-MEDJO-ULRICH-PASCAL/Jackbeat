from flask import Blueprint, render_template
from models import db, Artiste, Oeuvre

main_bp = Blueprint('main_bp', __name__)


@main_bp.route('/')
def index():
    # Statistiques pour la page d'accueil
    total_oeuvres = Oeuvre.query.filter_by(statut='approuve').count()
    total_artistes = Artiste.query.filter_by(statut='approuve').count()
    en_attente = Oeuvre.query.filter_by(statut='en_attente').count() + \
                 Artiste.query.filter_by(statut='en_attente').count()

    # Dernières œuvres approuvées
    dernieres_oeuvres = (Oeuvre.query
                         .filter_by(statut='approuve')
                         .order_by(Oeuvre.created_at.desc())
                         .limit(6).all())

    return render_template('index.html',
                           total_oeuvres=total_oeuvres,
                           total_artistes=total_artistes,
                           en_attente=en_attente,
                           dernieres_oeuvres=dernieres_oeuvres)


@main_bp.route('/notre-histoire')
def notre_histoire():
    return render_template('notre_histoire.html')


@main_bp.route('/ping')
def ping():
    """
    Endpoint léger utilisé par UptimeRobot pour garder
    l'application éveillée sur Render (plan gratuit).
    Répond instantanément sans toucher à la base de données.
    """
    from flask import jsonify
    from datetime import datetime
    return jsonify({
        'status': 'ok',
        'app':    'Jackbeat',
        'time':   datetime.utcnow().isoformat()
    })
