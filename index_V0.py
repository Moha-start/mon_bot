from datetime import datetime, time as Time
from dateutil.relativedelta import relativedelta
import sqlite3
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
import re, json, os
# --- CONFIGURATION ---
LOGS_ACTIFS = True
if not LOGS_ACTIFS:
    print = lambda *args, **kwargs: None


TOKEN = "8267702446:AAEyqxNWZEAy4Q3x6ToQWuwPZ2HiScmTwPA"
CHAT_ID = 6302498043

# Variable globale pour stocker l'instance du bot
bot_service = None

# --- CLASSES ---
class Pile:
    def __init__(self, nom_fichier="ma_pile.json"):
        self.nom_fichier = nom_fichier
        self.pile = self._charger()

    def _charger(self):
        if os.path.exists(self.nom_fichier):
            with open(self.nom_fichier, 'r') as f:
                return json.load(f)
        return []

    def _sauvegarder(self):
        with open(self.nom_fichier, 'w') as f:
            json.dump(self.pile, f)

    def add(self, element):
        self.pile.append(element)
        self._sauvegarder()

    def get(self):
        if not self.est_vide():
            element = self.pile.pop()
            self._sauvegarder()
            return element
        return None
    def empty(self):
        while not self.est_vide():
            self.get()
        self._sauvegarder()
    def est_vide(self):
        return len(self.pile) == 0

    def __str__(self):
        text=""
        for elem in self.pile:
            text+=str(elem)+"\n"
        return text

PILE = Pile()

# --- FONCTIONS SYSTEME (INIT) ---

async def post_init(application: Application):
    """Fonction appelée une fois que l'application est prête."""
    global bot_service
    bot_service = application.bot
    print("✅ Le bot est initialisé et la variable globale est connectée !")
    await envoyer_message("🟢 Bot en ligne et prêt à être utilisé !")

async def envoyer_message(message: str):
    """Envoie un message en utilisant l'instance globale du bot."""
    if bot_service is None:
        print("⚠️ Erreur : Le bot n'est pas encore prêt pour envoyer des messages.")
        return
    try:
        await bot_service.send_message(chat_id=CHAT_ID, text=message, parse_mode="HTML")
        print(f"📤 Message envoyé : {message}")
    except Exception as e:
        print(f"❌ Erreur Telegram lors de l'envoi : {e}")

# --- LOGIQUE METIER ---

async def cerveaux(update: Update, contexte: ContextTypes.DEFAULT_TYPE):
    global CHAT_ID  # On va mettre à jour l'ID globalement
    
    # Récupérer les infos du message entrant
    user_id = update.effective_chat.id
    texte = update.message.text
    
    print(f"📩 Message REÇU de l'ID : {user_id}")
    print(f"📄 Contenu : {texte}")

    # Mettre à jour le CHAT_ID pour répondre à la personne qui parle
    if CHAT_ID != user_id:
        print(f"⚠️ Attention : Le CHAT_ID dans le code ({CHAT_ID}) était différent.")
        CHAT_ID = user_id
        print(f"✅ Correction : Les futures réponses iront vers {CHAT_ID}")

    if texte:
        await trait_tache(texte)

