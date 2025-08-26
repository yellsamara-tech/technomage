from flask import Flask
import threading
import requests
import time
import os

app = Flask(__name__)
BOT_URL = os.getenv("PING_URL")  # сюда можно поставить любой URL, который доступен

def ping_loop():
    while True:
        try:
            if BOT_URL:
                requests.get(BOT_URL)
                print("Ping sent ✅")
        except Exception as e:
            print("Ping failed:", e)
        time.sleep(10 * 60)  # каждые 10 минут

@app.route("/")
def index():
    return "Bot ping server is running."

if __name__ == "__main__":
    threading.Thread(target=ping_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
