import time
import subprocess
import os
import shutil

# Chemin de ton dossier MT5 local
MT5_PATH = os.path.expandvars(r"%APPDATA%\MetaQuotes\Terminal\Common\Files")
# Chemin de ton dépôt local sur ton PC
LOCAL_REPO_PATH = r"C:\Users\Edy Sandrine\Downloads\Compte CTO Trading & EA\Dashbord"

while True:
    try:
        # Copier les fichiers du dossier MT5 vers ton dossier git local
        for filename in os.listdir(MT5_PATH):
            if filename.endswith(".csv") or filename.endswith(".txt") or filename.endswith(".json"):
                shutil.copy(os.path.join(MT5_PATH, filename), LOCAL_REPO_PATH)

        # Envoyer automatiquement sur GitHub
        os.chdir(LOCAL_REPO_PATH)
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", "Auto-sync MT5 data"], check=True)
        subprocess.run(["git", "push", "origin", "main"], check=True)
        
        print("Données synchronisées avec succès !")
    except Exception as e:
        print("En attente de nouveaux fichiers / Pas de modifications...")

    # Attendre 30 secondes avant la prochaine synchronisation
    time.sleep(30)