def vider_base_de_donnees():
    conn=None
    try:
        conn = sqlite3.connect("tache.db")
        cursor = conn.cursor()
        cursor.execute("DELETE FROM taches")
        cursor.execute("DELETE FROM notification")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='taches'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='notification'")
        conn.commit()
        print("Toutes les donnees ont ete supprimees avec succes.")
    except sqlite3.Error as e:
        print(f"Erreur lors de la suppression : {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def init_db():
    conn=sqlite3.connect("tache.db")
    c=conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS taches(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            Chat_id INTEGER,
            titre TEXT,
            date_limite INTEGER,
            note TEXT,
            statut TEXT DEFAULT 'EN_COURS',
            Days TEXT
            )
            ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS notification(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tache_id INTEGER,
            date_to_send INTEGER,
            message TEXT,
            name_times TEXT,
            envoye INTEGER DEFAULT 0)
              ''')
    c.execute("CREATE INDEX IF NOT EXISTS idx_notif_envoi ON notification(envoye, date_to_send);")
    conn.commit()
    conn.close()
    print("Base de donnees initialisee (taches + notifications).")

def get_command(texte:str) -> tuple[str,str]:
    texte+=" "
    index=0
    size=len(texte)
    while index<size and texte[index]==" ":
        index+=1
    first=""
    while index<size and texte[index]!=" ":
        first+=texte[index]
        index+=1
    return first.lower(),texte[index+1:]

def get_entry_title(texte:str)->tuple[str,str]:
    new=""
    index=0
    size=len(texte)
    while index<size and texte[index]!=",":
        new+=texte[index]
        index+=1
    return new,texte[index+1:]




def get_date(texte: str) -> tuple[datetime, str]:
    # Regex breakdown:
    # Day/Month (required)
    # Optional Year ( / followed by 4 digits)
    # Optional Time (whitespace followed by HH:MM)
    pattern = r"(\d{1,2}/\d{1,2})(?:/(\d{4}))?(?:\s+(\d{1,2}:\d{1,2}))?"
    
    match = re.search(pattern, texte)
    if not match:
        raise ValueError("Format de date invalide. Utilisez au moins JJ/MM")

    day_month = match.group(1)
    year = match.group(2)
    time = match.group(3)
    
    # 1. Handle Year: use current year if missing
    current_year = datetime.now().year
    full_date_str = f"{day_month}/{year if year else current_year}"
    
    # 2. Handle Time: use 23:59 if missing
    full_time_str = time if time else "23:59"
    
    final_str = f"{full_date_str} {full_time_str}"
    
    try:
        date_obj = datetime.strptime(final_str, "%d/%m/%Y %H:%M")
    except ValueError:
        raise ValueError("La date ou l'heure fournie est illogique.")

    # Clean up the remaining text
    index_fin_match = match.end()
    reste = texte[index_fin_match:].strip()
    if reste.startswith(','):
        reste = reste[1:].strip()
    return date_obj, reste

def get_days(date:datetime):
    if isinstance(date, (int, float)):
        date = datetime.fromtimestamp(date)
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]    
    return jours[date.weekday()]

def get_commanter(texte:str)->str:
    size=len(texte)
    index=0
    while index<size and texte[index]!=",":
        index+=1
    if size==0:return " "
    else : return texte[:index]

def est_dans_la_tranche(dt_a_tester:datetime):
    h_debut = Time(22, 0)
    h_fin = Time(6, 0)
    t = dt_a_tester.time()
    if h_debut <= h_fin:
        return h_debut <= t <= h_fin
    else:
        return t >= h_debut or t <= h_fin

def list_new_time(time:datetime)->list[datetime]:
    times=[]
    date_actue = datetime.now()
    timestamp_actuel = int(date_actue.timestamp())
    times.append((time,"Now"))
    for i in range(1,11):
        times.append((time-relativedelta(minutes=i),f"{i} minutes"))
    times.append((time-relativedelta(minutes=15),"15 minutes"))
    times.append((time-relativedelta(minutes=20),"20 minutes"))
    times.append((time-relativedelta(minutes=25),"25 minutes"))
    times.append((time-relativedelta(minutes=30),"30 minutes"))
    times.append((time-relativedelta(minutes=45),"45 minutes"))
    times.append((time-relativedelta(hours=1),"1 Heure"))
    times.append((time-relativedelta(minutes=90),"1:30 Heures"))
    for i in range(2,7):
        times.append((time-relativedelta(hours=i),f"{i} Heures"))
    times.append((time-relativedelta(hours=12),"12 Heures"))
    tranche=(est_dans_la_tranche(time))
    
    if tranche:
        newtime=time-relativedelta(hours=12)
        for i in range(1,7):
            times.append((newtime-relativedelta(days=i),f"{i} Joures"))
        for i in range(1,5):
            times.append((newtime-relativedelta(weeks=i),f"{i} Semaines"))
        for i in range(1,4):
            times.append((newtime-relativedelta(months=i),f"{i} Mois"))
    else:
        for i in range(1,7):
            times.append((time-relativedelta(days=i),f"{i} Joures"))
        for i in range(1,5):
            times.append((time-relativedelta(weeks=i),f"{i} Semaines"))
        for i in range(1,4):
            times.append((time-relativedelta(months=i),f"{i} Mois"))
    times.reverse()
    table=[]
    for i in range(len(times)):
        date=times[i][0].timestamp()
        if date>timestamp_actuel:
            table.append((date,times[i][1]))
    return table

async def inject_in_db_tache(title:str,date:datetime,commanter:str):
    try:
        date_ts=int(date.timestamp())
        conn=sqlite3.connect("tache.db")
        curseur=conn.cursor()
        sql_insert = "INSERT INTO taches (Chat_id ,titre ,date_limite ,note,Days) VALUES (?, ?, ?, ?, ?)"
        valeur=(CHAT_ID, title,date_ts,commanter,get_days(date_ts))
        curseur.execute(sql_insert,valeur)
        tache_id=curseur.lastrowid
        conn.commit()
        conn.close()
        print(f"l'injection de {title} est bien fait")
        return tache_id
    except sqlite3.IntegrityError:
        await envoyer_message("Erreur : il y a un problemme avec le key primaire")
    except sqlite3.Error as e:
        await envoyer_message(f"Erreur lors de l'insertion : {e}")

async def inject_in_db_notification(listetimes:list[datetime],tache_id,message):
    try:
        conn=sqlite3.connect("tache.db")
        curseur=conn.cursor()
        for elem in listetimes:
            sql_insert = "INSERT INTO notification (tache_id ,date_to_send ,message,name_times) VALUES (?, ?, ?, ?)"
            valeur=(tache_id, elem[0],message,elem[1])
            curseur.execute(sql_insert,valeur)
        conn.commit()
        conn.close()
    except sqlite3.IntegrityError:
        await envoyer_message("Erreur : il y a un problemme avec le key primaire")
    except sqlite3.Error as e:
        await envoyer_message(f"Erreur lors de l'insertion : {e}")

def done_tache(id_tache:int):
    try:
        conn=sqlite3.connect("tache.db")
        curseur=conn.cursor()
        curseur.execute(f"UPDATE taches SET statut = 'FINI' WHERE id=?",(id_tache,))
        curseur.execute(f"UPDATE notification SET envoye = 1 WHERE tache_id=?",(id_tache,))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Erreur SQL : {e}")

def delete_tache(id_tache:int):
    try:
        conn=sqlite3.connect("tache.db")
        curseur=conn.cursor()
        curseur.execute("SELECT * FROM taches WHERE id = ?",(id_tache,))
        res=curseur.fetchone()
        if res:
            elem={"commande":"delete","id":res[0],"chat_id":res[1],"titre":res[2],"date_limite":res[3],"note":res[4],"statut":res[5],"Days":res[6]}
            PILE.add(elem)
        curseur.execute("DELETE FROM notification WHERE tache_id = ?;",(id_tache,))
        curseur.execute("DELETE FROM taches WHERE id = ?",(id_tache,))
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        print(f"Erreur SQL : {e}")

async def get_nombre(texte:str):
    texte=texte.strip()
    if texte:
        if texte.isdigit():
            return int(texte)
        else:
            await envoyer_message("le Id doit etre un nombre il doit etre un entier")

async def fonc_add(texte:str):
    temp_title=get_entry_title(texte)
    texte=temp_title[1]
    title=temp_title[0]
    temp_time=get_date(texte)
    date=temp_time[0]
    texte=temp_time[1]
    commanter=get_commanter(texte)
    times=list_new_time(date)
    tache_id=await inject_in_db_tache(title,date,commanter)
    await inject_in_db_notification(times,tache_id,title)
    await envoyer_message(f"📝 la tache N°{tache_id} est ajouter")
    return tache_id

async def fonc_list(texte:str):
    conn = None
    try:
        nb=await get_nombre(texte)
        conn = sqlite3.connect("tache.db")
        curseur = conn.cursor()
        if nb:
            curseur.execute("SELECT * FROM taches WHERE statut='EN_COURS' ORDER BY date_limite ASC,titre LIMIT ?;",(nb,))
        else:
            curseur.execute("SELECT * FROM taches WHERE statut='EN_COURS' ORDER BY date_limite ASC,titre;")
        resultats = curseur.fetchall()
        liste="📋 Tâches en cours :\n\n"
        if resultats:
            for row in resultats:
                com=row[4]
                if com.strip():
                    liste+=f"🔹 {row[0]} : {row[2]} \n📅{row[6]} le {datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')} \n📝{com}\n\n"
                else :
                    liste+=f"🔹 {row[0]} : {row[2]} \n📅{row[6]} le  {datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')} \n\n"
        await envoyer_message(liste)
    except sqlite3.Error as e:
        print(f"Erreur SQL : {e}")
    finally:
        if conn:
            conn.close()

async def get_id(texte:str):
    size=len(texte)
    index=0
    nb=""
    while index<size:
        elem=texte[index]
        if elem==" "or elem ==",":
            index+=1
        else:
            nb+=elem
            index+=1
    if nb.isdigit():
        return int(nb)
    else :
        await envoyer_message("tu dois ecrire un nombre")

def get_list_ids(texte:str):
    ids=[]
    curent=""
    size=len(texte)
    index=0
    while index<size :
        elem=texte[index]
        if elem!=" " and elem!=",":
            curent+=elem
            index+=1
        elif elem==",":
            if curent.isdigit():
                ids.append(int(curent))
                curent=""
            index+=1
        else:index+=1
    if curent.isdigit():ids.append(int(curent))
    return ids
   
def get_element(index:list):
    liste=""
    try :
        conn = sqlite3.connect("tache.db")
        curseur = conn.cursor()
        for elem in index:
            curseur.execute("SELECT * FROM taches WHERE id = ?",(elem,))
            row=curseur.fetchone()
            if row:
                com=row[4]
                if com.strip():
                    liste+=f"🔹 {row[0]} : {row[2]} \n📅{row[6]} le {datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')} \n📝{com}\n\n"
                else :
                    liste+=f"🔹 {row[0]} : {row[2]} \n📅{row[6]} le  {datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')} \n\n"
        conn.close()
        return liste
    except sqlite3.Error as e:
        print(f"Erreur SQL : {e}")

async def rollback():
    elem=PILE.get()
    if not elem: return
    if elem["commande"]=="add":
        delete_tache(elem["id"])
        await envoyer_message("la tache est bien supprimer")
    elif elem["commande"]=="done":
        tache_id=elem["id"]
        conn = sqlite3.connect("tache.db")
        curseur = conn.cursor()
        curseur.execute("UPDATE taches SET statut = 'EN_COURS' WHERE id = ?;",(tache_id,))
        curseur.execute("UPDATE notification SET envoye = 0 WHERE tache_id = ? AND date_to_send>=?;",(tache_id,int( datetime.now().timestamp())))
        conn.commit()
        conn.close()
        await envoyer_message("la tache est bien indefinie")
    elif elem["commande"]=="delete":
        title=elem["titre"]
        tache_id=elem["id"]
        timestamp=elem["date_limite"]
        conn = sqlite3.connect("tache.db")
        curseur = conn.cursor()
        curseur.execute("INSERT INTO taches (id, Chat_id, titre, date_limite, note, statut, Days) VALUES (?, ?, ?, ?, ?, 'EN_COURS', ?)",(elem["id"], CHAT_ID, elem["titre"], timestamp, elem["note"], elem["Days"]))
        conn.commit()
        conn.close()
        date=datetime.fromtimestamp(timestamp)
        times=list_new_time(date)
        await inject_in_db_notification(times,tache_id,title)
        await envoyer_message(f"📝 la tache N°{tache_id} est ajouter")

async def trait_tache(texte:str):
    texte=texte.lower()
    temp_commande=get_command(texte)
    commande=temp_commande[0]
    texte=temp_commande[1]
    if commande=="/add" or commande=="add":
        try :
            tache_id=await fonc_add(texte)
            PILE.add({"commande":"add","id":tache_id})
        except :
            await envoyer_message("un erreur s'est produit")
    elif commande=="/list" or  commande=="list":
        await fonc_list(texte)
    elif commande=="/done" or commande=="done":
        tache_id=await get_id(texte)
        if tache_id:
            done_tache(tache_id)
            await envoyer_message(f"✅ la tache {tache_id} est fait")
            PILE.add({"commande":"done","id":tache_id})
    elif commande=="/delete" or commande=="delete":
        tache_id=await get_id(texte)
        if tache_id:
            delete_tache(tache_id)
            await envoyer_message(f"🗑️ la tache {tache_id} est supprimer")
    elif commande=="/help" or commande=="help":
        help_text = (
                    "🍎🍎🍎 <b>Assistant de Tâches - Guide des Commandes</b>\n\n"
                    "✨ <b>Gestion des tâches :</b>\n"
                    "• <code>/add Titre, JJ/MM [HH:mm], [Note]</code>\n"
                    "  <i>Ex: /add Acheter du pain, 25/12 18:00, Boulangerie fermée le lundi</i>\n"
                    "• <code>/list [nb]</code> : Affiche les [nb] prochaines tâches en cours.\n"
                    "• <code>/get ID1, ID2</code> : Affiche les détails de tâches spécifiques.\n\n"
                    "⚙️ <b>Actions :</b>\n"
                    "• <code>/done ID</code> : Marquer une tâche comme terminée.\n"
                    "• <code>/delete ID</code> : Supprimer définitivement une tâche.\n"
                    "• <code>/rollback</code> : Annuler la dernière action (add, done, delete).\n"
                    "• <code>/sync</code> : Lancer la synchronisation manuelle.\n\n"
                    "💡 <i>Note : Si vous ne précisez pas d'heure, 23:59 est utilisé par défaut.</i>"
                )
        await envoyer_message(help_text)
    elif commande=="/get" or commande=="get":
        ids=get_list_ids(texte)
        if ids:
            message=get_element(ids)
            await envoyer_message(message)
    elif commande=="/rollback" or commande=="rollback":
        await rollback()
    elif commande=="/sync" or commande=="sync":
        import subprocess
        import sys
        
        await envoyer_message("⚙️ Lancement de la synchronisation en arrière-plan...")
        
        try:
            # This executes the script using the same python interpreter as the bot
            subprocess.Popen([sys.executable, "daily_launcher.py"])
            # We use Popen so the bot doesn't "freeze" while waiting for the script to finish
        except Exception as e:
            await envoyer_message(f"❌ Erreur lors du lancement : {e}")
    else:
        await envoyer_message("commande inconnue. Tapez /help pour voir la liste.")

async def verification_periodique(context: ContextTypes.DEFAULT_TYPE):
    date_actue = datetime.now()
    timestamp_actuel = int(date_actue.timestamp())
    conn = None
    try:
        conn = sqlite3.connect("tache.db")
        curseur = conn.cursor()
        curseur.execute("SELECT * FROM notification WHERE date_to_send <= ? AND envoye=0", (timestamp_actuel,))
        resultats = curseur.fetchall()
        if resultats:
            for row in resultats:
                notif_id = row[0]
                message_texte = f"{row[3]} expire dans {row[4]}"
                await context.bot.send_message(chat_id=CHAT_ID, text=f"⏳ RAPPEL : {message_texte}")
                curseur.execute("UPDATE notification SET envoye = 1 WHERE id = ?", (notif_id,))
                conn.commit()
                print(f"Message '{message_texte}' envoye et marque comme fait.")
    except sqlite3.Error as e:
        print(f"Erreur SQL : {e}")
    finally:
        if conn:
            conn.close()
def start():
    print("Demarrage du bot...")
    # Add 'drop_pending_updates' here in the builder if run_polling isn't catching it
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(MessageHandler(filters.TEXT, cerveaux))
    
    job_queue = app.job_queue
    job_queue.run_repeating(verification_periodique, interval=60, first=10)
    print("Bot prêt ! Lancement du polling...")
    
    # Ensure this is set to True to ignore old messages on startup
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    print("import fini")
    init_db()
    print("db fini")
    start()
    print("start fini")