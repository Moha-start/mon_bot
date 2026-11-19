import psycopg2
from psycopg2 import Error, IntegrityError
import json
from config import DB_PARAMS, log
import bot_utils
from datetime import datetime

class Pile:
    def __init__(self, db_params):
        self.db_params = db_params
        self._creer_table()

    def _creer_table(self):
        conn = None
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pile_historique (
                    id SERIAL PRIMARY KEY,
                    donnees JSONB NOT NULL,
                    date_action TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
        except Error as e:
            log(f"❌ Erreur création table Pile : {e}")
        finally:
            if conn: conn.close()

    def add(self, element):
        conn = None
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            cur.execute("INSERT INTO pile_historique (donnees) VALUES (%s)", (json.dumps(element),))
            conn.commit()
        except Error as e:
            log(f"❌ Erreur insertion Pile : {e}")
        finally:
            if conn: conn.close()

    def get(self):
        # Optimisation avec RETURNING : on sélectionne et on supprime en 1 requête
        conn = None
        element = None
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            cur.execute("""
                DELETE FROM pile_historique 
                WHERE id = (SELECT id FROM pile_historique ORDER BY id DESC LIMIT 1) 
                RETURNING donnees;
            """)
            res = cur.fetchone()
            if res:
                element = res[0]
            conn.commit()
        except Error as e:
            log(f"❌ Erreur récupération Pile : {e}")
        finally:
            if conn: conn.close()
        return element

PILE = Pile(DB_PARAMS)

async def inject_in_db_tache(title, date_ts, commanter, days, flag=None):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        if flag:
            sql_insert = "INSERT INTO taches (Chat_id ,titre ,date_limite ,note,Days,flag) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id"
            valeur = (bot_utils.CHAT_ID, title, date_ts, commanter, days, flag)
        else:
            sql_insert = "INSERT INTO taches (Chat_id ,titre ,date_limite ,note,Days) VALUES (%s, %s, %s, %s, %s) RETURNING id"
            valeur = (bot_utils.CHAT_ID, title, date_ts, commanter, days)
        curseur.execute(sql_insert, valeur)
        tache_id = curseur.fetchone()[0]
        conn.commit()
        conn.close()
        log(f"l'injection de {title} est bien fait")
        return tache_id
    except IntegrityError:
        await bot_utils.envoyer_message("Erreur : il y a un problemme avec le key primaire")
    except Error as e:
        await bot_utils.envoyer_message(f"Erreur lors de l'insertion : {e}")

async def inject_in_db_notification(listetimes, tache_id, message):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        for elem in listetimes:
            sql_insert = "INSERT INTO notification (tache_id ,date_to_send ,message,name_times) VALUES (%s, %s, %s, %s)"
            valeur = (tache_id, elem[0], message, elem[1])
            curseur.execute(sql_insert, valeur)
        conn.commit()
        conn.close()
    except Error as e:
        await bot_utils.envoyer_message(f"Erreur lors de l'insertion : {e}")

def done_tache(id_tache: int):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        curseur.execute("UPDATE taches SET statut = 'FINI' WHERE id=%s", (id_tache,))
        curseur.execute("UPDATE notification SET envoye = 1 WHERE tache_id=%s", (id_tache,))
        conn.commit()
        conn.close()
    except Error as e:
        log(f"Erreur SQL : {e}")

def delete_tache(id_tache: int):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        curseur.execute("SELECT id, Chat_id, titre, date_limite, note, statut, Days, flag FROM taches WHERE id = %s", (id_tache,))
        res = curseur.fetchone()
        if res:
            elem = {
                "commande": "delete", "id": res[0], "chat_id": res[1], "titre": res[2],
                "date_limite": res[3], "note": res[4], "statut": res[5], "Days": res[6], "flag": res[7]
            }
            PILE.add(elem)
        # Supprime en cascade si ON DELETE CASCADE est activé, sinon la ligne suivante le fait
        curseur.execute("DELETE FROM notification WHERE tache_id = %s;", (id_tache,))
        curseur.execute("DELETE FROM taches WHERE id = %s", (id_tache,))
        conn.commit()
        conn.close()
    except Error as e:
        log(f"Erreur SQL : {e}")

def get_information(ids: list[int]) -> str:
    if not ids:
        return "⚠️ Aucun ID valide fourni. Exemple : <code>/get 1, 2</code>"

    conn = None
    result_text = ""
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()

        for tache_id in ids:
            curseur.execute(
                "SELECT id, Chat_id, titre, date_limite, note, statut, Days, flag FROM taches WHERE id = %s;",
                (tache_id,)
            )
            row = curseur.fetchone()

            if not row:
                result_text += f"❌ Tâche N°{tache_id} introuvable.\n\n"
                continue

            # Récupération du nombre de notifications restantes
            curseur.execute(
                "SELECT COUNT(*) FROM notification WHERE tache_id = %s AND envoye = 0;",
                (tache_id,)
            )
            notifs_restantes = curseur.fetchone()[0]

            date_str = datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')
            note = row[4].strip() if row[4] and row[4].strip() else "Aucune"
            statut = "✅ FINI" if row[5] == "FINI" else "⏳ EN_COURS"
            flag = row[7].upper() if row[7] else "Aucune"

            result_text += (
                f"🔹 <b>Tâche N°{row[0]} : {row[2]}</b>\n"
                f"📌 <b>Statut :</b> {statut}\n"
                f"📅 <b>Date limite :</b> {row[6]} le {date_str}\n"
                f"🔄 <b>Récurrence :</b> {flag}\n"
                f"📝 <b>Note :</b> {note}\n"
                f"🔔 <b>Rappels restants :</b> {notifs_restantes}\n\n"
            )

        return result_text.strip()
    except Error as e:
        log(f"Erreur SQL : {e}")
        return "❌ Une erreur SQL s'est produite lors de la récupération des informations."
    finally:
        if conn:
            conn.close()