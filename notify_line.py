"""
VIP Protection NACC - Automated LINE Notification Script
ส่งการแจ้งเตือนภารกิจที่ได้รับอนุมัติสำหรับวันพรุ่งนี้เข้า LINE
"""
import os
import sys
import json
import argparse
from datetime import datetime, timedelta, timezone
import requests
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd

# Handle Windows console UTF-8 output
if sys.platform == "win32" and hasattr(sys.stdout, "buffer"):
    import io
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass

# ==========================================
# 1. Configuration & Constants
# ==========================================
DEFAULT_TOKEN = "Kk2ZgtYu3zB/xrdE5cBKjb11Z625oGHiiaY8I/1iRgEsoWiQIpKdwqbM7zsLXbx7/wzMbNusHcR82UT2QOf8rQDDu//TlItdd0/hIUgybBEEPLeInU93Xz9M/avRDjnNHw4ki+0Spbf3TbgT7OeNrAdB04t89/1O/w1cDnyilFU="
DEFAULT_DESTINATION = "Cf37bd28f68feb697c8f8025af3ad51f4"  # LINE Group ID: VIP Protection NACC

THAI_DAYS = ["วันจันทร์", "วันอังคาร", "วันพุธ", "วันพฤหัสบดี", "วันศุกร์", "วันเสาร์", "วันอาทิตย์"]
THAI_MONTHS = ["", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", 
               "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

def get_thai_date_str(d):
    day_name = THAI_DAYS[d.weekday()]
    month_name = THAI_MONTHS[d.month]
    year_be = d.year + 543
    return f"{day_name}ที่ {d.day} {month_name} {year_be}"

def format_time_str(time_val):
    if not time_val:
        return "-"
    s = str(time_val).strip()
    parts = s.split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return s

# ==========================================
# 2. Connect to Google Sheets
# ==========================================
def connect_sheet():
    # 1. จาก Environment variable (เช่น GitHub Actions Secrets)
    env_sa = os.environ.get("GCP_SERVICE_ACCOUNT")
    if env_sa:
        try:
            info = json.loads(env_sa)
            creds = Credentials.from_service_account_info(info, scopes=SCOPES)
            client = gspread.authorize(creds)
            return client.open("VIP_Security_Tracking").sheet1
        except Exception as e:
            print(f"[!] Error loading creds from GCP_SERVICE_ACCOUNT: {e}")

    # 2. จากไฟล์ local service_account.json
    local_path = os.path.join(os.path.dirname(__file__), "service_account.json")
    if os.path.exists(local_path):
        try:
            creds = Credentials.from_service_account_file(local_path, scopes=SCOPES)
            client = gspread.authorize(creds)
            return client.open("VIP_Security_Tracking").sheet1
        except Exception as e:
            print(f"[!] Error loading creds from local service_account.json: {e}")

    # 3. ลองเปิดไฟล์ service_account.json ใน CWD
    if os.path.exists("service_account.json"):
        creds = Credentials.from_service_account_file("service_account.json", scopes=SCOPES)
        client = gspread.authorize(creds)
        return client.open("VIP_Security_Tracking").sheet1

    raise RuntimeError("ไม่พบ Google Service Account credentials")

# ==========================================
# 3. Message Builder
# ==========================================
def build_notification_message(target_date, records, is_tomorrow=True):
    target_str = target_date.strftime("%Y-%m-%d")
    df = pd.DataFrame(records)
    
    thai_date_label = get_thai_date_str(target_date)
    title_suffix = "ประจำวันพรุ่งนี้" if is_tomorrow else ""
    
    header = f"🔔 แจ้งเตือนภารกิจ VIP NACC {title_suffix}".strip()
    
    if df.empty:
        return (
            f"{header}\n"
            f"📅 {thai_date_label}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ ไม่มีภารกิจที่ได้รับอนุมัติครับ"
        )
    
    # กรองเฉพาะวันที่เป้าหมาย และสถานะอนุมัติแล้ว
    if "Date" not in df.columns:
        return None
        
    df["Date_clean"] = df["Date"].astype(str).str.strip()
    df["Approval_clean"] = df.get("Approval Status", "").astype(str).str.strip()
    
    approved_df = df[
        (df["Date_clean"] == target_str) & 
        (df["Approval_clean"] == "อนุมัติแล้ว")
    ].copy()
    
    if approved_df.empty:
        return (
            f"{header}\n"
            f"📅 {thai_date_label}\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"✅ ไม่มีภารกิจที่ได้รับอนุมัติครับ"
        )
    
    # เรียงลำดับตามเวลา
    if "Time" in approved_df.columns:
        approved_df["Time_sort"] = approved_df["Time"].astype(str)
        approved_df = approved_df.sort_values(by="Time_sort", ascending=True)
    
    count = len(approved_df)
    msg_lines = [
        header,
        f"📅 {thai_date_label}",
        f"━━━━━━━━━━━━━━━━━━━",
        f"พบภารกิจที่ได้รับอนุมัติ {count} ภารกิจ ดังนี้:\n"
    ]
    
    for idx, (_, row) in enumerate(approved_df.iterrows(), start=1):
        mission_name = str(row.get("Mission Name", "-")).strip()
        time_str = format_time_str(row.get("Time", ""))
        day_type = str(row.get("Day Type", "")).strip()
        dress_code = str(row.get("Dress Code", "")).strip() or "ชุดสูท"
        officers = str(row.get("Officers", "-")).strip()
        reporter = str(row.get("Reporter", "-")).strip()
        details = str(row.get("Additional Details", "")).strip()
        
        time_display = f"{time_str} น." if time_str != "-" else "ไม่ระบุเวลา"
        if day_type:
            time_display += f" ({day_type})"
            
        block = [
            f"📌 [{idx}] {mission_name}",
            f"⏰ เวลา: {time_display}",
            f"👔 การแต่งกาย: {dress_code}",
            f"👮 เจ้าหน้าที่: {officers}",
            f"📝 ผู้ทำรายงาน: {reporter}"
        ]
        if details:
            block.append(f"💬 หมายเหตุ: {details}")
            
        msg_lines.append("\n".join(block))
        if idx < count:
            msg_lines.append("───────────────────")
            
    msg_lines.append("━━━━━━━━━━━━━━━━━━━")
    msg_lines.append("🛡️ ขอให้ทุกท่านปฏิบัติภารกิจด้วยความราบรื่นและปลอดภัยครับ")
    
    return "\n".join(msg_lines)

# ==========================================
# 4. LINE Push Notification
# ==========================================
def send_line_push(message_text, destination=None, token=None):
    token = token or os.environ.get("LINE_CHANNEL_ACCESS_TOKEN") or DEFAULT_TOKEN
    destination = destination or os.environ.get("LINE_DESTINATION_ID") or DEFAULT_DESTINATION
    
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "to": destination,
        "messages": [
            {
                "type": "text",
                "text": message_text
            }
        ]
    }
    
    res = requests.post(url, headers=headers, json=payload, timeout=15)
    print(f"[*] LINE Push Status: {res.status_code}")
    if res.status_code != 200:
        print(f"[!] LINE Push Response: {res.text}")
    return res.status_code == 200

