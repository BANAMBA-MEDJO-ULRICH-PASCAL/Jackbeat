#!/usr/bin/env bash
# ════════════════════════════════════════════════
#  JACKBEAT — Script de build pour Render.com
#  Exécuté automatiquement à chaque déploiement
# ════════════════════════════════════════════════
set -o errexit   # Arrêter si une commande échoue

echo "📦 Installation des dépendances Python..."
pip install -r requirements.txt

echo "🗄️  Initialisation de la base de données..."
python -c "
from app import create_app
from models import db
app = create_app('production')
with app.app_context():
    db.create_all()
    print('✅ Tables créées / vérifiées')
"

echo "🌱 Vérification des données initiales..."
python -c "
from app import create_app
from models import db, Artiste, Oeuvre
app = create_app('production')
with app.app_context():
    if Artiste.query.count() == 0:
        import seed_data
        seed_data.seed()
        print('✅ Données de démonstration injectées')
    else:
        print(f'ℹ️  Base existante : {Artiste.query.count()} artistes')
"

echo "✅ Build Jackbeat terminé avec succès !"
