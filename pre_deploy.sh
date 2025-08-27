#!/bin/bash
# Удаляем старый Webhook перед деплоем
curl -s -X POST "https://api.telegram.org/bot$BOT_TOKEN/deleteWebhook"
echo "Webhook удален"
