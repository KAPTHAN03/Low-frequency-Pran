import datetime
import requests
import json
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
CLOUD_THRESHOLD = 0.0

def send_line_push(message_text):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"}
    payload = {"to": LINE_USER_ID, "messages": [{"type": "text", "text": message_text}]}
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        if response.status_code == 200:
            print("🚀 ส่งแจ้งเตือนพิกัดเข้า LINE สำเร็จ!", flush=True)
        else:
            print(f"❌ ส่งไลน์ล้มเหลว: {response.status_code} - {response.text}", flush=True)
    except Exception as e:
        print(f"❌ Line Error: {e}", flush=True)

def generate_radar_points(lat, lon, max_dist_km):
    center = (lat, lon)
    directions = {"N (เหนือ)": 0, "NE (ตะวันออกเฉียงเหนือ)": 45, "E (ตะวันออก)": 90, "SE (ตะวันออกเฉียงใต้)": 135, "S (ใต้)": 180, "SW (ตะวันตกเฉียงใต้)": 225, "W (ตะวันตก)": 270, "NW (ตะวันตกเฉียงเหนือ)": 315}
    
    points = [{"lat": lat, "lon": lon, "label": "Center (พิกัดหลัก)"}]
    for label, bearing in directions.items():
        dest_half = geodesic(kilometers=max_dist_km / 2.0).destination(center, bearing)
        dest_full = geodesic(kilometers=max_dist_km).destination(center, bearing)
        points.append({"lat": dest_half.latitude, "lon": dest_half.longitude, "label": label})
        points.append({"lat": dest_full.latitude, "lon": dest_full.longitude, "label": label})
    return points

print("🤖 บอทตรวจเมฆ 8 ทิศ เริ่มทำงาน...", flush=True)
current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
current_hour = current_time.hour  
print(f"🕒 รอบตรวจสอบ ณ เวลา: {current_time.strftime('%H:%M:%S')} น.", flush=True)

if 7 <= current_hour <= 19:
    try:
        radar_points = generate_radar_points(TARGET_LAT, TARGET_LON, RADIUS_KM)
        lats = [p["lat"] for p in radar_points]
        lons = [p["lon"] for p in radar_points]
        
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lats,
            "longitude": lons,
            "hourly": "cloud_cover_low,cloud_cover_mid,cloud_cover_high,cloud_base_height",
            "timezone": "Asia/Bangkok",
            "forecast_days": 1
        }
        
        print(f"📡 กำลังส่งคำขอชุดพิกัดเรดาร์รวม {len(radar_points)} จุด ไปยัง Open-Meteo...", flush=True)
        resp = requests.get(url, params=params, timeout=15)
        
        if resp.status_code == 200:
            data_json = resp.json()
            responses_list = data_json if isinstance(data_json, list) else [data_json]
            
            raw_data = []
            for idx, item in enumerate(responses_list):
                if idx >= len(radar_points): break
                dir_label = radar_points[idx]["label"]
                hourly = item.get("hourly", {})
                
                c_low = hourly.get("cloud_cover_low", [0.0]*24)[current_hour]
                c_mid = hourly.get("cloud_cover_mid", [0.0]*24)[current_hour]
                c_high = hourly.get("cloud_cover_high", [0.0]*24)[current_hour]
                b_height = hourly.get("cloud_base_height", [0.0]*24)[current_hour]
                
                raw_data.append({"direction": dir_label, "low": float(c_low or 0.0), "mid": float(c_mid or 0.0), "high": float(c_high or 0.0), "base_m": float(b_height if (b_height is not None and not np.isnan(b_height)) else 0.0)})
            
            df_summary = pd.DataFrame(raw_data).groupby("direction").mean().reset_index()
            
            alert_message = f"⚠️ [Low-frequency-Pran] รายงานกลุ่มเมฆเฉลี่ย 2 จุด/ทิศ ({current_time.strftime('%H:%M')} น.)\n"
            alert_message += f"เกณฑ์กำหนด: >= {CLOUD_THRESHOLD}% (รัศมี {RADIUS_KM} กม.)\n"
            alert_message += "----------------------------------\n"
            
            alert_triggered = False
            direction_order = ["Center (พิกัดหลัก)", "N (เหนือ)", "NE (ตะวันออกเฉียงเหนือ)", "E (ตะวันออก)", "SE (ตะวันออกเฉียงใต้)", "S (ใต้)", "SW (ตะวันตกเฉียงใต้)", "W (ตะวันตก)", "NW (ตะวันตกเฉียงเหนือ)"]
            
            for target_dir in direction_order:
                row = df_summary[df_summary["direction"] == target_dir]
                if row.empty: continue
                
                low_val, mid_val, high_val, base_m_val = row.iloc[0]["low"], row.iloc[0]["mid"], row.iloc[0]["high"], row.iloc[0]["base_m"]
                cloud_base_ft_str = "ไม่มีเมฆ" if base_m_val <= 0 else f"{int(round(base_m_val * 3.28084)):,} ft"
                
                if max(low_val, mid_val, high_val) >= CLOUD_THRESHOLD:
                    alert_message += f"⚠️ {target_dir}:\n"
                    alert_message += f"   [L: ต่ำ (ฐานเมฆเฉลี่ย: {cloud_base_ft_str}): {low_val:.0f}%]\n"
                    alert_message += f"   [M: กลาง (6,500-20,000 ft): {mid_val:.0f}%]\n"
                    alert_message += f"   [H: สูง (20,000 ft ขึ้นไป): {high_val:.0f}%]\n"
                    alert_triggered = True
            
            if alert_triggered:
                print("⚠️ ประมวลผลเสร็จสิ้น! กำลังส่งข้อมูลเข้า LINE...", flush=True)
                send_line_push(alert_message)
            else:
                print("✅ สภาพอากาศปกติ: เมฆต่ำกว่าเกณฑ์ทั้งหมด", flush=True)
        else:
            print(f"❌ API Error: {resp.status_code} - {resp.text}", flush=True)
    except Exception as e:
        print(f"❌ เกิดข้อผิดพลาดในระบบตรวจวัด: {e}", flush=True)
else:
    print("💤 นอกช่วงเวลาปฏิบัติภารกิจ (07:00 - 19:00 น.) ระบบปิดตัวเองอัตโนมัติ", flush=True)

print("🏁 ทำงานเสร็จสิ้น ปิด Job เรียบร้อย")
