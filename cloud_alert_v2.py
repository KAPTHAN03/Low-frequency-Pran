import datetime
import requests
import json
import os
import numpy as np
import pandas as pd
from geopy.distance import geodesic

# บังคับให้ matplotlib ใช้ Backend แบบไม่แสดงหน้าจอ (เซฟเป็นรูปภาพอย่างเดียว)
import matplotlib
matplotlib.use('Agg')  
import matplotlib.pyplot as plt

# ===================================================
# 📌 LINE API & CONFIGURATION
# ===================================================
LINE_CHANNEL_ACCESS_TOKEN = "jwuHwu0W0GBSfDCbjl22PoAOtAJLkLn/tb5UPKakL3bsU2c5cVzoWicH9aWqkNn7rZzylZjlw86vtlcbA3ggg11mAYDi45oFOHru6OXbL8Q3Oyo1HkYFdNe3oQV4louWJz1G/icXJ0LTFCmZqQk9vQdB04t89/1O/w1cDnyilFU="
LINE_USER_ID = "Ubd5b155e64f586825a02d6556d5ad3f2"

TARGET_LAT = 12.470361
TARGET_LON = 99.792917
RADIUS_KM = 5.0

# 🎯 เกณฑ์ความหนาของเมฆ (ใช้งานจริงตั้งไว้ที่ 50.0%)
CLOUD_THRESHOLD = 50.0  
STATE_FILE = "cloud_radar_state.json"
GRAPH_FILE = "cloud_history_5h.png"

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

def generate_and_save_graph(history_df):
    try:
        plt.figure(figsize=(8, 4))
        x_labels = [f"{int(h):02d}:00" for h in history_df["hour"]]
        
        plt.plot(x_labels, history_df["low"], marker='o', label='Low Clouds', color='#1f77b4', linewidth=2)
        plt.plot(x_labels, history_df["mid"], marker='s', label='Mid Clouds', color='#ff7f0e', linewidth=2)
        plt.plot(x_labels, history_df["high"], marker='^', label='High Clouds', color='#2ca02c', linewidth=2)
        
        plt.axhline(y=CLOUD_THRESHOLD, color='r', linestyle='--', label=f'Threshold ({CLOUD_THRESHOLD}%)')
        plt.title("Cloud Cover History (Past 5 Hours Area Avg)")
        plt.xlabel("Time")
        plt.ylabel("Cloud Cover (%)")
        plt.ylim(0, 105)
        plt.grid(True, linestyle=':', alpha=0.6)
        plt.legend(loc='upper left')
        plt.tight_layout()
        
        plt.savefig(GRAPH_FILE, dpi=150)
        plt.close()
        print(f"📊 Graph successfully generated and saved to {GRAPH_FILE}", flush=True)
    except Exception as e:
        print(f"❌ Graph Generation Error: {e}", flush=True)


print("🤖 Cloud Radar Bot Monitoring Started...", flush=True)

tz_thai = datetime.timezone(datetime.timedelta(hours=7))
current_time = datetime.datetime.now(tz_thai)
current_hour = current_time.hour  
current_date_str = current_time.strftime('%Y-%m-%d')

print(f"🕒 Current Local Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Hour: {current_hour})", flush=True)

if not (7 <= current_hour <= 19):
    print(f"💤 ช่วงเวลานี้ ({current_hour}:00) อยู่นอกเวลาปฏิบัติงาน (07:00 - 19:00). บอทจำศีลอัตโนมัติ ไม่ส่ง LINE.", flush=True)
    print("🏁 Job Completed (Standby mode).")
    exit(0)

prev_state = load_previous_state()
last_alert_date = prev_state.get("last_alert_date", "")
last_alert_hour = prev_state.get("last_alert_hour", -1)

if last_alert_date == current_date_str and last_alert_hour == current_hour:
    print(f"🛑 [HOURLY LOCK Active] บอทเคยแจ้งเตือนในชั่วโมงนี้ ({current_hour}:00) ไปแล้วรอบหนึ่ง! บล็อกการส่งซ้ำในชั่วโมงเดียวกัน.", flush=True)
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
        
        # คำนวณช่วงเวลา 5 ชั่วโมงย้อนหลัง
        start_hour = max(0, current_hour - 4) 
        target_hours = list(range(start_hour, current_hour + 1))
        
        raw_data_all_hours = []
        raw_data_current = []
        
        for idx, item in enumerate(responses_list):
            if idx >= len(radar_points): break
            dir_label = radar_points[idx]["label"]
            hourly = item.get("hourly", {})
            
            c_low_list = hourly.get("cloud_cover_low", [0.0]*24)
            c_mid_list = hourly.get("cloud_cover_mid", [0.0]*24)
            c_high_list = hourly.get("cloud_cover_high", [0.0]*24)
            
            for h in target_hours:
                raw_data_all_hours.append({
                    "hour": h,
                    "direction": dir_label,
                    "low": float(c_low_list[h] or 0.0),
                    "mid": float(c_mid_list[h] or 0.0),
                    "high": float(c_high_list[h] or 0.0)
                })
            
            raw_data_current.append({
                "direction": dir_label,
                "low": float(c_low_list[current_hour] or 0.0),
                "mid": float(c_mid_list[current_hour] or 0.0),
                "high": float(c_high_list[current_hour] or 0.0)
            })
        
        df_all = pd.DataFrame(raw_data_all_hours)
        df_history_avg = df_all.groupby("hour")[["low", "mid", "high"]].mean().reset_index()
        
        # สร้างกราฟและเซฟไฟล์เป็นรูปภาพ
        generate_and_save_graph(df_history_avg)
        
        df_summary = pd.DataFrame(raw_data_current).groupby("direction").mean().reset_index()
        
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

        alert_message += "----------------------------------\n"
        alert_message += "📈 Past 5h Avg (Low/Mid/High):\n"
        for _, r in df_history_avg.iterrows():
            alert_message += f"• {int(r['hour'])}:00 -> {r['low']:.0f}% / {r['mid']:.0f}% / {r['high']:.0f}%\n"

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
