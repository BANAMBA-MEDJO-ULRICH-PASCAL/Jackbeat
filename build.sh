set -o errexit

echo "📦 Mise à jour de pip..."
pip install --upgrade pip --quiet

echo "📦 Installation des dépendances..."
pip install -r requirements.txt --quiet

echo "🗄️  Migration + initialisation base de données..."
python -c "
from app import create_app
from models import db
app = create_app('production')
with app.app_context():
    # Créer les nouvelles tables
    db.create_all()
    
    # Migration douce — ajouter colonnes si elles n'existent pas
    conn = db.engine.raw_connection()
    cur  = conn.cursor()
    migrations = [
        ('artistes', 'photo_url', 'VARCHAR(500)'),
        ('artistes', 'site_web',  'VARCHAR(300)'),
        ('artistes', 'nb_vues',   'INTEGER DEFAULT 0'),
        ('oeuvres',  'nb_vues',   'INTEGER DEFAULT 0'),
    ]
    for table, col, typ in migrations:
        try:
            cur.execute(f'ALTER TABLE {table} ADD COLUMN {col} {typ}')
        except Exception:
            pass  # Colonne déjà présente
    conn.commit()
    conn.close()
    print('✅ Base de données migrée')
"

echo "🌱 Données de démonstration..."
python -c "
from app import create_app
from models import Artiste
app = create_app('production')
with app.app_context():
    if Artiste.query.count() == 0:
        import seed_data
        seed_data.seed()
    else:
        print(f'ℹ️  Base existante : {Artiste.query.count()} artistes')
"

echo "✅ Build Jackbeat Phase 1 terminé !"
