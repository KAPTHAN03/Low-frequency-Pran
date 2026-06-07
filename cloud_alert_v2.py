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
    points = [{"lat": lat, "lon": lon, "bearing": -1, "label": "Center (พิกัดหลัก)"}]
    
    # สแกนพิกัดรัศมีโดยรอบทุกๆ 15 องศา เพื่อความแม่นยำในการเฉลี่ยพื้นที่
    for b in range(0, 360, 15):
        for d in np.linspace(1.5, max_dist_km, 3):
            dest = geodesic(kilometers=d).destination(center, b)
            points.append({"lat": dest.latitude, "lon": dest.longitude, "bearing": b})
    return points

def get_direction_label(bearing):
    if bearing == -1: 
        return "Center (พิกัดหลัก)"
    
    # แบ่งช่วงองศา 8 ทิศสากล ป้องกันเครื่องหมายคำพูดตกหล่น
    if (bearing >= 337.5) or (bearing < 22.5):   return "N (เหนือ)"
    if 22.5 <= bearing < 67.5:   return "NE (ตะวันออกเฉียงเหนือ)"
    if 67.5 <= bearing < 112.5:  return "E (ตะวันออก)"
    if 112.5 <= bearing < 157.5: return "SE (ตะวันออกเฉียงใต้)"
    if 157.5 <= bearing < 202.5: return "S (ใต้)"
    if 202.5 <= bearing < 247.5: return "SW (ตะวันตกเฉียงใต้)"
    if 247.5 <= bearing < 292.5: return "W (ตะวันตก)"
    if 292.5 <= bearing < 337.5: return "NW (ตะวันตกเฉียงเหนือ)"
    return "Unknown"

openmeteo = openmeteo_requests.Client()

@retry(stop=stop_after_attempt(5), wait=wait_fixed(3))
def fetch_weather_data(url, params):
    return openmeteo.weather_api(url, params=params)

start_script_time = time.time()
print("🤖 บอทตรวจเมฆระบบเรดาร์ 8 ทิศ (คำนวณจากมุมองศาจริง) เริ่มทำงาน...", flush=True)

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
            lats = [p["lat"] for p in radar_points]
            lons = [p["lon"] for p in radar_points]
            
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": lats,
                "longitude": lons,
                "hourly": ["cloud_cover_low", "cloud_cover_mid", "cloud_cover_high", "cloud_base_height"],
                "timezone": "Asia/Bangkok",
                "forecast_days": 1
            }
            
            responses = fetch_weather_data(url, params)
            
            # รวบรวมข้อมูลดิบเพื่อนำมาทำ Groupby ดึงค่าเฉลี่ยตามทิศทาง
            raw_data = []
            for idx, response in enumerate(responses):
                bearing = radar_points[idx]["bearing"]
                dir_label = get_direction_label(bearing)
                
                hourly = response.Hourly()
                c_low = hourly.Variables(0).ValuesAsNumpy()[current_hour]
                c_mid = hourly.Variables(1).ValuesAsNumpy()[current_hour]
                c_high = hourly.Variables(2).ValuesAsNumpy()[current_hour]
                b_height = hourly.Variables(3).ValuesAsNumpy()[current_hour]
                
                raw_data.append({
                    "direction": dir_label,
                    "low": c_low,
                    "mid": c_mid,
                    "high": c_high,
                    "base_m": b_height if not np.isnan(b_height) else 0
                })
            
            # คำนวณค่าเฉลี่ยแยกตามทิศทางกลุ่มมุมองศา
            df_radar = pd.DataFrame(raw_data)
            df_summary = df_radar.groupby("direction").mean().reset_index()
            
            alert_message = f"⚠️ [Low-frequency-Pran] รายงานกลุ่มเมฆสแกนองศา ({current_time.strftime('%H:%M')} น.)\n"
            alert_message += f"เกณฑ์กำหนด: >= {CLOUD_THRESHOLD}% (รัศมี {RADIUS_KM} กม.)\n"
            alert_message += "----------------------------------\n"
            
            alert_triggered = False
            
            # บังคับเรียงทิศทางรายงานให้กระชับและสัมพันธ์กับฟังก์ชันชื่อทิศ
            direction_order = [
                "Center (พิกัดหลัก)", "N (เหนือ)", "NE (ตะวันออกเฉียงเหนือ)",
                "E (ตะวันออก)", "SE (ตะวันออกเฉียงใต้)", "S (ใต้)",
                "SW (ตะวันตกเฉียงใต้)", "W (ตะวันตก)", "NW (ตะวันตกเฉียงเหนือ)"
            ]
            
            for target_dir in direction_order:
                row = df_summary[df_summary["direction"] == target_dir]
                if row.empty: continue
                
                low_val = row.iloc[0]["low"]
                mid_val = row.iloc[0]["mid"]
                high_val = row.iloc[0]["high"]
                base_m_val = row.iloc[0]["base_m"]
                
                if base_m_val <= 0:
                    cloud_base_ft_str = "ไม่มีเมฆ"
                else:
                    cloud_base_ft = int(round(base_m_val * 3.28084))
                    cloud_base_ft_str = f"{cloud_base_ft:,} ft"
                
                max_cloud = max(low_val, mid_val, high_val)
                
                if max_cloud >= CLOUD_THRESHOLD:
                    alert_message += f"⚠️ {target_dir}:\n"
                    alert_message += f"   [L: ต่ำ (ฐานเมฆ: {cloud_base_ft_str}): {low_val:.0f}%]\n"
                    alert_message += f"   [M: กลาง (6,500-20,000 ft): {mid_val:.0f}%]\n"
                    alert_message += f"   [H: สูง (20,000 ft ขึ้นไป): {high_val:.0f}%]\n"
                    alert_triggered = True
            
            if alert_triggered:
                print("⚠️ ประมวลผลโมเดลเรดาร์เสร็จสิ้น ยิงเข้า LINE ทันที", flush=True)
                send_line_push(alert_message)
            else:
                print("✅ สภาพอากาศปกติ: ทุกทิศทางเมฆต่ำกว่าเกณฑ์", flush=True)
                
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในระบบเรดาร์: {e}", flush=True)
    else:
        print("💤 นอกช่วงเวลาปฏิบัติภารกิจ (07:00 - 19:00 น.) ระบบสแตนด์บาย", flush=True)

    print(f"⌛ นอนหลับรอรอบถัดไปอีก 5 นาที...", flush=True)
    time.sleep(SUB_LOOP_INTERVAL_SEC)
