#!/usr/bin/env bash
# ════════════════════════════════════════════════
#  JACKBEAT — Script de build Render.com
# ════════════════════════════════════════════════
set -o errexit

echo "📦 Mise à jour de pip..."
pip install --upgrade pip --quiet

echo "📦 Installation des dépendances..."
pip install -r requirements.txt --quiet

echo "🗄️  Initialisation de la base de données..."
python -c "
from app import create_app
from models import db
app = create_app('production')
with app.app_context():
    db.create_all()
    print('✅ Tables créées')
"

echo "🌱 Données initiales..."
python -c "
from app import create_app
from models import Artiste
app = create_app('production')
with app.app_context():
    if Artiste.query.count() == 0:
        import seed_data
        seed_data.seed()
        print('✅ Données de test injectées')
    else:
        print(f'ℹ️  Base existante : {Artiste.query.count()} artistes')
"

echo "✅ Build terminé !"
