from datetime import datetime, time as Time
from dateutil.relativedelta import relativedelta
import psycopg2
from psycopg2 import Error, IntegrityError
from telegram import Update
from telegram.ext import Application, ContextTypes, MessageHandler, filters
import re, json, os
from dotenv import load_dotenv
# --- CONFIGURATION ---
load_dotenv()
LOGS_ACTIFS = True
if not LOGS_ACTIFS:
    print = lambda *args, **kwargs: None

TOKEN = os.getenv("TOKEN_TACHE")
CHAT_ID = int(os.getenv("CHAT_ID_TACHE"))

# Paramètres de connexion PostgreSQL
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT"))
}
# Variable globale pour stocker l'instance du bot
bot_service = None

class Pile:
    def __init__(self, db_params):
        self.db_params = db_params
        self._creer_table()

    def _creer_table(self):
        """Crée la table de stockage de la pile si elle n'existe pas."""
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
            print(f"❌ Erreur création table Pile : {e}")
        finally:
            if conn: conn.close()

    def add(self, element):
        """Ajoute une action au sommet de la pile."""
        conn = None
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            cur.execute("INSERT INTO pile_historique (donnees) VALUES (%s)", (json.dumps(element),))
            conn.commit()
        except Error as e:
            print(f"❌ Erreur insertion Pile : {e}")
        finally:
            if conn: conn.close()

    def get(self):
        """Récupère et supprime le dernier élément (LIFO)."""
        conn = None
        element = None
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            # On récupère le dernier ID
            cur.execute("SELECT id, donnees FROM pile_historique ORDER BY id DESC LIMIT 1")
            res = cur.fetchone()
            if res:
                row_id, element = res
                # On le supprime pour simuler le 'pop' de la pile
                cur.execute("DELETE FROM pile_historique WHERE id = %s", (row_id,))
                conn.commit()
        except Error as e:
            print(f"❌ Erreur récupération Pile : {e}")
        finally:
            if conn: conn.close()
        return element

    def empty(self):
        """Vide tout l'historique."""
        conn = None
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            cur.execute("TRUNCATE TABLE pile_historique RESTART IDENTITY")
            conn.commit()
        except Error as e:
            print(f"❌ Erreur vidage Pile : {e}")
        finally:
            if conn: conn.close()

    def est_vide(self):
        """Vérifie si la pile est vide."""
        conn = None
        vide = True
        try:
            conn = psycopg2.connect(**self.db_params)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM pile_historique")
            vide = (cur.fetchone()[0] == 0)
        except Error as e:
            print(f"❌ Erreur check vide Pile : {e}")
        finally:
            if conn: conn.close()
        return vide

    def __str__(self):
        return "Instance de Pile (Stockage : PostgreSQL)"

    def importer_historique_existant(self, liste_json):
        """Fonction utilitaire pour injecter ton gros JSON une seule fois."""
        for item in liste_json:
            self.add(item)
        print(f"✅ {len(liste_json)} éléments importés dans la base de données !")
PILE = Pile(DB_PARAMS)

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
    global CHAT_ID 
    user_id = update.effective_chat.id
    texte = update.message.text
    print(f"📩 Message REÇU de l'ID : {user_id}")
    print(f"📄 Contenu : {texte}")

    if CHAT_ID != user_id:
        print(f"⚠️ Attention : Le CHAT_ID dans le code ({CHAT_ID}) était différent.")
        CHAT_ID = user_id
        print(f"✅ Correction : Les futures réponses iront vers {CHAT_ID}")

    if texte:
        await trait_tache(texte)

