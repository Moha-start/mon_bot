import caldav
from datetime import datetime, timedelta
import pytz

# --- CONFIGURATION ---
NEXTCLOUD_URL = "https://linux-moha.tailc6cfda.ts.net/remote.php/dav/principals/users/Mohamed/"
USERNAME = "Mohamed"
PASSWORD = "LFzY8-9g8cd-4CSb9-qF2k5-Dfjxg"

# IMPORTANT : Laisse True pour tester. Mets False pour supprimer réellement.
DRY_RUN = True 
# ---------------------

def get_event_details(event):
    """Extrait les détails utiles d'un événement."""
    try:
        vevent = event.vobject_instance.vevent
        uid = vevent.uid.value
        summary = vevent.summary.value if hasattr(vevent, 'summary') else "Sans titre"
        
        dtstart = vevent.dtstart.value
        
        # Gestion de la durée
        if hasattr(vevent, 'dtend'):
            dtend = vevent.dtend.value
            # Si c'est des dates sans heure (all day), on convertit pour le calcul
            if not isinstance(dtstart, datetime):
                duration = dtend - dtstart # timedelta simple pour les dates
            else:
                duration = dtend - dtstart
        elif hasattr(vevent, 'duration'):
            duration = vevent.duration.value
        else:
            # Durée par défaut si non spécifiée (0)
            duration = timedelta(minutes=0)

        return {
            "obj": event,
            "uid": uid,
            "summary": summary,
            "start": dtstart,
            "duration": duration
        }
    except Exception as e:
        print(f"Erreur de lecture d'un événement: {e}")
        return None

def clean_calendar(calendar):
    print(f"\n--- Analyse du calendrier : {calendar.name} ---")
    events = calendar.events()
    
    # Dictionnaire pour grouper par date de début
    # Clé = date_debut, Valeur = liste d'événements
    events_by_start = {}

    for event in events:
        details = get_event_details(event)
        if not details:
            continue
            
        start_key = details['start']
        
        if start_key not in events_by_start:
            events_by_start[start_key] = []
        events_by_start[start_key].append(details)

    # Analyse des doublons
    for start_time, event_list in events_by_start.items():
        if len(event_list) > 1:
            print(f"-> Conflit détecté à : {start_time} ({len(event_list)} événements)")
            
            # On trie la liste par durée (du plus long au plus court)
            # Si les durées sont égales, le premier trouvé reste
            event_list.sort(key=lambda x: x['duration'], reverse=True)
            
            winner = event_list[0]
            losers = event_list[1:]
            
            print(f"   [GARDÉ] '{winner['summary']}' (Durée: {winner['duration']})")
            
            for loser in losers:
                print(f"   [À SUPPRIMER] '{loser['summary']}' (Durée: {loser['duration']})")
                
                if not DRY_RUN:
                    try:
                        loser['obj'].delete()
                        print("      -> Supprimé avec succès.")
                    except Exception as e:
                        print(f"      -> Erreur suppression: {e}")
                else:
                    print("      -> (Simulation : suppression ignorée)")

def main():
    try:
        client = caldav.DAVClient(
            url=NEXTCLOUD_URL,
            username=USERNAME,
            password=PASSWORD
        )
        principal = client.principal()
        calendars = principal.calendars()

        if not calendars:
            print("Aucun calendrier trouvé.")
            return

        for calendar in calendars:
            clean_calendar(calendar)

    except Exception as e:
        print(f"Erreur de connexion ou d'exécution : {e}")

if __name__ == "__main__":
    main()