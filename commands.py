import psycopg2
from psycopg2 import Error
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
import subprocess
import sys

from config import DB_PARAMS, log
import bot_utils
from database import (
    PILE, inject_in_db_tache, inject_in_db_notification,
    done_tache, delete_tache,get_information
)
import parsers
from instagram_ai import summarize_chat, clear_memory





async def fonc_add(texte: str):
    flags, index = parsers.get_flags(texte)
    texte = texte[index:].strip()

    nb, texte = parsers.get_number_flag(texte)
    if nb == '': nb = 30

    title, texte = parsers.get_entry_title(texte)
    title = title.strip()
    date, reste = parsers.get_date(texte)
    commanter = parsers.get_commanter(reste)

    date_ts = int(date.timestamp())
    days = parsers.get_days(date_ts)

    if len(flags) >= 1:
        times = parsers.list_times_flags(date, nb, flags[0])
        tache_id = await inject_in_db_tache(title, date_ts, commanter, days, flags[0])
    else:
        times = parsers.list_time(date)
        tache_id = await inject_in_db_tache(title, date_ts, commanter, days)

    await inject_in_db_notification(times, tache_id, title)
    await bot_utils.envoyer_message(f"📝 La tâche N°{tache_id} a été ajoutée.")
    return tache_id

async def fonc_list(texte: str):
    conn = None
    try:
        flags, index_start = parsers.get_flags(texte)
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()

        querry = "SELECT * FROM taches"
        commentaire = "c" in flags

        if "f" in flags:
            querry += " WHERE statut='FINI'"
            titre_liste = "📋 Tâches terminées :\n\n"
        elif "a" in flags:
            titre_liste = "📋 Toutes les tâches :\n\n"
        else:
            querry += " WHERE statut='EN_COURS'"
            titre_liste = "📋 Tâches en cours :\n\n"

        querry += " ORDER BY date_limite ASC, titre"

        if "n" in flags:
            nb, _ = parsers.get_number_flag(texte[index_start:])
            if nb: querry += f" LIMIT {nb}"

        curseur.execute(querry + ";")
        resultats = curseur.fetchall()

        if resultats:
            liste = titre_liste
            for row in resultats:
                com = row[4]
                tache_flag = row[7] if len(row) > 7 else None
                affichage_flag = f" 🔄 [{tache_flag.upper()}]" if tache_flag else ""
                date_str = datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')
                ligne_tache = f"🔹 {row[0]} : {row[2]} \n📅 {row[6]} le {date_str}{affichage_flag}\n"
                
                if commentaire and com and com.strip(): liste += ligne_tache + f"📝 {com}\n\n"
                else: liste += ligne_tache + "\n"
        else:
            liste = "il y a aucune tache ouvert"

        await bot_utils.envoyer_message(liste)
    except Error as e:
        log(f"Erreur SQL : {e}")
    finally:
        if conn: conn.close()

async def rollback():
    elem = PILE.get()
    if not elem: return

    if elem["commande"] == "add":
        delete_tache(elem["id"])
        await bot_utils.envoyer_message("la tache est bien supprimer")

    elif elem["commande"] == "done":
        tache_id = elem["id"]
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        curseur.execute("UPDATE taches SET statut = 'EN_COURS' WHERE id = %s;", (tache_id,))
        curseur.execute("UPDATE notification SET envoye = 0 WHERE tache_id = %s AND date_to_send>=%s;", 
                        (tache_id, int(datetime.now().timestamp())))
        conn.commit()
        conn.close()
        await bot_utils.envoyer_message("la tache est bien indefinie")

    elif elem["commande"] == "delete":
        tache_id = elem["id"]
        title = elem["titre"]
        timestamp = elem["date_limite"]
        flag_sauvegarde = elem.get("flag")

        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        curseur.execute(
            "INSERT INTO taches (id, Chat_id, titre, date_limite, note, statut, Days, flag) VALUES (%s, %s, %s, %s, %s, 'EN_COURS', %s, %s)",
            (tache_id, bot_utils.CHAT_ID, title, timestamp, elem["note"], elem["Days"], flag_sauvegarde)
        )
        conn.commit()
        conn.close()

        date = datetime.fromtimestamp(timestamp)
        times = parsers.list_times_flags(date, 30, flag_sauvegarde) if flag_sauvegarde else parsers.list_time(date)
        await inject_in_db_notification(times, tache_id, title)
        await bot_utils.envoyer_message(f"🔄 Restauration : La tâche N°{tache_id} a été réajoutée.")

    elif elem["commande"] in ["rename", "comment"]:
        id_tache = elem["id"]
        col = "titre" if elem["commande"] == "rename" else "note"
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        curseur.execute(f"UPDATE taches SET {col}=%s WHERE id=%s;", (elem["ancien"], id_tache))
        if col == "titre":
            curseur.execute("UPDATE notification SET message=%s WHERE tache_id=%s;", (elem["ancien"], id_tache))
        conn.commit()
        conn.close()
        await bot_utils.envoyer_message(f"📝 la tache N°{id_tache} a retrouvé sa valeur précédente.")

