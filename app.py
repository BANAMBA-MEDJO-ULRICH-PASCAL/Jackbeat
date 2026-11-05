import logging
import os
from datetime import datetime

import click
from flask import Flask, g, request, session, render_template, url_for, has_request_context
from flask_babel import Babel, lazy_gettext as _l, gettext as _, format_date
from flask_login import LoginManager, current_user
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix

from config import config
from models import _now, db, Admin, libelle
from security import apply_security_headers, csp_nonce, password_problems

login_manager = LoginManager()
csrf = CSRFProtect()
babel = Babel()

log = logging.getLogger('jackbeat')


# ════════════════════════════════════════════════
#  LANGUE (FR / EN)
# ════════════════════════════════════════════════

def select_locale():
    from flask import current_app
    langs = current_app.config['LANGUAGES']
    if not has_request_context():           # CLI, démarrage : langue par défaut
        return current_app.config['BABEL_DEFAULT_LOCALE']
    choix = request.args.get('lang')
    if choix in langs:
        return choix
    if session.get('lang') in langs:
        return session['lang']
    return request.accept_languages.best_match(list(langs)) or current_app.config['BABEL_DEFAULT_LOCALE']


def lang_url(code):
    """URL de la page courante dans une autre langue (?lang=xx)."""
    args = request.args.to_dict(flat=False)
    args['lang'] = [code]
    if request.endpoint and request.endpoint != 'static':
        try:
            return url_for(request.endpoint, **(request.view_args or {}), **args)
        except Exception:
            pass
    from urllib.parse import urlencode
    return request.path + '?' + urlencode(args, doseq=True)


# ════════════════════════════════════════════════
#  FABRIQUE D'APPLICATION
# ════════════════════════════════════════════════

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')
    cfg = config[config_name]
    if hasattr(cfg, 'validate'):
        cfg.validate()

    app = Flask(__name__)
    app.config.from_object(cfg)
    if os.environ.get('SECRET_KEY') and config_name == 'production':
        app.config['SECRET_KEY'] = os.environ['SECRET_KEY']

    if app.config.get('TRUSTED_PROXIES'):
        n = app.config['TRUSTED_PROXIES']
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    logging.basicConfig(level=logging.INFO)

    db.init_app(app)
    csrf.init_app(app)
    babel.init_app(app, locale_selector=select_locale)
    login_manager.init_app(app)
    login_manager.login_view = 'admin_bp.login'
    login_manager.login_message = _l('Veuillez vous connecter.')
    login_manager.login_message_category = 'warning'
    login_manager.session_protection = 'strong'

    from routes.main      import main_bp
    from routes.collecte  import collecte_bp
    from routes.dashboard import dashboard_bp
    from routes.admin     import admin_bp
    from routes.public    import public_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(collecte_bp,  url_prefix='/collecte')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(admin_bp,     url_prefix='/admin')
    app.register_blueprint(public_bp,    url_prefix='/explorer')

    # ── Requête : langue mémorisée ─────────────────
    @app.before_request
    def remember_language():
        choix = request.args.get('lang')
        if choix in app.config['LANGUAGES']:
            session['lang'] = choix
        g.lang = str(select_locale())

    @app.after_request
    def security_headers(response):
        return apply_security_headers(response)

    # ── Variables globales des templates ───────────
    @app.context_processor
    def inject_globals():
        ctx = dict(
            csp_nonce=csp_nonce(),
            lang=g.get('lang', 'fr'),
            languages=app.config['LANGUAGES'],
            lang_url=lang_url,
            current_year=_now().year,
        )
        # Les compteurs de modération ne concernent que l'espace admin
        if request.path.startswith('/admin') and current_user.is_authenticated:
            from models import Artiste, Oeuvre, Commentaire, Signalement
            try:
                ctx.update(
                    pending_artistes_count     = Artiste.query.filter_by(statut="en_attente").count(),
                    pending_oeuvres_count      = Oeuvre.query.filter_by(statut="en_attente").count(),
                    pending_comments_count     = Commentaire.query.filter_by(approuve=False).count(),
                    pending_signalements_count = Signalement.query.filter_by(statut="nouveau").count(),
                )
            except Exception:
                db.session.rollback()
        return ctx

    # Usage dans les templates : {{ valeur|libelle('region') }}
    app.jinja_env.filters['libelle'] = lambda valeur, categorie: libelle(categorie, valeur)
    app.jinja_env.filters['date_courte'] = lambda d: format_date(d, 'short') if d else ''
    app.jinja_env.filters['date_longue'] = lambda d: format_date(d, 'long') if d else ''

    _register_error_handlers(app)
    _register_cli(app)

    with app.app_context():
        from migrations import upgrade_schema
        upgrade_schema(db)
        _create_default_admin(app)

    return app


