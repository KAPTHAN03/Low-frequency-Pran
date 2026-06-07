import datetime
import openmeteo_requests
import pandas as pd
import requests
import json
import time
import numpy as np
from geopy.distance import geodesic
from tenacity import retry, stop_after_attempt, wait_fixed

# ===================================================
# 📌 ตั้งค่าบัญชี LINE Messaging API และเกณฑ์ตรวจเมฆ
# ===================================================
LINE_CHANNEL_ACCESS_TOKEN = "jwuHwu0W0GBSfDCbjl22PoAOtAJLkLn/tb5UPKakL3bsU2c5cVzoWicH9aWqkNn7rZzylZjlw86vtlcbA3ggg11mAYDi45oFOHru6OXbL8Q3Oyo1HkYFdNe3oQV4louWJz1G/icXJ0LTFCmZqQk9vQdB04t89/1O/w1cDnyilFU="
LINE_USER_ID = "Ubd5b155e64f586825a02d6556d5ad3f2"

TARGET_LAT = 12.470361
TARGET_LON = 99.792917
RADIUS_KM = 5.0
CLOUD_THRESHOLD = 0.0  # ตั้งค่าเป็น 0.0 ชั่วครู่เพื่อทดสอบให้กางครบ 8 ทิศ

SUB_LOOP_INTERVAL_SEC = 300  
MAX_RUN_DURATION_SEC = 3000   

def send_line_push(message_text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message_text}]
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            print("🚀 ส่งแจ้งเตือนพิกัด 8 ทิศเข้า LINE สำเร็จ!", flush=True)
        else:
            print(f"❌ ส่งล้มเหลว: {response.status_code} - {response.text}", flush=True)
    except Exception as e:
        print(f"❌ Error: {e}", flush=True)

# ฟังก์ชันสร้างเครือข่ายพิกัดรอบรัศมี 5 กม. เพื่อนำมาคัดแยกตามมุมองศาเรดาร์
def generate_radar_points(lat, lon, max_dist_km):
    center = (lat, lon)
