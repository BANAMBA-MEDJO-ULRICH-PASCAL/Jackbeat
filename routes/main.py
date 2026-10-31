from datetime import datetime

from flask import Blueprint, render_template, jsonify, Response, url_for

from models import _now, Artiste, Oeuvre

main_bp = Blueprint('main_bp', __name__)


@main_bp.route('/')
def index():
    total_oeuvres = Oeuvre.publiees().count()
    total_artistes = Artiste.query.filter_by(statut='approuve').count()
    dernieres_oeuvres = (Oeuvre.publiees()
                         .order_by(Oeuvre.created_at.desc())
                         .limit(6).all())
    return render_template('index.html',
                           total_oeuvres=total_oeuvres,
                           total_artistes=total_artistes,
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
    return jsonify({'status': 'ok', 'app': 'Jackbeat',
                    'time': _now().isoformat()})


@main_bp.route('/robots.txt')
def robots():
    lignes = ['User-agent: *', 'Disallow: /admin/', 'Disallow: /explorer/like/',
              'Disallow: /explorer/commenter/', 'Disallow: /explorer/signaler/',
              f"Sitemap: {url_for('main_bp.sitemap', _external=True)}"]
    return Response('\n'.join(lignes) + '\n', mimetype='text/plain')


@main_bp.route('/sitemap.xml')
def sitemap():
    urls = [url_for('main_bp.index', _external=True),
            url_for('main_bp.notre_histoire', _external=True),
            url_for('public_bp.artistes', _external=True),
            url_for('public_bp.top_charts', _external=True),
            url_for('dashboard_bp.index', _external=True),
            url_for('dashboard_bp.carte', _external=True),
            url_for('dashboard_bp.chronologie', _external=True)]
    urls += [url_for('public_bp.artiste_detail', id=a.id, _external=True)
             for a in Artiste.query.filter_by(statut='approuve').with_entities(Artiste.id)]
    urls += [url_for('public_bp.oeuvre_detail', id=o.id, _external=True)
             for o in Oeuvre.publiees().with_entities(Oeuvre.id)]
    body = ['<?xml version="1.0" encoding="UTF-8"?>',
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
            'xmlns:xhtml="http://www.w3.org/1999/xhtml">']
    for u in urls:
        sep = '&amp;' if '?' in u else '?'
        body.append(f'<url><loc>{u}</loc>'
                    f'<xhtml:link rel="alternate" hreflang="fr" href="{u}{sep}lang=fr"/>'
                    f'<xhtml:link rel="alternate" hreflang="en" href="{u}{sep}lang=en"/></url>')
    body.append('</urlset>')
    return Response('\n'.join(body), mimetype='application/xml')
