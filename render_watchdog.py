"""
ВНЕШНИЙ WATCHDOG для Render.com
Деплой: 
1. Создай репо на GitHub с этим файлом
2. На Render.com: New -> Web Service -> подключи репо
3. Build Command: pip install requests
4. Start Command: python watchdog.py
"""

import time
import requests
from datetime import datetime
import os

# --- CONFIG (через Environment Variables на Render) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'ТОКЕН_ВТОРОГО_БОТА')
CHAT_ID = os.environ.get('CHAT_ID', 'ТВОЙ_CHAT_ID')
SERVER_IP = os.environ.get('SERVER_IP', '192.168.1.XXX')  # или внешний IP если есть
CHECK_INTERVAL = int(os.environ.get('CHECK_INTERVAL', '60'))  # секунд

def send_alert(text):
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        requests.post(url, json={'chat_id': CHAT_ID, 'text': text, 'parse_mode': 'HTML'}, timeout=10)
        print(f'[{datetime.now()}] Alert sent: {text[:50]}...')
    except Exception as e:
        print(f'Failed to send alert: {e}')

def check_server():
    """Проверяем доступность через HTTP запрос (можно добавить endpoint на приставке)"""
    try:
        # Если у тебя есть открытый порт с каким-то веб-сервисом
        response = requests.get(f'http://{SERVER_IP}:8000/ping', timeout=5)
        return response.status_code == 200
    except:
        return False

def check_server_telegram():
    """
    ХИТРЫЙ СПОСОБ: проверяем через Telegram API
    Приставка каждые 2 мин отправляет /heartbeat боту
    Мы проверяем, когда был последний апдейт
    """
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates'
        resp = requests.get(url, timeout=10)
        data = resp.json()
        
        if data.get('ok') and data.get('result'):
            last_update = data['result'][-1]
            last_time = last_update['message']['date']
            now = datetime.now().timestamp()
            
            # Если последнее сообщение старше 5 минут - сервер мертв
            if now - last_time > 300:  # 5 минут
                return False
            return True
        return False
    except Exception as e:
        print(f'Check failed: {e}')
        return False

def main():
    print(f'Watchdog started. Monitoring {SERVER_IP} every {CHECK_INTERVAL}s...')
    
    last_status = None
    down_since = None
    alert_sent = False
    
    while True:
        is_alive = check_server_telegram()  # или check_server() если есть HTTP endpoint
        now = datetime.now()
        
        if is_alive:
            if last_status == False and alert_sent:  # Восстановилась!
                downtime = int((now - down_since).total_seconds() / 60)
                send_alert(f'''✅ <b>SERVER RECOVERED!</b>

⏱ Downtime: {downtime} minutes
🕐 {now.strftime("%Y-%m-%d %H:%M:%S")}
🌐 IP: {SERVER_IP}''')
                print(f'[{now}] ✅ Server back online (downtime: {downtime}min)')
                alert_sent = False
            down_since = None
            
        else:
            if last_status == True or (last_status is None and not alert_sent):
                send_alert(f'''🔴 <b>SERVER DOWN!</b>

⚠️ Server unreachable
🌐 IP: {SERVER_IP}
🕐 {now.strftime("%Y-%m-%d %H:%M:%S")}

<i>Will notify when back online...</i>''')
                down_since = now
                alert_sent = True
                print(f'[{now}] 🔴 Server down!')
        
        last_status = is_alive
        time.sleep(CHECK_INTERVAL)

if __name__ == '__main__':
    main()
