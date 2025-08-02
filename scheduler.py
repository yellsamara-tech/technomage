from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from config import TIMEZONE
from utils import send_email_report
from database import get_status_matrix

async def daily_task(bot):
    today = datetime.now(TIMEZONE)
    if today.day == 1:
        # Сохраняем весь предыдущий месяц
        rows = get_status_matrix()
        await send_email_report(rows, today - timedelta(days=1))

async def start_scheduler(bot):
    scheduler = AsyncIOScheduler(timezone=TIMEZONE)
    # Самарское время: 07:00 каждый день
    scheduler.add_job(daily_task, CronTrigger(hour=7, minute=0), kwargs={"bot": bot})
    scheduler.start()