def vider_base_de_donnees():
    conn=None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE taches, notification RESTART IDENTITY CASCADE;")
        conn.commit()
        print("Toutes les donnees ont ete supprimees avec succes.")
    except Error as e:
        print(f"Erreur lors de la suppression : {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def get_command(texte:str) -> tuple[str,str]:
    texte.strip()
    texte+=" "
    index=0
    size=len(texte)
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
    pattern = r"(\d{1,2}/\d{1,2})(?:/(\d{4}))?(?:\s+(\d{1,2}:\d{1,2}))?"
    match = re.search(pattern, texte)
    if not match:
        raise ValueError("Format de date invalide. Utilisez au moins JJ/MM")

    day_month = match.group(1)
    year = match.group(2)
    time = match.group(3)
    current_year = datetime.now().year
    full_date_str = f"{day_month}/{year if year else current_year}"
    full_time_str = time if time else "23:59"
    final_str = f"{full_date_str} {full_time_str}"
    
    try:
        date_obj = datetime.strptime(final_str, "%d/%m/%Y %H:%M")
    except ValueError:
        raise ValueError("La date ou l'heure fournie est illogique.")

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

def list_time(time:datetime)->list[datetime]:
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
        conn = psycopg2.connect(**DB_PARAMS)
        curseur=conn.cursor()
        sql_insert = "INSERT INTO taches (Chat_id ,titre ,date_limite ,note,Days) VALUES (%s, %s, %s, %s, %s) RETURNING id"
        valeur=(CHAT_ID, title,date_ts,commanter,get_days(date_ts))
        curseur.execute(sql_insert,valeur)
        tache_id=curseur.fetchone()[0]
        conn.commit()
        conn.close()
        print(f"l'injection de {title} est bien fait")
        return tache_id
    except IntegrityError:
        await envoyer_message("Erreur : il y a un problemme avec le key primaire")
    except Error as e:
        await envoyer_message(f"Erreur lors de l'insertion : {e}")

async def inject_in_db_notification(listetimes:list[datetime],tache_id,message):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        curseur=conn.cursor()
        for elem in listetimes:
            sql_insert = "INSERT INTO notification (tache_id ,date_to_send ,message,name_times) VALUES (%s, %s, %s, %s)"
            valeur=(tache_id, elem[0],message,elem[1])
            curseur.execute(sql_insert,valeur)
        conn.commit()
        conn.close()
    except IntegrityError:
        await envoyer_message("Erreur : il y a un problemme avec le key primaire")
    except Error as e:
        await envoyer_message(f"Erreur lors de l'insertion : {e}")

def done_tache(id_tache:int):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        curseur=conn.cursor()
        curseur.execute("UPDATE taches SET statut = 'FINI' WHERE id=%s",(id_tache,))
        curseur.execute("UPDATE notification SET envoye = 1 WHERE tache_id=%s",(id_tache,))
        conn.commit()
        conn.close()
    except Error as e:
        print(f"Erreur SQL : {e}")

def delete_tache(id_tache:int):
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        curseur=conn.cursor()
        curseur.execute("SELECT * FROM taches WHERE id = %s",(id_tache,))
        res=curseur.fetchone()
        if res:
            elem={"commande":"delete","id":res[0],"chat_id":res[1],"titre":res[2],"date_limite":res[3],"note":res[4],"statut":res[5],"Days":res[6]}
            PILE.add(elem)
        curseur.execute("DELETE FROM notification WHERE tache_id = %s;",(id_tache,))
        curseur.execute("DELETE FROM taches WHERE id = %s",(id_tache,))
        conn.commit()
        conn.close()
    except Error as e:
        print(f"Erreur SQL : {e}")

async def get_nombre(texte:str):
    texte.strip()
    if texte:
        index=0
        size=len(texte)
        valeur=texte[index]
        res=''
        while index<size and not valeur.isdecimal():
            index+=1
            valeur=texte[index]
        while index<size and (valeur.isdecimal() or valeur=="_"):
            valeur=texte[index]
            res+=valeur
            index+=1
        try:
            return int(res)
        except ValueError:
            await envoyer_message("le Id doit etre un nombre  entier")
        except :
            await envoyer_message("un erreur s'est produit")

def get_flags(texte:str):
    texte=texte.strip()
    index=0
    size=len(texte)
    flags=[]
    if texte:
        if texte[0]=="-":
            index+=1
            flags=[]
            while index<size and texte[index]!=" ":
                flags.append(texte[index].lower())
                index+=1
    return flags,index

async def fonc_add(texte:str):
    flags,index=get_flags(texte)
    texte=texte[index:]
    temp_title=get_entry_title(texte)
    texte=temp_title[1]
    title=temp_title[0]
    temp_time=get_date(texte)
    date=temp_time[0]
    texte=temp_time[1]
    commanter=get_commanter(texte)
    
    if flags:
        nb=30
        if 'h' in flags:
            pass
        elif 'd' in flags:
            pass
        elif 'w' in flags:
            pass
        elif 'm' in flags:
            pass
        elif 'y' in flags:
            pass
    else:
        times=list_time(date)
        tache_id=await inject_in_db_tache(title,date,commanter)
        await inject_in_db_notification(times,tache_id,title)
        await envoyer_message(f"📝 la tache N°{tache_id} est ajouter")
        return tache_id

async def fonc_list(texte:str):
    conn = None
    try:
        flags,index_start=get_flags(texte)
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        querry="SELECT * FROM taches"
        commentaire=False
        if flags==[]:
            querry+=" WHERE statut='EN_COURS'"
        elif "f" in flags:
            querry+=" WHERE statut='FINI'"
        elif "a" not in flags:
            querry+=" WHERE statut='EN_COURS'"
        querry+=" ORDER BY date_limite ASC,titre"
        if "n" in flags:
            nb=get_nombre(texte[index_start:])
            querry+=f" LIMIT {nb}"
        if "c" in flags:
            commentaire=True
        querry+=";"
        curseur.execute(querry)
        resultats = curseur.fetchall()
        if resultats:
            liste="📋 Tâches en cours :\n\n"
            if commentaire:
                for row in resultats:
                    com=row[4]
                    if com.strip():
                        liste+=f"🔹 {row[0]} : {row[2]} \n📅{row[6]} le {datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')} \n📝{com}\n\n"
                    else :
                        for row in resultats:
                            liste+=f"🔹 {row[0]} : {row[2]} \n📅{row[6]} le  {datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')} \n\n"
            else :
                for row in resultats:
                    liste+=f"🔹 {row[0]} : {row[2]} \n📅{row[6]} le  {datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')} \n\n"
        else:
            liste+="il y a aucune tache ouvert"
        await envoyer_message(liste)
    except Error as e:
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
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        for elem in index:
            curseur.execute("SELECT * FROM taches WHERE id = %s",(elem,))
            row=curseur.fetchone()
            if row:
                com=row[4]
                if com.strip():
                    liste+=f"🔹 {row[0]} : {row[2]} \n📅{row[6]} le {datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')} \n📝{com}\n\n"
                else :
                    liste+=f"🔹 {row[0]} : {row[2]} \n📅{row[6]} le  {datetime.fromtimestamp(row[3]).strftime('%d/%m/%Y %H:%M')} \n\n"
        conn.close()
        return liste
    except Error as e:
        print(f"Erreur SQL : {e}")

def get_elem_id(text:str):
    text=text.strip()
    id_tache=''
    index=0
    size=len(text)
    while index<size and text[index].isalnum():
        id_tache+=text[index]
        index+=1
    index+=1
    try :
        id_tache=int(id_tache)
        return True,id_tache,text[index:]
    except ValueError as e:
        return False,e

async def rollback():
    elem=PILE.get()
    if not elem: return
    
    if elem["commande"]=="add":
        delete_tache(elem["id"])
        await envoyer_message("la tache est bien supprimer")
        
    elif elem["commande"]=="done":
        tache_id=elem["id"]
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        curseur.execute("UPDATE taches SET statut = 'EN_COURS' WHERE id = %s;",(tache_id,))
        curseur.execute("UPDATE notification SET envoye = 0 WHERE tache_id = %s AND date_to_send>=%s;",(tache_id,int( datetime.now().timestamp())))
        conn.commit()
        conn.close()
        await envoyer_message("la tache est bien indefinie")
        
    elif elem["commande"]=="delete":
        title=elem["titre"]
        tache_id=elem["id"]
        timestamp=elem["date_limite"]
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        curseur.execute("INSERT INTO taches (id, Chat_id, titre, date_limite, note, statut, Days) VALUES (%s, %s, %s, %s, %s, 'EN_COURS', %s)",(elem["id"], CHAT_ID, elem["titre"], timestamp, elem["note"], elem["Days"]))
        conn.commit()
        conn.close()
        date=datetime.fromtimestamp(timestamp)
        times=list_time(date)
        await inject_in_db_notification(times,tache_id,title)
        await envoyer_message(f"📝 la tache N°{tache_id} est ajouter")
        
    elif elem["commande"]=="rename":
        id_tache=elem["id"]
        conn=psycopg2.connect(**DB_PARAMS)
        curseur=conn.cursor()
        curseur.execute("UPDATE taches SET titre=%s WHERE id =%s;",(elem["ancien"],id_tache))
        curseur.execute("UPDATE notification SET message=%s WHERE tache_id =%s;",(elem["ancien"],id_tache))
        conn.commit()
        conn.close()
        await envoyer_message(f"📝 la tache N°{tache_id} est sous l'ancien nom")
        
    elif elem["commande"]=="comment":
        id_tache=elem["id"]
        conn=psycopg2.connect(**DB_PARAMS)
        curseur=conn.cursor()
        curseur.execute("UPDATE taches SET note=%s WHERE id =%s;",(elem["ancien"],id_tache))
        conn.commit()
        conn.close()
        await envoyer_message(f"📝 la tache N°{tache_id} est sous l'ancien nom")

async def trait_tache(texte:str):
    texte=texte.strip()
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
            subprocess.Popen([sys.executable, "daily_launcher.py"])
        except Exception as e:
            await envoyer_message(f"❌ Erreur lors du lancement : {e}")
            
    elif commande=="/rename" or commande=="rename":
        values=get_elem_id(texte)
        if values[0]:
            id_tache,new_name=values[1],values[2]
            try:
                conn=psycopg2.connect(**DB_PARAMS)
                curseur=conn.cursor()
                curseur.execute("SELECT * FROM taches WHERE id = %s",(id_tache,))
                res=curseur.fetchone()
                if res:
                    elem={"commande":"rename","id":id_tache,'ancien':res[2]}
                    PILE.add(elem)
                    curseur.execute("UPDATE taches SET titre=%s WHERE id =%s;",(new_name,id_tache))
                    curseur.execute("UPDATE notification SET message=%s WHERE tache_id =%s;",(new_name,id_tache))
                conn.commit()
                conn.close()

                await envoyer_message(f"✅ La tâche N°{id_tache} a bien été renommée en : {new_name}")
            except Error as e:
                print(f"Erreur SQL : {e}")
                await envoyer_message(f"❌ Une erreur SQL s'est produite lors du renommage.")
        else:
           await envoyer_message(f"❌ Une erreur s'est produite : {values[1]}")
           
    elif commande=="/comment" or commande=="comment":
        values=get_elem_id(texte)
        if values[0]:
            id_tache,new_note=values[1],values[2]
            try:
                conn=psycopg2.connect(**DB_PARAMS)
                curseur=conn.cursor()
                curseur.execute("SELECT * FROM taches WHERE id = %s",(id_tache,))
                res=curseur.fetchone()        
                if res:
                    elem={"commande":"comment","id":id_tache,'ancien':res[4]}
                    PILE.add(elem)
                curseur.execute("UPDATE taches SET note=%s WHERE id =%s;",(new_note,id_tache))
                conn.commit()
                conn.close()
                await envoyer_message(f"✅ le commenetaire :({new_note}) est bien ajouter a la tâche N°{id_tache}")        
            except Error as e:
                print(f"Erreur SQL : {e}")
                await envoyer_message(f"❌ Une erreur SQL s'est produite lors d'ajout du commantaire.")
        else:
            await envoyer_message(f"❌ Une erreur s'est produite : {values[1]}")
            
    elif commande=="/help" or commande=="help":
        #{a: tout meme supprimer,n:pour le nombre des element,f:pour ce qui est fini,c:pour les commantire}
        help_text = (
                    " <b>Assistant de Tâches - Guide des Commandes</b>\n\n"
                    "✨ <b>Gestion des tâches :</b>\n"
                    "• <code>/add Titre, JJ/MM [HH:mm], [Note]</code>\n"
                    "  <i>Ex: /add Acheter du pain, 25/12 18:00, Boulangerie fermée le lundi</i>\n"
                    #"• /add \[-flag\] \[nombre\] Titre, JJ/MM \[HH:mm\], \[Note\]"
                    #"Nb de base =30"
                    #"       -h : hourly chaque heure"
                    #"       -d : daily chaque jour"
                    #"       -w : weekly chaque semaine"
                    #"       -m : monthly chaque mois"
                    #s"       -y : yearly chaque année (ou par an"
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
                    "💡 <i>Note : Si vous ne précisez pas d'heure, 23:59 est utilisé par défaut.</i>"
                )
        await envoyer_message(help_text)
    
    else:
        await envoyer_message("commande inconnue. Tapez /help pour voir la liste.")

async def verification_periodique(context: ContextTypes.DEFAULT_TYPE):
    date_actue = datetime.now()
    timestamp_actuel = int(date_actue.timestamp())
    conn = None
    try:
        conn = psycopg2.connect(**DB_PARAMS)
        curseur = conn.cursor()
        curseur.execute("SELECT * FROM notification WHERE date_to_send <= %s AND envoye=0", (timestamp_actuel,))
        resultats = curseur.fetchall()
        if resultats:
            for row in resultats:
                notif_id = row[0]
                message_texte = f"{row[3]} expire dans {row[4]}"
                await context.bot.send_message(chat_id=CHAT_ID, text=f"⏳ RAPPEL : {message_texte}")
                curseur.execute("UPDATE notification SET envoye = 1 WHERE id = %s", (notif_id,))
                conn.commit()
                print(f"Message '{message_texte}' envoye et marque comme fait.")
    except Error as e:
        print(f"Erreur SQL : {e}")
    finally:
        if conn:
            conn.close()

def start():
    print("Demarrage du bot...")
    app = Application.builder().token(TOKEN).post_init(post_init).build()
    
    app.add_handler(MessageHandler(filters.TEXT, cerveaux))
    
    job_queue = app.job_queue
    job_queue.run_repeating(verification_periodique, interval=60, first=10)
    print("Bot prêt ! Lancement du polling...")
    
    app.run_polling(drop_pending_updates=True)

if __name__=="__main__":
    print("import fini")
    print("db fini")
    start()
    print("start fini")