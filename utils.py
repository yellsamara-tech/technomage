from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from config import ADMIN_EMAIL, EMAIL_LOGIN, EMAIL_PASSWORD
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def get_day_column(day: int) -> str:
    return f"d{day}"

def generate_status_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(
        KeyboardButton("На месте"),
        KeyboardButton("Отпуск"),
        KeyboardButton("Больничный"),
        KeyboardButton("Командировка"),
    )
    keyboard.add(KeyboardButton("/статус"))
    return keyboard

async def send_email_report(rows, report_date):
    message = MIMEMultipart()
    message["From"] = EMAIL_LOGIN
    message["To"] = ADMIN_EMAIL
    message["Subject"] = f"Отчёт за {report_date.strftime('%B %Y')}"

    header = "ID,Таб.номер,ФИО," + ",".join([str(i) for i in range(1, 32)])
    lines = [header]
    for row in rows:
        lines.append(",".join([str(col or "") for col in row]))

    text = "\n".join(lines)

    message.attach(MIMEText(text, "plain"))

    try:
        with smtplib.SMTP_SSL("smtp.yandex.ru", 465) as server:
            server.login(EMAIL_LOGIN, EMAIL_PASSWORD)
            server.sendmail(EMAIL_LOGIN, ADMIN_EMAIL, message.as_string())
    except Exception as e:
        print("Ошибка отправки email:", e)

