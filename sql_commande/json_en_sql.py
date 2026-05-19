import psycopg2
import json
import os

# --- CONFIGURATION ---
DB_PARAMS = {
    "dbname": "tache",
    "user": "postgres",
    "password": "Mohamed2006",
    "host": "localhost",
    "port": "5432"
}

# Le nom du fichier que le script doit lire
NOM_FICHIER_JSON = "ma_pile.json"

def initialisation_depuis_fichier():
    # 1. Vérifier si le fichier existe
    if not os.path.exists(NOM_FICHIER_JSON):
        print(f"❌ Erreur : Le fichier '{NOM_FICHIER_JSON}' est introuvable.")
        return

    conn = None
    try:
        # 2. Lire le fichier JSON
        print(f"📖 Lecture du fichier {NOM_FICHIER_JSON}...")
        with open(NOM_FICHIER_JSON, 'r', encoding='utf-8') as f:
            donnees_historique = json.load(f)

        if not isinstance(donnees_historique, list):
            print("❌ Erreur : Le format du JSON doit être une liste [].")
            return

        # 3. Connexion à PostgreSQL
        conn = psycopg2.connect(**DB_PARAMS)
        cur = conn.cursor()

        # 4. Création de la table si nécessaire
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pile_historique (
                id SERIAL PRIMARY KEY,
                donnees JSONB NOT NULL,
                date_action TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. Insertion des données
        print(f"📥 Insertion de {len(donnees_historique)} éléments dans la base de données...")
        for element in donnees_historique:
            cur.execute(
                "INSERT INTO pile_historique (donnees) VALUES (%s)",
                (json.dumps(element),)
            )
        
        conn.commit()
        print("✅ Importation réussie et terminée !")

    except json.JSONDecodeError:
        print(f"❌ Erreur : Le fichier '{NOM_FICHIER_JSON}' ne contient pas un JSON valide.")
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation : {e}")
        if conn: conn.rollback()
    finally:
        if conn: conn.close()

if __name__ == "__main__":
    initialisation_depuis_fichier()