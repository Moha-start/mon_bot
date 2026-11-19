import os
import json
import time
import requests
from instagrapi import Client
from google import genai
import config
from config import log

ai_client = genai.Client(api_key=config.AI_API_KEY)

def load_memory():
    if not os.path.exists(config.MEMORY_FILE):
        return []
    with open(config.MEMORY_FILE, "r", encoding="utf-8") as f:
        try: return json.load(f)
        except json.JSONDecodeError: return []

def save_message(username, text):
    memory = load_memory()
    memory.append({"sender": username, "message": text})
    with open(config.MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump(memory, f, indent=4)

def clear_memory():
    with open(config.MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f)

def summarize_chat():
    memory = load_memory()
    if not memory: return "Aucun message à résumer."

    chat_transcript = "\n".join([f"{msg['sender']}: {msg['message']}" for msg in memory])
    prompt = f"Fais un résumé très bref de cette conversation de groupe:\n\n{chat_transcript}"

    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            response = ai_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            return response.text
        except Exception as e:
            error_msg = str(e)
            if "503" in error_msg or "UNAVAILABLE" in error_msg.upper():
                log(f"⚠️ Serveur IA surchargé (Tentative {attempt + 1}/{max_retries}). Attente...")
                if attempt < max_retries - 1: time.sleep(retry_delay)
                else: raise Exception("L'IA Gemini est actuellement indisponible.")
            else:
                raise e

def notifier_telegram(message_texte):
    url = f"https://api.telegram.org/bot{config.TOKEN}/sendMessage"
    # Note: On utilise le chat d'origine pour les notifs d'arrière plan
    requests.post(url, json={"chat_id": config.INITIAL_CHAT_ID, "text": message_texte})

def lancer_bot_instagram():
    cl = Client()
    session_file = "/home/mohamed/mon_bot/ig_session.json"
    try:
        if os.path.exists(session_file):
            log("🔄 Chargement session Instagram...")
            cl.load_settings(session_file)
            cl.login(config.IG_USERNAME, config.IG_PASSWORD)
            log("✅ Connecté IG (Session chargée).")
        else:
            cl.login(config.IG_USERNAME, config.IG_PASSWORD)
            cl.dump_settings(session_file)
            log("✅ Connecté IG (Nouvelle session).")
    except Exception as e:
        log(f"❌ Erreur critique IG : {e}")
        return

    user_cache = {}
    last_processed_timestamp = None
    log("🎧 Polling HTTP Instagram Démarré...")

    while True:
        try:
            thread = cl.direct_thread(config.TARGET_THREAD_ID)
            messages = thread.messages
            messages.reverse()

            for msg in messages:
                if last_processed_timestamp is None:
                    last_processed_timestamp = msg.timestamp
                    continue

                if msg.timestamp > last_processed_timestamp:
                    last_processed_timestamp = msg.timestamp
                    if getattr(msg, 'item_type', '') != 'text': continue
                        
                    sender_id = msg.user_id
                    text = msg.text

                    if sender_id not in user_cache:
                        user_cache[sender_id] = cl.user_info(sender_id).username
                    sender_username = user_cache[sender_id]

                    if sender_username == config.OTHER_BOT_USERNAME:
                        log(f"🔄 Résumé en cours...")
                        summary = summarize_chat()
                        notifier_telegram(f"🤖 Résumé Instagram :\n{summary}")
                        clear_memory()
                    else:
                        save_message(sender_username, text)
        except Exception as e:
            log(f"❌ Erreur Polling IG : {e}")
            
        time.sleep(15)
        