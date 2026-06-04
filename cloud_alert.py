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
# 📌 ตั้งค่าบัญชีและเกณฑ์การแจ้งเตือนภัย
# ===================================================
# ⚠️ ตรงนี้ใส่ Token ยาวๆ ที่ได้มาจากหัวข้อ Channel access token ล่างสุดของหน้าจอ LINE
LINE_CHANNEL_ACCESS_TOKEN = "dvwYYveHRf+Ayfd03sFQJjMtUkMPjuWqVgqRuBoUBowxmQdOZ76cZ54b/AyLS0BpcINVryk825la+UmfaG2vxfmzHviq3pOszBQZZedltS8TZoiKuahWv7guTxHwyh7Or3YNyWP9QK0R443yRuTzSgdB04t89/1O/w1cDnyilFU="

# ⚠️ ตรงนี้ให้เอารหัส "Your user ID" ที่คัดลอกมาจากขั้นตอนที่ 1 (ล่างสุดของหน้า LINE Developers) มาวางแทนในเครื่องหมายคำพูดครับ
LINE_USER_ID = "วาง_Your_user_ID_ของคุณตรงนี้" 

TARGET_LAT = 12.470361     
TARGET_LON = 99.792917     
RADIUS_KM = 5.0            
CLOUD_THRESHOLD = 50.0     

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
            print("🚀 ส่งแจ้งเตือนสำเร็จ!")
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
    "hourly": ["cloud_cover_low", "cloud_cover_mid"],
    "timezone": "Asia/Bangkok",
    "forecast_days": 1
}

responses = fetch_weather_data(url, params)

current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
current_hour = current_time.hour  

alert_message = f"📊 [ทดสอบระบบ] รายงานตรวจพบเมฆ ({current_time.strftime('%H:%M')} น.)\n"
alert_message += f"โซน: 2,000 - 15,000 ft (รัศมี {RADIUS_KM} กม.)\n"
alert_message += f"เกณฑ์เตือนภัย: >= {CLOUD_THRESHOLD}%\n"
alert_message += "----------------------------------\n"

for i, response in enumerate(responses):
    location_label = locations[i]["label"]
    hourly = response.Hourly()
    cloud_low_values = hourly.Variables(0).ValuesAsNumpy()
    cloud_mid_values = hourly.Variables(1).ValuesAsNumpy()
    
    time_units = hourly.Time()
    time_units_end = hourly.TimeEnd()
    time_step = hourly.Interval()
    times = pd.to_datetime(range(time_units, time_units_end, time_step), unit="s", utc=True).tz_convert("Asia/Bangkok")
    
    df = pd.DataFrame({"time": times, "cloud_low": cloud_low_values, "cloud_mid": cloud_mid_values})
    current_hour_df = df[df['time'].dt.hour == current_hour]
    
    if not current_hour_df.empty:
        low_val = current_hour_df.iloc[0]['cloud_low']
        mid_val = current_hour_df.iloc[0]['cloud_mid']
        target_cloud_zone = max(low_val, mid_val)
        
        if target_cloud_zone >= CLOUD_THRESHOLD:
            alert_message += f"⚠️ {location_label}: {target_cloud_zone:.1f}% (Low: {low_val:.0f}%, Mid: {mid_val:.0f}%)\n"
        else:
            alert_message += f"✅ {location_label}: ปกติ ({target_cloud_zone:.1f}%)\n"

# 📌 บังคับส่งข้อความออกทันทีเพื่อทดสอบสัญญาณท่อส่งข้อมูล
send_line_push(alert_message)
