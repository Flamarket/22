"""
WATCHDOG SERVER для Render.com
Принимает heartbeat'ы от приставки и мониторит её статус
"""

from flask import Flask, request, jsonify
import threading
import time
import requests
from datetime import datetime
import os

app = Flask(__name__)

# --- CONFIG (заполни в Environment Variables на Render) ---
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')
SERVER_NAME = os.environ.get('SERVER_NAME', 'TV Box Server')
ALERT_TIMEOUT = int(os.environ.get('ALERT_TIMEOUT', '300'))  # 5 минут без heartbeat = алерт

# Состояние
last_heartbeat = None
server_was_down = False
heartbeat_data = {}

def send_telegram(text):
    """Отправка сообщения в Telegram"""
    try:
        url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
        requests.post(url, json={
            'chat_id': CHAT_ID,
            'text': text,
            'parse_mode': 'HTML'
        }, timeout=10)
        print(f'[{datetime.now()}] Telegram sent: {text[:50]}...')
    except Exception as e:
        print(f'Failed to send telegram: {e}')

@app.route('/')
def home():
    """Главная страница - показывает статус"""
    global last_heartbeat, heartbeat_data
    
    if last_heartbeat:
        elapsed = int((datetime.now().timestamp() - last_heartbeat))
        status = '🟢 ONLINE' if elapsed < ALERT_TIMEOUT else '🔴 OFFLINE'
        last_seen = datetime.fromtimestamp(last_heartbeat).strftime('%Y-%m-%d %H:%M:%S')
    else:
        status = '⚪ WAITING'
        last_seen = 'Never'
        elapsed = 0
    
    html = f'''
    <html>
    <head>
        <title>Server Monitor</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body {{ font-family: monospace; padding: 20px; background: #1a1a1a; color: #0f0; }}
            .status {{ font-size: 24px; margin: 20px 0; }}
            .info {{ margin: 10px 0; }}
        </style>
    </head>
    <body>
        <h1>🛡 {SERVER_NAME} Monitor</h1>
        <div class="status">Status: {status}</div>
        <div class="info">📡 Last Heartbeat: {last_seen}</div>
        <div class="info">⏱ Elapsed: {elapsed}s ago</div>
        <div class="info">⚙️ Data: {heartbeat_data}</div>
        <hr>
        <small>Auto-refresh every 10s</small>
    </body>
    </html>
    '''
    return html

@app.route('/heartbeat', methods=['POST', 'GET'])
def heartbeat():
    """Принимаем heartbeat от приставки"""
    global last_heartbeat, server_was_down, heartbeat_data
    
    now = datetime.now().timestamp()
    last_heartbeat = now
    
    # Сохраняем данные от приставки
    if request.method == 'POST':
        heartbeat_data = request.get_json() or {}
    else:
        heartbeat_data = dict(request.args)
    
    # Если сервер был down - уведомляем о восстановлении
    if server_was_down:
        send_telegram(f'''✅ <b>SERVER RECOVERED!</b>

🖥 {SERVER_NAME}
🕐 {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
📊 {heartbeat_data}

<i>Server is back online!</i>''')
        server_was_down = False
        print(f'[{datetime.now()}] ✅ Server recovered')
    
    print(f'[{datetime.now()}] 💓 Heartbeat received: {heartbeat_data}')
    return jsonify({'status': 'ok', 'timestamp': now})

def monitor_thread():
    """Фоновый поток - проверяет таймауты"""
    global last_heartbeat, server_was_down
    
    while True:
        time.sleep(30)  # проверяем каждые 30 секунд
        
        if last_heartbeat:
            elapsed = datetime.now().timestamp() - last_heartbeat
            
            # Если давно не было heartbeat'а и алерт еще не отправлен
            if elapsed > ALERT_TIMEOUT and not server_was_down:
                send_telegram(f'''🔴 <b>SERVER DOWN!</b>

🖥 {SERVER_NAME}
⚠️ No heartbeat for {int(elapsed/60)} minutes
🕐 Last seen: {datetime.fromtimestamp(last_heartbeat).strftime("%Y-%m-%d %H:%M:%S")}

<i>Waiting for recovery...</i>''')
                server_was_down = True
                print(f'[{datetime.now()}] 🔴 Server down alert sent')

if __name__ == '__main__':
    # Запускаем фоновый монитор
    monitor = threading.Thread(target=monitor_thread, daemon=True)
    monitor.start()
    
    print(f'🚀 Watchdog server starting...')
    print(f'⏱ Alert timeout: {ALERT_TIMEOUT}s')
    
    # Render.com требует слушать на порту из переменной PORT
    port = int(os.environ.get('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