# ==========================================
# 5. Main Execution
# ==========================================
def main():
    parser = argparse.ArgumentParser(description="Send tomorrow's approved VIP missions to LINE")
    parser.add_argument("--date", help="Specific target date (YYYY-MM-DD)")
    parser.add_argument("--destination", help="LINE Group ID or User ID")
    parser.add_argument("--test", action="store_true", help="Send test message immediately")
    parser.add_argument("--dry-run", action="store_true", help="Print message without sending to LINE")
    args = parser.parse_args()

    # วันที่และเวลาประเทศไทย (UTC+7)
    th_tz = timezone(timedelta(hours=7))
    now_th = datetime.now(th_tz)
    
    if args.test:
        test_msg = (
            f"🔔 [ทดสอบระบบ] การแจ้งเตือน VIP Protection NACC\n"
            f"⏰ เวลาปัจจุบัน: {now_th.strftime('%d/%m/%Y %H:%M:%S')}\n"
            f"✅ ระบบเชื่อมต่อ LINE Messaging API สำเร็จสมบูรณ์ครับ!"
        )
        print(test_msg)
        if not args.dry_run:
            send_line_push(test_msg, destination=args.destination)
        return

    # วันที่เป้าหมาย: วันพรุ่งนี้ (ตามเวลาประเทศไทย)
    if args.date:
        target_date = datetime.strptime(args.date.strip(), "%Y-%m-%d").date()
    else:
        target_date = now_th.date() + timedelta(days=1)
        
    is_tomorrow = (target_date == (now_th.date() + timedelta(days=1)))
    print(f"[*] Target Date: {target_date} ({get_thai_date_str(target_date)}) | Tomorrow: {is_tomorrow}")
    
    sheet = connect_sheet()
    records = sheet.get_all_records()
    print(f"[*] Read {len(records)} records from Google Sheet")
    
    message = build_notification_message(target_date, records, is_tomorrow=is_tomorrow)
    print("\n--- Notification Message ---")
    print(message)
    print("----------------------------\n")
    
    if args.dry_run:
        print("[*] Dry run mode - message not sent.")
    else:
        success = send_line_push(message, destination=args.destination)
        if success:
            print("[+] Notification sent successfully!")
        else:
            print("[-] Failed to send notification.")
            sys.exit(1)

if __name__ == "__main__":
    main()
