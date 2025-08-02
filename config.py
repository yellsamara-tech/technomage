import os
from dotenv import load_dotenv
import pytz

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
EMAIL_LOGIN = os.getenv("EMAIL_LOGIN")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Самарское время (UTC+4)
TIMEZONE = pytz.timezone("Europe/Samara")
