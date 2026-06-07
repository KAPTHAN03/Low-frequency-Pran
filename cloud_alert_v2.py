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
CLOUD_THRESHOLD = 0.0  # ตั้งเป็น 0.0 เพื่อทดสอบระบบให้ไลน์เด้งรายงานครบทุกทิศทันที

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
            print("🚀 ส่งแจ้งเตือนพิกัดเข้า LINE สำเร็จ!", flush=True)
        else:
            print(f"❌ ส่งไลน์ล้มเหลว: {response.status_code} - {response.text}", flush=True)
    except Exception as e:
        print(f"❌ Line Error: {e}", flush=True)

# 🗺️ สร้างพิกัด: Center 1 จุด + (8 ทิศทางหลัก x ทิศละ 2 จุดตรวจที่ระยะ 2.5 กม. และ 5.0 กม.) = รวม 17 จุด
def generate_radar_points(lat, lon, max_dist_km):
    center = (lat, lon)
    directions = {
        "N (เหนือ)": 0,
        "NE (ตะวันออกเฉียงเหนือ)": 45,
        "E (ตะวันออก)": 90,
        "SE (ตะวันออกเฉียงใต้)": 135,
        "S (ใต้)": 180,
        "SW (ตะวันตกเฉียงใต้)": 225,
        "W (ตะวันตก)": 270,
        "NW (ตะวันตกเฉียงเหนือ)": 315
    }
    
    points = []
    # 1. พิกัดจุดศูนย์กลาง
    points.append({"lat": lat, "lon": lon, "label": "Center (พิกัดหลัก)"})
    
    # 2. พิกัดรอบตัว ทิศละ 2 ระยะเพื่อนำมาหาค่าเฉลี่ยพื้นที่
    for label, bearing in directions.items():
        dist_half = max_dist_km / 2.0
        dest_half = geodesic(kilometers=dist_half).destination(center, bearing)
        dest_full = geodesic(kilometers=max_dist_km).destination(center, bearing)
        
        points.append({"lat": dest_half.latitude, "lon": dest_half.longitude, "label": label})
        points.append({"lat": dest_full.latitude, "lon": dest_full.longitude, "label": label})
        
    return points

start_script_time = time.time()
print("🤖 บอทตรวจเมฆ 8 ทิศ (สูตรคำนวณเฉลี่ย 2 จุดตรวจ/ทิศ) เริ่มทำงาน...", flush=True)

while True:
    if time.time() - start_script_time > MAX_RUN_DURATION_SEC:
        print("🔄 ครบระยะเวลาโควตารอบใหญ่ ปิดตัวเพื่อส่งไม้ต่อรอบถัดไป", flush=True)
        break

    current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    current_hour = current_time.hour  
    
    print(f"\n🕒 รอบตรวจสอบย่อย ณ เวลา: {current_time.strftime('%H:%M:%S')} น.", flush=True)
    
    if 7 <= current_hour <= 19:
        try:
            radar_points = generate_radar_points(TARGET_LAT, TARGET_LON, RADIUS_KM)
            
            # แยกอาเรย์ลิตส์ของละติจูดและลองจิจูดสำหรับส่งให้ Open-Meteo API ตามคู่มือสากล
            lats = [p["lat"] for p in radar_points]
            lons = [p["lon"] for p in radar_points]
            
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lats,
                "longitude": lons,
                "hourly": "cloud
