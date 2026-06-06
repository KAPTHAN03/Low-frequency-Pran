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
    current_hour = current_time.hour  
    
    print(f"\n🕒 รอบตรวจสอบย่อย ณ เวลา: {current_time.strftime('%H:%M:%S')} น.")
    
    if 7 <= current_hour <= 19:
        try:
            locations = get_8_direction_coordinates(TARGET_LAT, TARGET_LON, RADIUS_KM)
            lats = [loc["lat"] for loc in locations]
            lons = [loc["lon"] for loc in locations]
            
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lats,
                "longitude": lons,
                "hourly": ["cloud_cover_low", "cloud_cover_mid", "cloud_cover_high", "cloud_base_height"],
                "timezone": "Asia/Bangkok",
                "forecast_days": 1
            }
            
            responses = fetch_weather_data(url, params)
            
            alert_message = f"⚠️ [Low-frequency-Pran] รายงานตรวจพบกลุ่มเมฆ ({current_time.strftime('%H:%M')} น.)\n"
            alert_message += f"เกณฑ์กำหนด: >= {CLOUD_THRESHOLD}% (รัศมี {RADIUS_KM} กม.)\n"
            alert_message += "----------------------------------\n"
            
            alert_triggered = False
            
            for i, response in enumerate(responses):
                location_label = locations[i]["label"]
                hourly = response.Hourly()
                
                cloud_low = hourly.Variables(0).ValuesAsNumpy()
                cloud_mid = hourly.Variables(1).ValuesAsNumpy()
                cloud_high = hourly.Variables(2).ValuesAsNumpy()
                cloud_base_m = hourly.Variables(3).ValuesAsNumpy() # ดึงข้อมูลความสูงฐานเมฆ (เมตร)
                
                time_units = hourly.Time()
                time_units_end = hourly.TimeEnd()
                time_step = hourly.Interval()
                times = pd.to_datetime(range(time_units, time_units_end, time_step), unit="s", utc=True).tz_convert("Asia/Bangkok")
                
                df = pd.DataFrame({
                    "time": times, 
                    "cloud_low": cloud_low, 
                    "cloud_mid": cloud_mid,
                    "cloud_high": cloud_high,
                    "cloud_base_m": cloud_base_m
                })
                current_hour_df = df[df['time'].dt.hour == current_hour]
                
                if not current_hour_df.empty:
                    low_val = current_hour_df.iloc[0]['cloud_low']
                    mid_val = current_hour_df.iloc[0]['cloud_mid']
                    high_val = current_hour_df.iloc[0]['cloud_high']
                    base_m_val = current_hour_df.iloc[0]['cloud_base_m']
                    
                    # แปลงความสูงฐานเมฆจากเมตรเป็นฟุต (ft)
                    if pd.isna(base_m_val) or base_m_val <= 0:
                        cloud_base_ft_str = "ไม่มีเมฆ"
                    else:
                        cloud_base_ft = int(round(base_m_val * 3.28084))
                        cloud_base_ft_str = f"{cloud_base_ft:,} ft"
                    
                    # หาค่าที่มากที่สุดของจุด/ทิศนั้น เพื่อตรวจเช็คเกณฑ์เตือนภัย
                    max_cloud_in_route = max(low_val, mid_val, high_val)
                    
                    if max_cloud_in_route >= CLOUD_THRESHOLD:
                        alert_message += f"⚠️ {location_label}:\n"
                        alert_message += f"   [L: ต่ำ (ฐานเมฆ: {cloud_base_ft_str}): {low_val:.0f}%]\n"
                        alert_message += f"   [M: กลาง (6,500-20,000 ft): {mid_val:.0f}%]\n"
                        alert_message += f"   [H: สูง (20,000 ft ขึ้นไป): {high_val:.0f}%]\n"
                        alert_triggered = True
            
            if alert_triggered:
                print("⚠️ ตรวจพบมวลเมฆเกินเกณฑ์ ยิงเข้า LINE ทันที")
                send_line_push(alert_message)
            else:
                print("✅ สภาพอากาศปกติ: ทุกทิศทางเมฆต่ำกว่าเกณฑ์")
                
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในลูปย่อย: {e}")
    else:
        print("💤 นอกช่วงเวลาปฏิบัติภารกิจ (07:00 - 19:00 น.) ระบบสแตนด์บาย")

    print(f"⌛ นอนหลับรอรอบถัดไปอีก 5 นาที...")
    time.sleep(SUB_LOOP_INTERVAL_SEC)
