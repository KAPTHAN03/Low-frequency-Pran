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
# 🕒 ตั้งเวลารันสูงสุดต่อรอบไว้ที่ 50 นาทีเพื่อให้สอดคล้องกับรอบการทำงานของเซิร์ฟเวอร์
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
        {"lat": west.latitude, "lon": west.longitude, "label": "West (ทิศตะวันตก 5 กม.)"}
    ]

openmeteo = openmeteo_requests.Client()

@retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
def fetch_weather_data(url, params):
    return openmeteo.weather_api(url, params=params)

# บันทึกเวลาที่สคริปต์เริ่มทำงานในรอบนั้นๆ
start_script_time = time.time()
print("🤖 บอททำงานระบบไฮบริด (เปิดรอบใหญ่และรันย่อยทุก 5 นาทีข้างใน) เริ่มทำงาน...")

while True:
    # ตรวจสอบว่ารันลูปย่อยมานานจนใกล้หมดชั่วโมงหรือยัง (ถ้าเกิน 50 นาทีให้จบเพื่อรอรอบถัดไป)
    if time.time() - start_script_time > MAX_RUN_DURATION_SEC:
        print("🔄 ครบโควตารันรอบนี้แล้ว ปิดตัวชั่วคราวเพื่อส่งไม้ต่อให้ระบบอัตโนมัติรอบถัดไป")
        break

    current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
    current_hour = current_time.hour  
    
    print(f"\n🕒 รอบตรวจสอบย่อย ณ เวลา: {current_time.strftime('%H:%M:%S')} น.")
    
    # 🔒 เงื่อนไขช่วงเวลาทำงาน 07:00 - 19:00 น.
    if 7 <= current_hour <= 19:
        try:
            locations = get_nearby_coordinates(TARGET_LAT, TARGET_LON, RADIUS_KM)
            lats = [loc["lat"] for loc in locations]
            lons = [loc["lon"] for loc in locations]
            
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lats,
                "longitude": lons,
                "hourly": ["cloud_cover_low", "cloud_cover_mid", "cloud_cover_high"],
                "timezone": "Asia/Bangkok",
                "forecast_days": 1
            }
            
            responses = fetch_weather_data(url, params)
            
            alert_message = f"⚠️ [Low-frequency-Pran] ตรวจพบกลุ่มเมฆหนา ({current_time.strftime('%H:%M')} น.)\n"
            alert_message += f"L: ต่ำ, M: กลาง, H: สูง (รัศมี {RADIUS_KM} กม.)\n"
            alert_message += f"เกณฑ์กำหนด: >= {CLOUD_THRESHOLD}%\n"
            alert_message += "----------------------------------\n"
            
            alert_triggered = False
            
            for i, response in enumerate(responses):
                location_label = locations[i]["label"]
                hourly = response.Hourly()
                cloud_low_values = hourly.Variables(0).ValuesAsNumpy()
                cloud_mid_values = hourly.Variables(1).ValuesAsNumpy()
                cloud_high_values = hourly.Variables(2).ValuesAsNumpy()
                
                time_units = hourly.Time()
                time_units_end = hourly.TimeEnd()
                time_step = hourly.Interval()
                times = pd.to_datetime(range(time_units, time_units_end, time_step), unit="s", utc=True).tz_convert("Asia/Bangkok")
                
                df = pd.DataFrame({
                    "time": times, 
                    "cloud_low": cloud_low_values, 
                    "cloud_mid": cloud_mid_values,
                    "cloud_high": cloud_high_values
                })
                current_hour_df = df[df['time'].dt.hour == current_hour]
                
                if not current_hour_df.empty:
                    low_val = current_hour_df.iloc[0]['cloud_low']
                    mid_val = current_hour_df.iloc[0]['cloud_mid']
                    high_val = current_hour_df.iloc[0]['cloud_high']
                    
                    target_cloud_zone = max(low_val, mid_val, high_val)  
                    
                    if target_cloud_zone >= CLOUD_THRESHOLD:
                        alert_message += f"⚠️ {location_label}: {target_cloud_zone:.1f}% (L:{low_val:.0f}%, M:{mid_val:.0f}%, H:{high_val:.0f}%)\n"
                        alert_triggered = True
            
            if alert_triggered:
                print("⚠️ พบกลุ่มเมฆหนา ยิงแจ้งเตือนเข้า LINE เรียบร้อย")
                send_line_push(alert_message)
            else:
                print("✅ สภาพอากาศปกติ: เมฆต่ำกว่าเกณฑ์ ไม่ส่งข้อความรบกวน")
                
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในลูปย่อย: {e}")
    else:
        print("💤 นอกช่วงเวลาปฏิบัติภารกิจ (07:00 - 19:00 น.) ระบบพักการทำงาน")

    # สั่งระบบนอนรอ 5 นาทีก่อนจะขยับไปเช็ครอบย่อยถัดไป
    print(f"⌛ นอนหลับรอรอบถัดไปอีก 5 นาที...")
    time.sleep(SUB_LOOP_INTERVAL_SEC)
