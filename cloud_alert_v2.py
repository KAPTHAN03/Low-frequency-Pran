import datetime
import requests
import json
import numpy as np
import pandas as pd
from geopy.distance import geodesic

# ===================================================
# 📌 LINE API & CONFIGURATION
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
            print("🚀 LINE notification sent successfully!", flush=True)
        else:
            print(f"❌ LINE failed: {response.status_code} - {response.text}", flush=True)
    except Exception as e:
        print(f"❌ LINE Error: {e}", flush=True)

def generate_radar_points(lat, lon, max_dist_km):
    center = (lat, lon)
    directions = {"N": 0, "NE": 45, "E": 90, "SE": 135, "S": 180, "SW": 225, "W": 270, "NW": 315}
    points = [{"lat": lat, "lon": lon, "label": "Center"}]
    for label, bearing in directions.items():
        dest_half = geodesic(kilometers=max_dist_km / 2.0).destination(center, bearing)
        dest_full = geodesic(kilometers=max_dist_km).destination(center, bearing)
        points.append({"lat": dest_half.latitude, "lon": dest_half.longitude, "label": label})
        points.append({"lat": dest_full.latitude, "lon": dest_full.longitude, "label": label})
    return points

print("🤖 Cloud Radar Bot Monitoring Started...", flush=True)
current_time = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=7)))
current_hour = current_time.hour  
print(f"🕒 Check active at: {current_time.strftime('%H:%M:%S')}", flush=True)

if 7 <= current_hour <= 19:
    try:
        radar_points = generate_radar_points(TARGET_LAT, TARGET_LON, RADIUS_KM)
        lats = [p["lat"] for p in radar_points]
        lons = [p["lon"] for p in radar_points]
        
        # ⚡ ยิงคำขอแบบรวมกลุ่มพิกัด โดยตัด cloud_base_height ออกเพื่อไม่ให้ API พัง
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lats,
            "longitude": lons,
            "hourly": "cloud_cover_low,cloud_cover_mid,cloud_cover_high",
            "timezone": "Asia/Bangkok",
            "forecast_days": 1
        }
        
        print(f"📡 Requesting ALL {len(radar_points)} points in ONE single batch...", flush=True)
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
                
                raw_data.append({
                    "direction": dir_label,
                    "low": float(c_low or 0.0),
                    "mid": float(c_mid or 0.0),
                    "high": float(c_high or 0.0)
                })
            
            df_summary = pd.DataFrame(raw_data).groupby("direction").mean().reset_index()
            
            time_str = current_time.strftime('%H:%M')
            alert_message = f"⚠️ [Low-frequency-Pran] Cloud Radar Report ({time_str})\n"
            alert_message += f"Threshold: >= {CLOUD_THRESHOLD}% (Radius {RADIUS_KM} km)\n"
            alert_message += "----------------------------------\n"
            
            alert_triggered = False
            direction_order = ["Center", "N", "NE", "E", "SE", "S", "SW", "W", "NW"]
            
            for target_dir in direction_order:
                row = df_summary[df_summary["direction"] == target_dir]
                if row.empty: continue
                
                low_val, mid_val, high_val = row.iloc[0]["low"], row.iloc[0]["mid"], row.iloc[0]["high"]
                
                if max(low_val, mid_val, high_val) >= CLOUD_THRESHOLD:
                    alert_message += f"⚠️ Direction: {target_dir}\n"
                    alert_message += f"   [L: Low Cloud: {low_val:.0f}%]\n"
                    alert_message += f"   [M: Mid Cloud (6.5k-20k ft): {mid_val:.0f}%]\n"
                    alert_message += f"   [H: High Cloud (20k ft+): {high_val:.0f}%]\n"
                    alert_triggered = True
            
            if alert_triggered:
                print("⚠️ Processing complete! Sending to LINE...", flush=True)
                send_line_push(alert_message)
            else:
                print("✅ Clear Skies: Below threshold", flush=True)
        else:
            print(f"❌ API Error: {resp.status_code} - {resp.text}", flush=True)
    except Exception as e:
        print(f"❌ Processing Error: {e}", flush=True)
else:
    print("💤 Outside operational hours (07:00 - 19:00). Standby.", flush=True)

print("🏁 Job Completed.")
