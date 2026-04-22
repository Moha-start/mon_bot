import caldav

# Ta configuration
NC_URL = "https://linux-moha.tailc6cfda.ts.net/remote.php/dav/principals/users/Mohamed/"
NC_USER = "Mohamed"
NC_PASS = "LFzY8-9g8cd-4CSb9-qF2k5-Dfjxg"

def verifier_noms_calendriers():
    print("⏳ Connexion à Nextcloud...")
    try:
        client = caldav.DAVClient(url=NC_URL, username=NC_USER, password=NC_PASS)
        principal = client.principal()
        calendars = principal.calendars()

        print("\n--- Analyse des noms de calendriers ---")
        print("Note : Regarde bien s'il y a un espace entre le guillemet et le texte.\n")

        if not calendars:
            print("❌ Aucun calendrier trouvé.")
            return

        for cal in calendars:
            # On récupère le nom brut via les propriétés DAV
            props = cal.get_properties([caldav.dav.DisplayName()])
            name = props.get('{DAV:}displayname', 'Nom inconnu')
            
            # Affichage ultra-précis
            print(f'Nom trouvé : -->"{name}"<--')

    except Exception as e:
        print(f"❌ Erreur lors de la récupération : {e}")

if __name__ == "__main__":
    verifier_noms_calendriers()