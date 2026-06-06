import datetime
import openmeteo_requests
import pandas as pd
import requests
import json
import time
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
CLOUD_THRESHOLD = 50.0

# ⏱️ ตั้งค่าให้ลูปย่อยในสคริปต์ตื่นมาเช็คทุก 5 นาที (300 วินาที)
SUB_LOOP_INTERVAL_SEC = 300  
# 🕒 ตั้งเวลารันสูงสุดต่อรอบไว้ที่ 50 นาทีเพื่อให้สอดคล้องกับรอบการจ้างงานของเซิร์ฟเวอร์
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
            print("🚀 ส่งแจ้งเตือนผ่าน LINE บอทสำเร็จ!")
        else:
            print(f"❌ ส่งล้มเหลว: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def get_nearby_coordinates(lat, lon, distance_km):
    center = (lat, lon)
    north = geodesic(kilometers=distance_km).destination(center, 0)
    south = geodesic(kilometers=distance_km).destination(center, 180)
    east = geodesic(kilometers=distance_km).destination(center, 90)
    west = geodesic(kilometers=distance_km).destination(center, 270)
    
    return [
        {"lat": lat, "lon": lon, "label": "Center (พิกัดหลัก)"},
        {"lat": north.latitude, "lon": north.longitude, "label": "North (ทิศเหนือ 5 กม.)"},
        {"lat": south.latitude, "lon": south.longitude, "label": "South (ทิศใต้ 5 กม.)"},
        {"lat": east.latitude, "lon": east.longitude, "label": "East (ทิศตะวันออก 5 กม.)"},
        {"lat": west.latitude, "lon": west.longitude, "
