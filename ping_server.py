from flask import Flask
import threading, requests, time, os
import sys

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
    threading.Thread(target=self_ping, daemon=True).start()

    # --- вот эта часть ---
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5001
    app.run(host="0.0.0.0", port=port)
