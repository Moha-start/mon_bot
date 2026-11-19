import os
from dotenv import load_dotenv

load_dotenv()

LOGS_ACTIFS = True

def log(*args, **kwargs):
    if LOGS_ACTIFS:
        print(*args, **kwargs)

# Telegram
TOKEN = os.getenv("TOKEN_TACHE")
INITIAL_CHAT_ID = int(os.getenv("CHAT_ID_TACHE"))

# Base de données
DB_PARAMS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST"),
    "port": int(os.getenv("DB_PORT"))
}

# Instagram & IA
IG_USERNAME = os.getenv("IG_USERNAME")
IG_PASSWORD = os.getenv("IG_PASSWORD")
TARGET_THREAD_ID = os.getenv("TARGET_THREAD_ID")
OTHER_BOT_USERNAME = os.getenv("OTHER_BOT_USERNAME")
MEMORY_FILE = os.getenv("MEMORY_FILE")
AI_API_KEY = os.getenv("AI_API_KEY")