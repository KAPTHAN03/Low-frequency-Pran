import datetime
import requests
import json
import time
import numpy as np
import pandas as pd
from geopy.distance import geodesic

# ===================================================
# 📌 ตั้งค่าบัญชี LINE Messaging API และเกณฑ์ตรวจเมฆ
# ===================================================
LINE_CHANNEL_ACCESS_TOKEN = "jwuHwu0W0GBSfDCbjl22PoAOtAJLkLn/tb5UPKakL3bsU2c5cVzoWicH9aWqkNn7rZzylZjlw86vtlcbA3ggg11mAYDi45oFOHru6OXbL8Q3Oyo1HkYFdNe3oQV4louWJz1G/icXJ0LTFCmZqQk9vQdB04t89/1O/w1cDnyilFU="
LINE_USER_ID = "Ubd5b155e64f586825a02d6556d5ad3f2"

TARGET_LAT = 12.470361
TARGET_LON = 99.792917
RADIUS_KM = 5.0
CLOUD_THRESHOLD = 0.0  # 0.0 เพื่อบังคับให้ไลน์รายงานครบทุกทิศทันทีในการทดสอบระบบ

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
            print("🚀 ส่งแจ้งเตือนพิกัดเข้า LINE สำเร็จ!", flush=True)
        else:
            print(f"❌ ส่งไลน์ล้มเหลว: {response.status_code} - {response.text}", flush=True)
    except Exception as e:
        print(f"❌ Line Error: {e}", flush=True)

# 🗺️ สร้างพิกัด: Center 1 จุด + (8 ทิศทาง x ทิศละ 2 จุดตรวจที่ระยะ 2.5 กม. และ 5.0 กม.) = รวม 17 จุด
def generate_radar_points(lat, lon, max_dist_km):
    center = (lat, lon)
    # จัดรูปโครงสร้าง Dictionary ทิศทางให้ปิดปีกกาอย่างสมบูรณ์แบบกระชับ
    directions = {"N (เหนือ)": 0, "NE (ตะวันออกเฉียงเหนือ)": 45, "E (ตะวันออก)": 90, "SE (ตะวันออกเฉียงใต้)": 135, "S (ใต้)": 180, "SW (ตะวันตกเฉียงใต้)": 225, "W (ตะวันตก)": 270, "NW (ตะวันตกเฉียงเหนือ)": 315}
    
    points = []
    points.append({"lat": lat, "lon": lon, "label": "Center (พิกัดหลัก)"})
    
    for label, bearing in directions.items():
        dist_half = max_dist_km / 2.0
        dest_half = geodesic(kilometers=dist_half).destination(center, bearing)
        dest_full = geodesic(kilometers=max_dist_km).destination(center, bearing)
        
        points.append({"lat": dest_half.latitude, "lon": dest_half.longitude, "label": label})
        points.append({"lat": dest_full.latitude, "lon": dest_full.longitude, "label": label})
        
    return points

print("🤖 บอทตรวจเม
