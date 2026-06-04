import datetime
import openmeteo_requests
import requests_cache
import pandas as pd
import requests
import json
import os
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
CLOUD_THRESHOLD = 50.0     # เกณฑ์แจ้งเตือนภัยเมฆหนาเกิน 50%

STATE_FILE = "last_alert.json"

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

# ⏰ ตรวจเช็คเวลาปัจจุบันของประเทศไทย (UTC+7)
current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
current_hour = current_time.hour  

print(f"⏰ เวลาปัจจุบันที่ระบบตรวจวัดได้: {current_time.strftime('%H:%M')} น.")

# 🔒 เงื่อนไขที่ 1: ตรวจสอบเวลาให้อยู่ในช่วง 07:00 - 19:00 น. ตามเวลาประเทศไทย
if not (7 <= current_hour <= 19):
    print("💤 นอกช่วงเวลาปฏิบัติภารกิจ (07:00 - 19:00 น.) ระบบหยุดการทำงานชั่วคราว")
    # รีเซ็ตสถานะบันทึกประวัติเมื่อพ้นช่วงเวลาทำงาน
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w") as f:
            json.dump({"last_alert_time": current_time.isoformat(), "was_alerting": False}, f)
    exit()

# ดึงข้อมูลสภาพอากาศจาก Open-Meteo API (เพิ่ม cloud_cover_high เมฆชั้นสูง)
cache_session = requests_cache.CachedSession('.cache', expire_after=300)
openmeteo = openmeteo_requests.Client(session=cache_session)

@retry(stop=stop_after_attempt(5), wait=wait_fixed(2))
def fetch_weather_data(url, params):
    return openmeteo.weather_api(url, params=params)

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

alert_message = f"⚠️ [Low-frequency-Pran] รายงานตรวจพบเมฆ ({current_time.strftime('%H:%M')} น.)\n"
alert_message += f"L: ต่ำ, M: กลาง, H: สูง (รัศมี {RADIUS_KM} กม.)\n"
alert_message += f"เกณฑ์เตือนภัย: >= {CLOUD_THRESHOLD}%\n"
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
        
        # คัดเลือกค่าที่หนาแน่นที่สุดในบรรดาเมฆทั้ง 3 ชั้นมาพิจารณา
        target_cloud_zone = max(low_val, mid_val, high_val)  
        
        if target_cloud_zone >= CLOUD_THRESHOLD:
            alert_message += f"⚠️ {location_label}: {target_cloud_zone:.1f}% (L:{low_val:.0f}%, M:{mid_val:.0f}%, H:{high_val:.0f}%)\n"
            alert_triggered = True

# ===================================================
# 🔄 เงื่อนไขที่ 2: ควบคุมการแจ้งเตือน (เตือนซ้ำทุก 15 นาทีเมื่อเกินเกณฑ์ / ไม่ถึงเกณฑ์ไม่ต้องเตือน)
# ===================================================
should_send = False

if alert_triggered:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            state = json.load(f)
            last_alert_str = state.get("last_alert_time")
            last_status = state.get("was_alerting", False)
            
        if last_alert_str and last_status:
            last_alert_time = datetime.datetime.fromisoformat(last_alert_str)
            time_diff = (current_time - last_alert_time).total_seconds() / 60.0
            
            # หากตรวจเจอเมฆหนาต่อเนื่อง และครบรอบเวลา 15 นาที ให้ส่งเตือนซ้ำ
            if time_diff >= 14.5:  
                alert_message += f"\n🔄 (รายงานสภาวะเมฆหนาต่อเนื่องทุก 15 นาที)"
                should_send = True
            else:
                print(f"⌛ เมฆเกินเกณฑ์ แต่ยังไม่ครบกำหนดรอบเวลา 15 นาที (เพิ่งแจ้งไปเมื่อ {time_diff:.1f} นาทีที่แล้ว)")
        else:
            # กรณีพึ่งเปลี่ยนสเตตัสจากท้องฟ้าปกติ มาเป็นเมฆหนาเกินเกณฑ์ครั้งแรก ให้เตือนทันที
            should_send = True
    else:
        # หากรันครั้งแรกสุดแล้วเจอเมฆหนาทันที
        should_send = True

    # บันทึกสถานะรอบนี้ว่า "มีการเตือนภัย (True)"
    with open(STATE_FILE, "w") as f:
        json.dump({"last_alert_time": current_time.isoformat(), "was_alerting": True}, f)

else:
    print("✅ สภาพอากาศปกติ: ไม่มีเมฆชั้นใดถึงเกณฑ์ 50% (ระบบไม่ส่งข้อความรบกวน)")
    # บันทึกสถานะรอบนี้ว่า "ท้องฟ้าปกติ (False)"
    with open(STATE_FILE, "w") as f:
        json.dump({"last_alert_time": current_time.isoformat(), "was_alerting": False}, f)

# 🚀 ส่งสัญญาณเข้า LINE เมื่อผ่านทุกเงื่อนไขตามที่กำหนด
if should_send:
    send_line_push(alert_message)
