#!/usr/bin/env bash
# ════════════════════════════════════════════════
#  JACKBEAT — Script de build (Render.com)
# ════════════════════════════════════════════════
set -o errexit

echo "📦 Mise à jour de pip..."
pip install --upgrade pip --quiet

echo "📦 Installation des dépendances..."
pip install -r requirements.txt --quiet

echo "🌍 Compilation des traductions (FR / EN)..."
pybabel compile -d translations --statistics

echo "🗄️  Migration de la base de données..."
# create_app() met le schéma à jour (colonnes manquantes ajoutées, idempotent)
python -c "from app import create_app; create_app(); print('✅ Base de données migrée')"

echo "🌱 Données de démonstration (ajout des entrées manquantes uniquement)..."
python seed_data.py

echo "✅ Build Jackbeat terminé !"
