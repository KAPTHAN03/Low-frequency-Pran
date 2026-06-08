import datetime
import requests
import json
import os
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

# 🎯 ตั้งเกณฑ์ทดสอบไว้ที่ 0.0% เพื่อให้ LINE เด้งทันที (ทดสอบผ่านแล้วค่อยมาแก้เป็น 50.0 ครับ)
CLOUD_THRESHOLD = 0.0  
STATE_FILE = "cloud_radar_state.json"

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

def load_previous_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️ State file error: {e}", flush=True)
            return {"last_alert_date": "", "last_alert_hour": -1}
    return {"last_alert_date": "", "last_alert_hour": -1}

def save_current_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
        print(f"💾 State memory updated: {state}", flush=True)
    except Exception as e:
        print(f"⚠️ Cannot save state file: {e}", flush=True)

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
current_date_str = current_time.strftime('%Y-%m-%d')

print(f"🕒 Current Local Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Hour: {current_hour})", flush=True)

# ดึงประวัติความจำล่าสุดมาเช็ค
prev_state = load_previous_state()
last_alert_date = prev_state.get("last_alert_date", "")
last_alert_hour = prev_state.get("last_alert_hour", -1)

# ตรรกะล็อกรายชั่วโมง (เมื่อกดรันซ้ำในชั่วโมงเดิม)
if last_alert_date == current_date_str and last_alert_hour == current_hour:
    print(f"🛑 [LOCK Active] บอทเคยแจ้งเตือนในชั่วโมงนี้ ({current_hour}:00) ไปแล้วรอบหนึ่ง! บล็อกการส่งซ้ำเพื่อเซฟโควตา.", flush=True)
    print("🏁 Job Completed (Skipped due to hourly lock).")
    exit(0)

try:
    radar_points = generate_radar_points(TARGET_LAT, TARGET_LON, RADIUS_KM)
    lats = [p["lat"] for p in radar_points]
    lons = [p["lon"] for p in radar_points]
    
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
        alert_message = f"⚠️ [Low-frequency-Pran] Heavy Cloud Alert (>50%) ({time_str})\n"
        alert_message += f"Threshold: > {CLOUD_THRESHOLD}% (Radius {RADIUS_KM} km)\n"
        alert_message += "----------------------------------\n"
        
        heavy_cloud_detected = False
        direction_order = ["Center", "N", "NE", "E", "SE", "S", "SW", "W", "NW"]
        
        print("📊 Current Cloud Density Breakdown:", flush=True)
        for target_dir in direction_order:
            row = df_summary[df_summary["direction"] == target_dir]
            if row.empty: continue
            
            low_val, mid_val, high_val = row.iloc[0]["low"], row.iloc[0]["mid"], row.iloc[0]["high"]
            max_cloud = max(low_val, mid_val, high_val)
            print(f"   -> Direction {target_dir}: Max Cloud = {max_cloud:.0f}%", flush=True)
            
            if max_cloud >= CLOUD_THRESHOLD:
                alert_message += f"⚠️ Direction: {target_dir}\n"
                alert_message += f"   [L: {low_val:.0f}%, M: {mid_val:.0f}%, H: {high_val:.0f}%]\n"
                heavy_cloud_detected = True

        if heavy_cloud_detected:
            print("⚠️ Heavy cloud detected! Sending alert to LINE...", flush=True)
            send_line_push(alert_message)
            save_current_state({"last_alert_date": current_date_str, "last_alert_hour": current_hour})
        else:
            print("✅ Clouds are below threshold. No alert sent.", flush=True)
            
    else:
        print(f"❌ API Error: {resp.status_code} - {resp.text}", flush=True)
except Exception as e:
    print(f"❌ Processing Error: {e}", flush=True)

print("🏁 Job Completed.")