async def trait_tache(texte: str):
    texte = texte.strip()
    commande, texte = parsers.get_command(texte)

    if commande in ["/add", "add"]:
        try:
            tache_id = await fonc_add(texte)
            PILE.add({"commande": "add", "id": tache_id})
        except Exception as e:
            log(e)
            await bot_utils.envoyer_message("un erreur s'est produit")

    elif commande in ["/list", "list"]:
        await fonc_list(texte)

    elif commande in ["/done", "done"]:
        try:
            tache_id = int(texte)
            done_tache(tache_id)
            await bot_utils.envoyer_message(f"✅ la tache {tache_id} est fait")
            PILE.add({"commande": "done", "id": tache_id})
        except ValueError:
            await bot_utils.envoyer_message("ID invalide")

    elif commande in ["/delete", "delete"]:
        try:
            tache_id = int(texte)
            delete_tache(tache_id)
            await bot_utils.envoyer_message(f"🗑️ la tache {tache_id} est supprimer")
        except ValueError:
            pass

    elif commande in ["/rollback", "rollback"]:
        await rollback()
        
    elif commande in ["/sync", "sync"]:
        await bot_utils.envoyer_message("⚙️ Lancement de la synchronisation du calendrier...")
        # Lancement du script de synchro dans son propre dossier pour qu'il trouve son .env
        subprocess.Popen(
            [sys.executable, "run_auto.py"],
            cwd="/home/mohamed/calander"
        )

    elif commande in ["/rename", "rename", "/comment", "comment"]:
        ok, id_tache, new_val = parsers.get_elem_id(texte)
        if ok:
            col = "titre" if "rename" in commande else "note"
            conn = psycopg2.connect(**DB_PARAMS)
            curseur = conn.cursor()
            curseur.execute("SELECT * FROM taches WHERE id = %s", (id_tache,))
            res = curseur.fetchone()
            if res:
                ancien = res[2] if col == "titre" else res[4]
                PILE.add({"commande": col.replace('titre', 'rename').replace('note', 'comment'), "id": id_tache, "ancien": ancien})
                curseur.execute(f"UPDATE taches SET {col}=%s WHERE id=%s;", (new_val, id_tache))
                if col == "titre":
                    curseur.execute("UPDATE notification SET message=%s WHERE tache_id=%s;", (new_val, id_tache))
                conn.commit()
            conn.close()
            await bot_utils.envoyer_message(f"✅ Mise à jour effectuée sur la tâche N°{id_tache}")

    elif commande in ["/igsummary", "igsummary"]:
        await bot_utils.envoyer_message("🔄 Génération du résumé Instagram...")
        try:
            summary = summarize_chat()
            await bot_utils.envoyer_message(f"🤖 Résumé Instagram :\n{summary}")
            clear_memory()
            await bot_utils.envoyer_message("🗑️ Mémoire IG effacée.")
        except Exception as e:
            await bot_utils.envoyer_message(f"❌ Erreur : {e}")
    
    elif commande in ["/help", "help"]:
        help_text = (
            "LE texte entre [] est Optionelle\n"
            " <b>Assistant de Tâches - Guide des Commandes</b>\n\n"
            "✨ <b>Gestion des tâches :</b>\n"
            "• <code> /add [-flag] [nb] Titre, JJ/MM[/AAAA] [HH:mm], [Note]</code>\n"
            "       -nb : de base = 30 c'est le nombre de repition\n"
            "       -h : hourly chaque heure\n"
            "       -d : daily chaque jour\n"
            "       -w : weekly chaque semaine\n"
            "       -m : monthly chaque mois\n"
            "• <code>/list </code> : Affiche les [nb] prochaines tâches en cours.\n"
            "       -a : renvois tous les tache existant\n"
            "       -f : renvois tous les tache fini\n"
            "       -n nb: renvois un nombre d'elemnt donner\n"
            "       -c : renvois les element avec les commantaire si possible\n"
            "• <code>/get ID1, ID2</code> : Affiche les détails de tâches spécifiques.\n\n"
            "⚙️ <b>Actions :</b>\n"
            "• <code>/done ID</code> : Marquer une tâche comme terminée.\n"
            "• <code>/delete ID</code> : Supprimer définitivement une tâche.\n"
            "• <code>/rollback</code> : Annuler la dernière action (add, done, delete).\n"
            "• <code>/sync</code> : Lancer la synchronisation manuelle.\n"
            "• <code>/rename ID nouveaux nom</code> : permet de renoumer les element.\n"
            "• <code>/comment ID nouveaux nom</code> : permet d'ajouter ou modifier les commande.\n\n"
            "• <code>/igsummary</code> : Force la génération du résumé Instagram et vide la mémoire.\n"
            "💡 <i>Note : Si vous ne précisez pas d'heure, 23:59 est utilisé par défaut.</i>"
        )
        await bot_utils.envoyer_message(help_text)
    
    elif commande in ["/get", "get"]:
        ids = parsers.get_list_ids(texte)
        info = get_information(ids)
        await bot_utils.envoyer_message(info)

    else:
        await bot_utils.envoyer_message("commande inconnue. Tapez /help pour voir la liste.")

async def cerveaux(update: Update, contexte: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_chat.id
    texte = update.message.text
    log(f"📩 REÇU: {texte}")

    if bot_utils.CHAT_ID != user_id:
        bot_utils.CHAT_ID = user_id
        log(f"✅ Correction: Réponses vers {bot_utils.CHAT_ID}")

    if texte: await trait_tache(texte)