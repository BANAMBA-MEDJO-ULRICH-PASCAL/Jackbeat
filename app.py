from flask import Flask
from flask_login import LoginManager
from models import db, Admin
from config import config
import os

login_manager = LoginManager()

def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    db_url = app.config.get('SQLALCHEMY_DATABASE_URI', '')
    if db_url.startswith('postgres://'):
        app.config['SQLALCHEMY_DATABASE_URI'] = db_url.replace('postgres://', 'postgresql://', 1)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'admin_bp.login'
    login_manager.login_message = 'Veuillez vous connecter.'
    login_manager.login_message_category = 'warning'

    from routes.main      import main_bp
    from routes.collecte  import collecte_bp
    from routes.dashboard import dashboard_bp
    from routes.admin     import admin_bp
    from routes.public    import public_bp      # NEW

    app.register_blueprint(main_bp)
    app.register_blueprint(collecte_bp,  url_prefix='/collecte')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(admin_bp,     url_prefix='/admin')
    app.register_blueprint(public_bp,    url_prefix='/explorer')   # NEW

    @app.context_processor
    def inject_globals():
        try:
            from models import Artiste, Oeuvre, Commentaire, Signalement
            return dict(
                pending_artistes_count     = Artiste.query.filter_by(statut="en_attente").count(),
                pending_oeuvres_count      = Oeuvre.query.filter_by(statut="en_attente").count(),
                pending_comments_count     = Commentaire.query.filter_by(approuve=False).count(),
                pending_signalements_count = Signalement.query.filter_by(statut="nouveau").count(),
            )
        except Exception:
            return dict(pending_artistes_count=0, pending_oeuvres_count=0,
                        pending_comments_count=0, pending_signalements_count=0)

    with app.app_context():
        db.create_all()
        _create_default_admin(app)

    return app

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

def _create_default_admin(app):
    if Admin.query.count() == 0:
        admin = Admin(username=app.config['ADMIN_USERNAME'])
        admin.set_password(app.config['ADMIN_PASSWORD'])
        db.session.add(admin)
        db.session.commit()
        print(f"✅ Admin créé : {app.config['ADMIN_USERNAME']}")

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
