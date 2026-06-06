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
CLOUD_THRESHOLD = 50.0

SUB_LOOP_INTERVAL_SEC = 300  # ตื่นมาตรวจวัดย่อยทุกๆ 5 นาที
MAX_RUN_DURATION_SEC = 3000   # รันลูปในรอบใหญ่สูงสุด 50 นาที

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
            print("🚀 ส่งแจ้งเตือนพิกัด 8 ทิศเข้า LINE สำเร็จ!")
        else:
            print(f"❌ ส่งล้มเหลว: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"❌ Error: {e}")

def get_8_direction_coordinates(lat, lon, distance_km):
    center = (lat, lon)
    # มุมองศาของทั้ง 8 ทิศ (N, NE, E, SE, S, SW, W, NW)
    directions = {
        "Center (พิกัดหลัก)": None,
        "N (เหนือ: 337.5°-22.5°)": 0,
        "NE (ตะวันออกเฉียงเหนือ: 22.5°-67.5°)": 45,
        "E (ตะวันออก: 67.5°-112.5°)": 90,
        "SE (ตะวันออกเฉียงใต้: 112.5°-157.5°)": 135,
        "S (ใต้: 157.5°-202.5°)": 180,
        "SW (ตะวันตกเฉียงใต้: 202.5°-247.5°)": 225,
        "W (ตะวันตก: 247.5°-292.5°)": 270,
        "NW (ตะวันตกเฉียงเหนือ: 292.5°-337.5°)": 315
    }
    
    loc_list = []
    for label, bearing in directions.items():
        if bearing is None:
            loc_list.append({"lat": lat, "lon": lon, "label": label})
        else:
            destination = geodesic(kilometers=distance_km).destination(center, bearing)
            loc_list.append({"lat": destination.latitude, "lon": destination.longitude, "label": label})
    return loc_list

openmeteo = openmeteo_requests.Client()

@retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
def fetch_weather_data(url, params):
    return openmeteo.weather_api(url, params=params)

start_script_time = time.time()
print("🤖 บอทตรวจเมฆปราณบุรีระบบ 8 ทิศ + ฐานเมฆจริง เริ่มทำงาน...")

while True:
    if time.time() - start_script_time > MAX_RUN_DURATION_SEC:
        print("🔄 ครบระยะเวลาโควตารอบใหญ่ ปิดตัวเพื่อส่งไม้ต่อรอบถัดไป")
        break

    current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    current_hour =