def _register_error_handlers(app):
    messages = {
        400: (_l('Requête invalide'), _l("La requête n'a pas pu être traitée.")),
        403: (_l('Accès refusé'), _l("Vous n'avez pas l'autorisation d'accéder à cette page.")),
        404: (_l('Page introuvable'), _l("Cette page n'existe pas ou a été déplacée.")),
        405: (_l('Méthode non autorisée'), _l("Cette action n'est pas permise de cette façon.")),
        413: (_l('Requête trop volumineuse'), _l('Les données envoyées dépassent la taille autorisée.')),
        429: (_l('Trop de requêtes'), _l('Vous avez effectué trop de requêtes. Merci de patienter quelques minutes.')),
        500: (_l('Erreur interne'), _l("Une erreur inattendue s'est produite. Nous avons été notifiés.")),
    }

    def render_error(code):
        titre, texte = messages.get(code, messages[500])
        return render_template('errors.html', code=code, titre=titre, texte=texte), code

    for code in messages:
        if code == 500:
            continue
        app.register_error_handler(code, lambda e, c=code: render_error(c))

    @app.errorhandler(500)
    def internal_error(e):
        db.session.rollback()
        return render_error(500)

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        log.warning('CSRF refusé sur %s', request.path)
        titre = _('Session expirée')
        texte = _('Le formulaire a expiré ou est invalide. Rechargez la page et réessayez.')
        return render_template('errors.html', code=400, titre=titre, texte=texte), 400


def _register_cli(app):
    @app.cli.command('admin-create')
    @click.argument('username')
    @click.password_option()
    def admin_create(username, password):
        """Créer un compte administrateur."""
        problems = password_problems(password, username)
        if problems:
            raise click.ClickException(' '.join(problems))
        if Admin.query.filter_by(username=username).first():
            raise click.ClickException('Cet identifiant existe déjà.')
        a = Admin(username=username)
        a.set_password(password)
        db.session.add(a)
        db.session.commit()
        click.echo(f'Admin « {username} » créé.')

    @app.cli.command('admin-reset-password')
    @click.argument('username')
    @click.password_option()
    def admin_reset(username, password):
        """Réinitialiser le mot de passe d'un admin (déconnecte ses sessions)."""
        a = Admin.query.filter_by(username=username).first()
        if not a:
            raise click.ClickException('Admin introuvable.')
        problems = password_problems(password, username)
        if problems:
            raise click.ClickException(' '.join(problems))
        a.set_password(password)
        db.session.commit()
        click.echo('Mot de passe réinitialisé.')

    @app.cli.command('admin-disable-2fa')
    @click.argument('username')
    def admin_disable_2fa(username):
        """Désactiver la double authentification (téléphone perdu)."""
        a = Admin.query.filter_by(username=username).first()
        if not a:
            raise click.ClickException('Admin introuvable.')
        a.totp_enabled, a.totp_secret, a.backup_codes = False, None, None
        a.session_version = (a.session_version or 1) + 1
        db.session.commit()
        click.echo('Double authentification désactivée.')

    @app.cli.command('seed')
    @click.option('--sync', is_flag=True, help='Mettre aussi à jour les fiches de démo existantes.')
    def seed_cmd(sync):
        """Insérer les données de démonstration."""
        from seed_data import seed
        seed(sync=sync)


def _create_default_admin(app):
    if Admin.query.count() > 0:
        return
    password = app.config.get('ADMIN_PASSWORD')
    username = app.config['ADMIN_USERNAME']
    if not password:
        log.error("Aucun admin n'existe et ADMIN_PASSWORD n'est pas défini : "
                  "utilisez `flask admin-create <identifiant>`.")
        return
    if not (app.debug or app.testing):
        problems = password_problems(password, username)
        if problems:
            log.error('ADMIN_PASSWORD trop faible, admin non créé : %s', ' '.join(problems))
            return
    admin = Admin(username=username)
    admin.set_password(password)
    db.session.add(admin)
    db.session.commit()
    log.info('Admin créé : %s', username)


@login_manager.user_loader
def load_user(token):
    try:
        user_id, version = token.split(':', 1)
        admin = db.session.get(Admin, int(user_id))
    except (ValueError, AttributeError):
        return None
    if admin is None or str(admin.session_version or 1) != version:
        return None
    return admin


app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
