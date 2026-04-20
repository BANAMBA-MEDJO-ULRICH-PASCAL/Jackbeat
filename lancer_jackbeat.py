#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════╗
║   JACKBEAT — Script de lancement             ║
║   Patrimoine Musical Camerounais             ║
╚══════════════════════════════════════════════╝

Ce script :
1. Installe les dépendances si nécessaire
2. Initialise la base de données
3. Injecte des données de test (si vide)
4. Lance le serveur Flask sur http://localhost:5000

USAGE :  python lancer_jackbeat.py
"""
import subprocess, sys, os

def pip_install():
    print("📦 Installation des dépendances...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt", "-q"])
    print("✅ Dépendances installées\n")

def init_db():
    from app import create_app
    from models import db, Artiste, Oeuvre
    app = create_app('development')
    with app.app_context():
        db.create_all()
        print("✅ Base de données prête")

        # Seed si vide
        if Artiste.query.count() == 0:
            print("🌱 Injection des données de test...")
            import seed_data
            seed_data.seed()
        else:
            nb_a = Artiste.query.filter_by(statut='approuve').count()
            nb_o = Oeuvre.query.filter_by(statut='approuve').count()
            print(f"ℹ️  Base existante : {nb_a} artistes · {nb_o} œuvres approuvées")

def run():
    from app import app
    print("\n" + "═"*50)
    print("  🎵  JACKBEAT — Serveur démarré !")
    print("═"*50)
    print("  → Ouvrir dans ton navigateur :")
    print("    http://localhost:5000")
    print()
    print("  → Espace admin :")
    print("    http://localhost:5000/admin")
    print("    Login : admin  /  Mot de passe : jackbeat2024")
    print()
    print("  → Arrêter le serveur : Ctrl+C")
    print("═"*50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5000)

if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    pip_install()
    init_db()
    run()
