from flask import Flask
import threading
import requests
import time
import os

app = Flask("ping_server")

@app.route("/")
def ping():
    return "OK", 200

def self_ping():
    url = os.getenv("RENDER_EXTERNAL_URL")
    if not url:
        print("RENDER_EXTERNAL_URL не задан")
        return
    while True:
        try:
            requests.get(url)
        except Exception as e:
            print(f"Ошибка ping: {e}")
        time.sleep(600)  # раз в 10 минут

if __name__ == "__main__":
    # Запускаем поток ping
    threading.Thread(target=self_ping, daemon=True).start()
    app.run(host="0.0.0.0", port=5000)
