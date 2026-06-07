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
CLOUD_THRESHOLD = 0.0  # 0.0 เพื่อบังคับให้กางครบทุกทิศลง LINE ทันทีชัวร์ๆ

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

# 🗺️ สร้างพิกัด: ทิศละ 2 จุดตรวจ (ระยะครึ่งทาง 2.5 กม. และ ระยะเต็ม 5.0 กม.)
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
    # พิกัดที่ 1: จุดศูนย์กลาง (Center)
    points.append({"lat": lat, "lon": lon, "label": "Center (พิกัดหลัก)"})
    
    # พิกัดทิศอื่นๆ ทิศละ 2 จุดย่อย
    for label, bearing in directions.items():
        dist_half = max_dist_km / 2.0
        dest_half = geodesic(kilometers=dist_half).destination(center, bearing)
        dest_full = geodesic(kilometers=max_dist_km).destination(center, bearing)
        
        points.append({"lat": dest_half.latitude, "lon": dest_half.longitude, "label": label})
        points.append({"lat": dest_full.latitude, "lon": dest_full.longitude, "label": label})
        
    return points

start_script_time = time.time()
print("🤖 บอทตรวจเมฆ 8 ทิศ (ระบบคำนวณเฉลี่ย 2 จุดตรวจ/ทิศ) เริ่มทำงาน...", flush=True)

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
            raw_data = []
            
            print(f"📡 กำลังทยอยดึงข้อมูลสภาพอากาศทีละพิกัด (รวม {len(radar_points)} จุด)...", flush=True)
            
            # เปลี่ยนมาใช้การดึงข้อมูลผ่าน requests ดั้งเดิมทีละจุด เพื่อหลีกเลี่ยงข้อจำกัดโมเดลอาร์เรย์ของ Open-Meteo
            for p in radar_points:
                url = f"https://api.open-meteo.com/v1/forecast?latitude={p['lat']}&longitude={p['lon']}&hourly=cloud_cover_low,cloud_cover_mid,cloud_cover_high,cloud_base_height&timezone=Asia/Bangkok&forecast_days=1"
                resp = requests.get(url, timeout=10)
                
                if resp.status_code == 200:
                    data = resp.json()
                    hourly = data.get("hourly", {})
                    
                    c_low = hourly.get("cloud_cover_low", [0]*24)[current_hour]
                    c_mid = hourly.get("cloud_cover_mid", [0]*24)[current_hour]
                    c_high = hourly.get("cloud_cover_high", [0]*24)[current_hour]
                    b_height = hourly.get("cloud_base_height", [0]*24)[current_hour]
                    
                    raw_data.append({
                        "direction": p["label"],
                        "low": float(c_low) if c_low is not None else 0.0,
                        "mid": float(c_mid) if c_mid is not None else 0.0,
                        "high": float(c_high) if c_high is not None else 0.0,
                        "base_m": float(b_height) if (b_height is not None and not np.isnan(b_height)) else 0.0
                    })
                else:
                    print(f"⚠️ จุด {p['label']} ดึงข้อมูลไม่สำเร็จ: สถานะ {resp.status_code}", flush=True)
                
                time.sleep(0.1) # หน่วงเวลาเล็กน้อยเพื่อถนอมเซิร์ฟเวอร์ API
            
            # ยุบรวมหาค่าเฉลี่ยทางพื้นที่ของทั้ง 2 จุดในทิศเดียวกัน
            df_radar = pd.DataFrame(raw_data)
            df_summary = df_radar.groupby("direction").mean().reset_index()
            
            alert_message = f"⚠️ [Low-frequency-Pran] รายงานกลุ่มเมฆเฉลี่ย 2 จุด/ทิศ ({current_time.strftime('%H:%M')} น.)\n"
            alert_message += f"เกณฑ์กำหนด: >= {CLOUD_THRESHOLD}% (รัศมี {RADIUS_KM} กม.)\n"
            alert_message += "----------------------------------\n"
            
            alert_triggered = False
            
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
                    # แปลงหน่วยเมตรเป็นฟุตจากค่าเฉลี่ย
                    cloud_base_ft = int(round(base_m_val * 3.28084))
                    cloud_base_ft_str = f"{cloud_base_ft:,} ft"
                
                max_cloud = max(low_val, mid_val, high_val)
                
                if max_cloud >= CLOUD_THRESHOLD:
                    alert_message += f"⚠️ {target_dir}:\n"
                    alert_message += f"   [L: ต่ำ (ฐานเมฆเฉลี่ย: {cloud_base_ft_str}): {low_val:.0f}%]\n"
                    alert_message += f"   [M: กลาง (6,500-20,000 ft): {mid_val:.0f}%]\n"
                    alert_message += f"   [H: สูง (20,000 ft ขึ้นไป): {high_val:.0f}%]\n"
                    alert_triggered = True
            
            if alert_triggered:
                send_line_push(alert_message)
            else:
                print("✅ สภาพอากาศปกติ: ทุกทิศทางเมฆต่ำกว่าเกณฑ์", flush=True)
                
        except Exception as e:
            print(f"❌ เกิดข้อผิดพลาดในการประมวลผลคำนวณ: {e}", flush=True)
    else:
        print("💤 นอกช่วงเวลาปฏิบัติภารกิจ (07:00 - 19:00 น.) ระบบสแตนด์บาย", flush=True)

    print(f"⌛ นอนหลับรอรอบถัดไปอีก 5 นาที...", flush=True)
    time.sleep(SUB_LOOP_INTERVAL_SEC)
