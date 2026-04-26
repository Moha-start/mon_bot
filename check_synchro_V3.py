import caldav
import requests
from icalendar import Calendar
from datetime import datetime, date, timedelta
import pytz
import json
import os

# =============================================================================
# CONFIGURATION
# =============================================================================
NC_URL = "https://linux-moha.tailc6cfda.ts.net/remote.php/dav/principals/users/Mohamed/"
NC_USER = "Mohamed"
NC_PASS = "LFzY8-9g8cd-4CSb9-qF2k5-Dfjxg"
URL_ICS = "https://mescalendriers.u-bordeaux.fr/ics/ab94a7d112f4f9e2e87bf271f7d0d6d6"
FICHIER_JSON = "historique_modifications.json"

CALENDRIERS_GERES = ["TD Machine","Examain","Examen TD Machine","Orales","TD","Cours","Cours/TD"]
# =============================================================================

def get_now_utc():
    return datetime.now(pytz.utc).replace(hour=0, minute=0, second=0, microsecond=0)

def normaliser_date(dt):
    if dt is None: return None
    if type(dt) is date:
        dt = datetime.combine(dt, datetime.min.time())
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    return dt.astimezone(pytz.utc)

def generer_signature(titre, dt_debut):
    titre_clean = str(titre).strip().lower()
    date_clean = normaliser_date(dt_debut).strftime("%Y-%m-%d %H:%M")
    return f"{titre_clean}|{date_clean}"

def nettoyer_description(desc):
    if not desc: return ""
    d = str(desc).strip().lower()
    d = d.replace('\n', ' ').replace('\r', '').replace('\\n', ' ')
    while '  ' in d:
        d = d.replace('  ', ' ')
    return d

def extraire_nom_calendrier_cible(description):
    if not description: return None
    lines = description.strip().splitlines()
    return lines[0].strip() if lines else None

def enregistrer_log_json(action, details):
    """ Enregistre une action avec des données complètes pour historique/rollback """
    logs = []
    if os.path.exists(FICHIER_JSON):
        try:
            with open(FICHIER_JSON, 'r', encoding='utf-8') as f:
                logs = json.load(f)
        except: pass
    
    log_entry = {
        "date_action": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "type": action,
        "evenement": details
    }
    logs.append(log_entry)
    with open(FICHIER_JSON, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=4, ensure_ascii=False, default=str)

def mettre_a_jour_desc_event(caldav_event, nouvelle_description):
    cal_data = Calendar.from_ical(caldav_event.data)
    for component in cal_data.walk('VEVENT'):
        component['DESCRIPTION'] = nouvelle_description
    caldav_event.data = cal_data.to_ical()
    caldav_event.save()

def ajouter_evenement(calendrier_obj, data_ics):
    try:
        calendrier_obj.save_event(
            dtstart=data_ics['debut'],
            dtend=data_ics['fin'],
            summary=data_ics['titre'],
            location=data_ics['lieu'],
            description=data_ics['desc_ics_raw']
        )
        return True
    except Exception as e:
        print(f"❌ Erreur création event : {e}")
        return False

def synchroniser_intelligent():
    print("--- Démarrage Synchro Intelligente + Logs Précis ---")
    date_limite = get_now_utc()
    
    try:
        client = caldav.DAVClient(url=NC_URL, username=NC_USER, password=NC_PASS)
        principal = client.principal()
        calendars = {cal.get_properties([caldav.dav.DisplayName()])['{DAV:}displayname']: cal 
                     for cal in principal.calendars()}
    except Exception as e:
        print(f"❌ Erreur Connexion : {e}")
        return

    # 2. Téléchargement ICS
    try:
        r = requests.get(URL_ICS)
        r.raise_for_status()
        cal_ics_data = Calendar.from_ical(r.content)
    except Exception as e:
        print(f"❌ Erreur ICS : {e}")
        return

    # 3. Analyse ICS
    events_ics = {}
    for ev in cal_ics_data.walk('VEVENT'):
        dt_start = ev.get('dtstart').dt
        if normaliser_date(dt_start) < date_limite: continue

        titre = str(ev.get('summary', ''))
        sig = generer_signature(titre, dt_start)
        events_ics[sig] = {
            'titre': titre,
            'debut': dt_start,
            'fin': ev.get('dtend').dt if ev.get('dtend') else dt_start + timedelta(hours=1),
            'lieu': str(ev.get('location', '')),
            'desc_raw': str(ev.get('description', '')),
            'desc_clean': nettoyer_description(str(ev.get('description', ''))),
            'nom_cal_cible': extraire_nom_calendrier_cible(str(ev.get('description', ''))),
            'trouve_sur_nc': False
        }

    # 4. Scan Nextcloud (Modifs et Suppressions)
    nb_updates = 0; nb_suppr = 0; nb_ajouts = 0
    print("🔍 Analyse de vos calendriers...")

    for cal_name, cal_obj in calendars.items():
        try:
            events = cal_obj.date_search(start=date_limite, end=date_limite.replace(year=date_limite.year+1))
            for ev_obj in events:
                comp = Calendar.from_ical(ev_obj.data).walk('VEVENT')[0]
                t = str(comp.get('summary', ''))
                d = comp.get('dtstart').dt
                sig_nc = generer_signature(t, d)
                
                if sig_nc in events_ics:
                    # L'événement existe : on check la description
                    target = events_ics[sig_nc]
                    target['trouve_sur_nc'] = True
                    desc_nc_raw = str(comp.get('description', ''))
                    
                    if target['desc_clean'] != nettoyer_description(desc_nc_raw):
                        print(f"✏️  MàJ description : {t}")
                        mettre_a_jour_desc_event(ev_obj, target['desc_raw'])
                        # LOG PRÉCIS
                        enregistrer_log_json("MISE_A_JOUR", {
                            "titre": t, "date": d, "calendrier": cal_name,
                            "ancienne_description": desc_nc_raw,
                            "nouvelle_description": target['desc_raw']
                        })
                        nb_updates += 1
                
                elif cal_name in CALENDRIERS_GERES:
                    # L'événement n'est plus dans l'ICS : on supprime
                    print(f"🗑️  Suppression : {t}")
                    # LOG PRÉCIS AVANT SUPPRESSION
                    enregistrer_log_json("SUPPRESSION", {
                        "titre": t, "debut": d, 
                        "fin": comp.get('dtend').dt if comp.get('dtend') else d,
                        "lieu": str(comp.get('location', '')),
                        "description": str(comp.get('description', '')),
                        "calendrier": cal_name
                    })
                    ev_obj.delete()
                    nb_suppr += 1
        except: pass

    # 5. Ajouts
    for sig, data in events_ics.items():
        if not data['trouve_sur_nc'] and data['nom_cal_cible'] in calendars:
            cal_target = calendars[data['nom_cal_cible']]
            print(f"🆕 Ajout : {data['titre']} -> {data['nom_cal_cible']}")
            if ajouter_evenement(cal_target, data):
                # LOG PRÉCIS DE L'AJOUT
                enregistrer_log_json("AJOUT", {
                    "titre": data['titre'], "debut": data['debut'], "fin": data['fin'],
                    "lieu": data['lieu'], "description": data['desc_raw'],
                    "calendrier": data['nom_cal_cible']
                })
                nb_ajouts += 1

    print(f"\n✅ Synchro finie. Modifs: {nb_updates} | Suppr: {nb_suppr} | Ajouts: {nb_ajouts}")

if __name__ == "__main__":
    synchroniser_intelligent()