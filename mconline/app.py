from flask import Flask, jsonify
import requests
import os
import logging
from dotenv import load_dotenv
import datetime
import platform
import socket
import pytz  # 添加 pytz 库

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Global variables
online_timestamp = None
hostname = socket.gethostname()
system_info = platform.system() + " " + platform.release()
china_timezone = pytz.timezone('Asia/Shanghai')  # 定义东八区时区

# Telegram Bot Configuration
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")

@app.route('/online')
def online():
    """Record system coming online and send notification"""
    global online_timestamp
    online_timestamp = datetime.datetime.now(china_timezone)  # 使用东八区时区
    
    # Enhanced message (without hostname and system info)
    message = f"🟢 *大瑶 上线*\n\n" \
              f"🕒 *时间*: {online_timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    try:
        response = send_telegram_message(message)
        if response.get('ok'):
            app.logger.info(f"Online notification sent successfully")
            return jsonify({
                "status": "success", 
                "message": "Online notification sent",
                "timestamp": online_timestamp.strftime("%Y-%m-%d %H:%M:%S")
            })
        else:
            app.logger.error(f"Failed to send online notification: {response}")
            return jsonify({"status": "error", "message": "Notification send failed", "details": response}), 500
    except Exception as e:
        app.logger.error(f"Online notification exception: {str(e)}")
        return jsonify({"status": "error", "message": "Notification send exception", "details": str(e)}), 500

@app.route('/offline')
def offline():
    """Record system going offline and calculate uptime"""
    global online_timestamp
    offline_timestamp = datetime.datetime.now(china_timezone)  # 使用东八区时区
    
    # Calculate uptime
    if online_timestamp:
        time_diff = offline_timestamp - online_timestamp
        hours, remainder = divmod(time_diff.total_seconds(), 3600)
        minutes, remainder = divmod(remainder, 60)
        seconds = int(remainder)
        
        uptime_str = f"{int(hours)}小时 {int(minutes)}分钟 {seconds}秒"
        online_time_str = online_timestamp.strftime("%Y-%m-%d %H:%M:%S")
    else:
        uptime_str = "未知"
        online_time_str = "未记录"
    
    offline_time_str = offline_timestamp.strftime("%Y-%m-%d %H:%M:%S")
    
    # Enhanced message with better formatting (without hostname and system info)
    message = f"🔴 *大瑶 下线*\n\n" \
              f"⬆️ *上线时间*: {online_time_str}\n" \
              f"⬇️ *下线时间*: {offline_time_str}\n" \
              f"⏱️ *在线时长*: {uptime_str}"
    
    try:
        response = send_telegram_message(message)
        if response.get('ok'):
            app.logger.info(f"Offline notification sent successfully")
            return jsonify({
                "status": "success", 
                "message": "Offline notification sent",
                "online_at": online_time_str,
                "offline_at": offline_time_str,
                "uptime": uptime_str
            })
        else:
            app.logger.error(f"Failed to send offline notification: {response}")
            return jsonify({"status": "error", "message": "Notification send failed", "details": response}), 500
    except Exception as e:
        app.logger.error(f"Offline notification exception: {str(e)}")
        return jsonify({"status": "error", "message": "Notification send exception", "details": str(e)}), 500

def send_telegram_message(message):
    """Send message to Telegram with markdown formatting"""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    return response.json()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5007, debug=True)