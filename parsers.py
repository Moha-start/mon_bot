import re
from datetime import datetime, time as Time
from dateutil.relativedelta import relativedelta

def get_command(texte: str) -> tuple[str, str]:
    texte.strip()
    texte += " "
    index = 0
    size = len(texte)
    first = ""
    while index < size and texte[index] != " ":
        first += texte[index]
        index += 1
    return first.lower(), texte[index+1:]

def get_entry_title(texte: str) -> tuple[str, str]:
    new = ""
    index = 0
    size = len(texte)
    while index < size and texte[index] != ",":
        new += texte[index]
        index += 1
    return new, texte[index+1:]

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

def get_days(date: datetime):
    if isinstance(date, (int, float)):
        date = datetime.fromtimestamp(date)
    jours = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
    return jours[date.weekday()]

def get_commanter(texte: str) -> str:
    size = len(texte)
    index = 0
    while index < size and texte[index] != ",":
        index += 1
    if size == 0: return " "
    else: return texte[:index]

def est_dans_la_tranche(dt_a_tester: datetime):
    h_debut = Time(22, 0)
    h_fin = Time(6, 0)
    t = dt_a_tester.time()
    if h_debut <= h_fin: return h_debut <= t <= h_fin
    else: return t >= h_debut or t <= h_fin

def clean_past_times(times: list) -> list:
    date_aujourdhui = datetime.now()
    timestamp_actuel = int(date_aujourdhui.timestamp())
    table = []
    for dt_obj, label in times:
        ts = int(dt_obj.timestamp())
        if ts > timestamp_actuel: table.append((ts, label))
    return table

def list_time(time: datetime) -> list:
    times = []
    times.append((time, "Now"))
    for i in range(1, 11): times.append((time-relativedelta(minutes=i), f"{i} minutes"))
    times.extend([
        (time-relativedelta(minutes=15), "15 minutes"),
        (time-relativedelta(minutes=20), "20 minutes"),
        (time-relativedelta(minutes=25), "25 minutes"),
        (time-relativedelta(minutes=30), "30 minutes"),
        (time-relativedelta(minutes=45), "45 minutes"),
        (time-relativedelta(hours=1), "1 Heure"),
        (time-relativedelta(minutes=90), "1:30 Heures")
    ])
    for i in range(2, 7): times.append((time-relativedelta(hours=i), f"{i} Heures"))
    times.append((time-relativedelta(hours=12), "12 Heures"))
    tranche = est_dans_la_tranche(time)

    base = time - relativedelta(hours=12) if tranche else time
    for i in range(1, 7): times.append((base-relativedelta(days=i), f"{i} Joures"))
    for i in range(1, 5): times.append((base-relativedelta(weeks=i), f"{i} Semaines"))
    for i in range(1, 4): times.append((base-relativedelta(months=i), f"{i} Mois"))

    times.reverse()
    return clean_past_times(times)

def list_times_flags(time: datetime, number: int = 30, flag: str = 'e'):
    times = []
    for i in range(1, 11): times.append((time - relativedelta(minutes=i), f"{i} minutes"))
    times.extend([
        (time - relativedelta(minutes=15), "15 minutes"), (time - relativedelta(minutes=20), "20 minutes"),
        (time - relativedelta(minutes=25), "25 minutes"), (time - relativedelta(minutes=30), "30 minutes"),
        (time - relativedelta(minutes=45), "45 minutes"), (time - relativedelta(hours=1), "1 Heure"),
        (time - relativedelta(minutes=90), "1:30 Heures")
    ])
    tranche = est_dans_la_tranche(time)
    
    if flag == 'h':
        for i in range(2, number + 1): times.append((time - relativedelta(hours=i), f"{i} Heures"))
    elif flag == 'd':
        for i in range(2, 7): times.append((time - relativedelta(hours=i), f"{i} Heures"))
        times.append((time - relativedelta(hours=12), "12 Heures"))
        base_time = time - relativedelta(hours=12) if tranche else time
        for i in range(2, number + 1): times.append((base_time - relativedelta(days=i), f"{i} Jours"))
    elif flag == 'w':
        for i in range(2, 7): times.append((time - relativedelta(hours=i), f"{i} Heures"))
        times.append((time - relativedelta(hours=12), "12 Heures"))
        times.append((time - relativedelta(days=1), "1 Jour"))
        base_time = time - relativedelta(hours=12) if tranche else time
        for i in range(2, number + 1): times.append((base_time - relativedelta(weeks=i), f"{i} Semaines"))
    elif flag == 'm':
        for i in range(2, 7): times.append((time - relativedelta(hours=i), f"{i} Heures"))
        times.append((time - relativedelta(hours=12), "12 Heures"))
        times.append((time - relativedelta(days=1), "1 Jour"))
        base_time = time - relativedelta(hours=12) if tranche else time
        for i in range(2, number + 1): times.append((base_time - relativedelta(months=i), f"{i} Mois"))
    return clean_past_times(times)

def get_number_flag(texte: str):
    index = 0
    texte = texte.strip()
    res = ''
    size = len(texte)
    if not texte or not texte[index].isdecimal():
        return "", texte
    while index < size and texte[index].isdecimal():
        res += texte[index]
        index += 1
    try: res = int(res)
    except: pass
    return res, texte[index:]

def get_flags(texte: str):
    texte = texte.strip()
    index = 0
    size = len(texte)
    flags = []
    if texte and texte[0] == "-":
        index += 1
        while index < size and texte[index] != " ":
            flags.append(texte[index].lower())
            index += 1
    return flags, index

def get_list_ids(texte: str):
    ids = []
    curent = ""
    size = len(texte)
    index = 0
    while index < size:
        elem = texte[index]
        if elem != " " and elem != ",":
            curent += elem
        elif elem == ",":
            if curent.isdigit():
                ids.append(int(curent))
                curent = ""
        index += 1
    if curent.isdigit(): ids.append(int(curent))
    return ids

def get_elem_id(text: str):
    text = text.strip()
    id_tache = ''
    index = 0
    size = len(text)
    while index < size and text[index].isalnum():
        id_tache += text[index]
        index += 1
    index += 1
    try:
        return True, int(id_tache), text[index:]
    except ValueError as e:
        return False, e