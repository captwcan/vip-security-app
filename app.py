import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import uuid
import os
from datetime import datetime
import time

# ==========================================
# 1. Configuration & Constants
# ==========================================
st.set_page_config(page_title="VIP Security Tracking", layout="wide")

OFFICERS = [
    "นายวันพิทักษ์ วงค์มูล", "นายทรงพล เล็กพูนศักดิ์",
    "ร.ต.อ. วรดร ใสสุขล", "นายปริวรรตน์ จารุเศวตรัศมิ์", "นายไกรฤทธิ์ ศรีสูงเนิน",
    "นายวีรพจน์ สรรพากิจวัฒนา", "นางสาวปาณิชา ใจมุข", "นางสาวพลชา กองจันทร์",
    "นายณัฐนันท์ อำม์พรพันธ์", "นายกมลนัทธ์ ศักดิ์สุวรรณ", "นายกฤตภาส เอี่ยมศรี"
]

DAY_TYPES = ["วันทำงานปกติ (ในเวลา)", "วันทำงานปกติ (นอกเวลา)", "วันหยุด"]

THAI_MONTHS = [
    "", "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"
]

# ==========================================
# 2. Database Connection
# ==========================================
@st.cache_resource
def init_connection_v3():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. ลองอ่านจากไฟล์ Local ก่อน (สำหรับรันบนคอมพิวเตอร์ตัวเอง)
    if os.path.exists("service_account.json"):
        try:
            credentials = Credentials.from_service_account_file("service_account.json", scopes=scopes)
            client = gspread.authorize(credentials)
            sheet = client.open("VIP_Security_Tracking").sheet1 
            return sheet
        except Exception as e:
            st.error(f"❌ ไม่สามารถเชื่อมต่อ Google Sheets (Local) ได้: {e}")
            return None
            
    # 2. ลองอ่านจาก Streamlit Secrets (สำหรับรันบน Cloud ออนไลน์ 24 ชม.)
    elif "gcp_service_account" in st.secrets:
        try:
            # ใช้ st.secrets ซึ่งเก็บเป็น dictionary ได้เลย
            credentials = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
            client = gspread.authorize(credentials)
            sheet = client.open("VIP_Security_Tracking").sheet1 
            return sheet
        except Exception as e:
            st.error(f"❌ ไม่สามารถเชื่อมต่อ Google Sheets (Cloud) ได้: {e}")
            return None
            
    else:
        st.error("❌ ไม่พบไฟล์ service_account.json หรือการตั้งค่า Secrets กรุณาตรวจสอบ")
        return None

sheet = init_connection_v3()

@st.cache_data(ttl=60)
def get_data():
    if sheet is None:
        return pd.DataFrame(columns=["Mission ID", "Mission Name", "Date", "Time", "Day Type", "Officers", "Reporter", "Report Status", "Additional Details", "Approval Status"])
    else:
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
        if not df.empty:
            if 'Time' not in df.columns: df['Time'] = ''
            if 'Report Status' not in df.columns: df['Report Status'] = 'ยังไม่ส่ง'
            if 'Additional Details' not in df.columns: df['Additional Details'] = ''
            if 'Approval Status' not in df.columns: df['Approval Status'] = 'อนุมัติแล้ว'
            
            # เติมค่าให้แถวเก่าที่ช่องใหม่ยังว่างอยู่
            df['Report Status'] = df['Report Status'].replace('', 'ยังไม่ส่ง')
            df['Report Status'] = df['Report Status'].fillna('ยังไม่ส่ง').astype(str)
            df['Approval Status'] = df['Approval Status'].replace('', 'อนุมัติแล้ว')
            df['Approval Status'] = df['Approval Status'].fillna('อนุมัติแล้ว').astype(str)
            df['Additional Details'] = df['Additional Details'].fillna('').astype(str)
        else:
            df = pd.DataFrame(columns=["Mission ID", "Mission Name", "Date", "Time", "Day Type", "Officers", "Reporter", "Report Status", "Additional Details", "Approval Status"])
        
        # จัดการข้อมูลเก่าใน DB ให้ตรงกับประเภทใหม่
        if not df.empty and 'Day Type' in df.columns:
            df['Day Type'] = df['Day Type'].replace(["วันหยุดเสาร์-อาทิตย์", "วันหยุดนักขัตฤกษ์"], "วันหยุด")
            df['Day Type'] = df['Day Type'].replace(["วันทำงานปกติ"], "วันทำงานปกติ (ในเวลา)")
            
        return df

# ==========================================
# 3. Helper Functions
# ==========================================
def to_thai_date(date_val):
    if pd.isna(date_val) or not date_val:
        return ""
    try:
        if isinstance(date_val, str):
            d = datetime.strptime(date_val.strip(), '%Y-%m-%d').date()
        else:
            d = date_val.date() if isinstance(date_val, datetime) else date_val
            
        year = d.year + 543
        month = THAI_MONTHS[d.month]
        day = d.day
        return f"{day} {month} {year}"
    except:
        return str(date_val)

def to_thai_month_year(date_str_yyyy_mm):
    try:
        y, m = date_str_yyyy_mm.split('-')
        return f"{THAI_MONTHS[int(m)]} {int(y) + 543}"
    except:
        return date_str_yyyy_mm
        
def thai_date_picker(label, default_date=None, key_prefix=""):
    st.markdown(f'<p style="font-size:14px; margin-bottom:5px;">{label}</p>', unsafe_allow_html=True)
    col1, col2, col3 = st.columns(3)
    
    today = datetime.today()
    if default_date is None:
        default_date = today.date()
        
    current_year_be = today.year + 543
    
    days = list(range(1, 32))
    default_day_idx = default_date.day - 1
    
    thai_months_list = THAI_MONTHS[1:] 
    default_month_idx = default_date.month - 1
    
    years_be = list(range(current_year_be - 5, current_year_be + 5))
    default_year_be = default_date.year + 543
    default_year_idx = years_be.index(default_year_be) if default_year_be in years_be else 5
    
    with col1:
        sel_day = st.selectbox("วัน", days, index=default_day_idx, key=f"{key_prefix}_day", label_visibility="collapsed")
    with col2:
        sel_month_str = st.selectbox("เดือน", thai_months_list, index=default_month_idx, key=f"{key_prefix}_month", label_visibility="collapsed")
    with col3:
        sel_year_be = st.selectbox("ปี (พ.ศ.)", years_be, index=default_year_idx, key=f"{key_prefix}_year", label_visibility="collapsed")
        
    sel_month = THAI_MONTHS.index(sel_month_str)
    sel_year_ce = sel_year_be - 543
    
    try:
        final_date = datetime(sel_year_ce, sel_month, sel_day).date()
        return final_date, None
    except ValueError:
        return None, "รูปแบบวันที่ไม่ถูกต้อง (เช่น 31 กุมภาพันธ์)"

def add_mission(name, date, time_val, day_type, officers, reporter):
    if not sheet:
        st.error("ไม่สามารถบันทึกได้: ยังไม่ได้เชื่อมต่อ Google Sheets")
        return
        
    mission_id = str(uuid.uuid4())
    clean_officers = [name.split(" (")[0] for name in officers]
    clean_reporter = reporter.split(" (")[0] if reporter else ""
    
    officers_str = ", ".join(clean_officers)
    
    # Logic การอนุมัติ
    today = datetime.today().date()
    approval_status = "รอเห็นชอบ" if date > today else "อนุมัติแล้ว"
    
    row = [mission_id, name, str(date), str(time_val), day_type, officers_str, clean_reporter, "ยังไม่ส่ง", "", approval_status]
    
    sheet.append_row(row)
    st.cache_data.clear()
    st.success("บันทึกข้อมูลลง Google Sheets สำเร็จ!")

def update_mission(mission_id, name, date, time_val, day_type, officers, reporter):
    if not sheet:
        st.error("ไม่สามารถอัปเดตได้: ยังไม่ได้เชื่อมต่อ Google Sheets")
        return
        
    clean_officers = [name.split(" (")[0] for name in officers]
    clean_reporter = reporter.split(" (")[0] if reporter else ""
    officers_str = ", ".join(clean_officers)
    
    cell = sheet.find(mission_id)
    if cell:
        row_idx = cell.row
        sheet.update(f"B{row_idx}:G{row_idx}", [[name, str(date), str(time_val), day_type, officers_str, clean_reporter]])
        st.cache_data.clear()
        st.success("อัปเดตข้อมูลใน Google Sheets สำเร็จ!")

def approve_mission(mission_id):
    if not sheet:
        st.error("ไม่สามารถอัปเดตได้: ยังไม่ได้เชื่อมต่อ Google Sheets")
        return
        
    cell = sheet.find(mission_id)
    if cell:
        row_idx = cell.row
        sheet.update(f"J{row_idx}", [["อนุมัติแล้ว"]])
        st.cache_data.clear()

def update_mission_details(mission_id, status, details):
    if not sheet:
        st.error("ไม่สามารถอัปเดตได้: ยังไม่ได้เชื่อมต่อ Google Sheets")
        return
        
    cell = sheet.find(mission_id)
    if cell:
        row_idx = cell.row
        sheet.update_cell(row_idx, 8, str(status))
        sheet.update_cell(row_idx, 9, str(details))
        st.cache_data.clear()
    else:
        st.error(f"ไม่พบ Mission ID: {mission_id} ในฐานข้อมูล")

def delete_mission(mission_id):
    if not sheet:
        st.error("ไม่สามารถลบได้: ยังไม่ได้เชื่อมต่อ Google Sheets")
        return
        
    cell = sheet.find(mission_id)
    if cell:
        sheet.delete_rows(cell.row)
        st.cache_data.clear()
        st.success("ลบข้อมูลจาก Google Sheets สำเร็จ!")

# ==========================================
# 4. ฟังก์ชันแสดงตาราง Dashboard (สามารถนำไปใช้ซ้ำได้)
# ==========================================
def render_dashboard(df):
    if not df.empty:
        filter_type = st.radio("มุมมองข้อมูล", ["สถิติสะสม (All-time)", "สถิติรายเดือน (Monthly)"], horizontal=True)
        
        df_filtered = df[df['Approval Status'] == 'อนุมัติแล้ว'].copy()
        if df_filtered.empty:
            st.info("ยังไม่มีภารกิจที่ได้รับการอนุมัติ")
            return
            
        df_filtered['Date_Obj'] = pd.to_datetime(df_filtered['Date'], errors='coerce')
        
        metric_label = "รวมภารกิจทั้งหมด (ครั้ง)"
        
        if filter_type == "สถิติรายเดือน (Monthly)":
            df_filtered['Month-Year'] = df_filtered['Date_Obj'].dt.strftime('%Y-%m')
            months_raw = sorted(df_filtered['Month-Year'].dropna().unique(), reverse=True)
            
            if months_raw:
                month_options = {raw: to_thai_month_year(raw) for raw in months_raw}
                selected_thai_month = st.selectbox("เลือกเดือน/ปี", list(month_options.values()))
                
                selected_raw_month = [k for k, v in month_options.items() if v == selected_thai_month][0]
                df_filtered = df_filtered[df_filtered['Month-Year'] == selected_raw_month]
                metric_label = f"จำนวนภารกิจในเดือน{selected_thai_month} (ครั้ง)"
                
        total_missions_count = len(df_filtered)
        
        # ค้นหาภารกิจล่าสุด (อ้างอิงจากวันที่ปฏิบัติงานจริง ที่ <= วันนี้)
        today = datetime.today().date()
        df_for_latest = df.copy()
        df_for_latest['Date_Obj'] = pd.to_datetime(df_for_latest['Date'], errors='coerce').dt.date
        past_missions = df_for_latest[df_for_latest['Date_Obj'] <= today]
        
        if not past_missions.empty:
            past_missions = past_missions.sort_values(by=['Date', 'Time'], ascending=[False, False])
            latest_row = past_missions.iloc[0]
            latest_name = latest_row['Mission Name']
            latest_date = to_thai_date(latest_row['Date'])
            latest_time = str(latest_row['Time'])[:5] if pd.notna(latest_row['Time']) and str(latest_row['Time']).strip() else ""
            latest_display = f"{latest_date}" + (f" เวลา {latest_time}" if latest_time else "")
        else:
            latest_name = "-"
            latest_display = "ยังไม่มีภารกิจ"
        
        # จัดเรียง 2 Metrics ไว้คู่กัน
        m_col1, m_col2 = st.columns(2)
        with m_col1:
            st.metric(label=metric_label, value=total_missions_count)
        with m_col2:
            st.metric(label="📌 ภารกิจล่าสุด", value=latest_name, delta=latest_display, delta_color="off")
            
        st.divider()
        
        # ==========================================
        # งานที่กำลังจะมาถึง (Upcoming Missions)
        # ==========================================
        st.subheader("🚀 งานที่กำลังจะมาถึง (Upcoming Missions)")
        
        today = datetime.today().date()
        upcoming_df = df_filtered.copy()
        upcoming_df['Date_Obj_DateOnly'] = pd.to_datetime(upcoming_df['Date'], errors='coerce').dt.date
        upcoming_df = upcoming_df[upcoming_df['Date_Obj_DateOnly'] >= today]
        
        # เรียงลำดับจากวันที่ใกล้จะถึงที่สุดขึ้นก่อน (Ascending)
        upcoming_df = upcoming_df.sort_values(by=['Date', 'Time'], ascending=[True, True])
        
        if not upcoming_df.empty:
            upcoming_display = upcoming_df[['Date', 'Time', 'Mission Name', 'Officers']].copy()
            upcoming_display['Date'] = upcoming_display['Date'].apply(to_thai_date)
            upcoming_display.rename(columns={
                "Date": "วันที่",
                "Time": "เวลา",
                "Mission Name": "ชื่อภารกิจ",
                "Officers": "เจ้าหน้าที่ปฏิบัติงาน"
            }, inplace=True)
            
            st.dataframe(
                upcoming_display,
                column_config={
                    "ชื่อภารกิจ": st.column_config.TextColumn("ชื่อภารกิจ", width="large"),
                    "เจ้าหน้าที่ปฏิบัติงาน": st.column_config.TextColumn("เจ้าหน้าที่ปฏิบัติงาน", width="large")
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("🎉 ไม่มีภารกิจที่กำลังจะมาถึงในช่วงเวลานี้")
            
        st.divider()
        st.subheader("🏆 สถิติการปฏิบัติงาน (Leaderboard)")
        
        stats = []
        for officer in OFFICERS:
            officer_missions = df_filtered[df_filtered['Officers'].fillna('').str.contains(officer)]
            total_missions = len(officer_missions)
            
            normal_inside = len(officer_missions[officer_missions['Day Type'] == 'วันทำงานปกติ (ในเวลา)'])
            normal_outside = len(officer_missions[officer_missions['Day Type'] == 'วันทำงานปกติ (นอกเวลา)'])
            
            holiday_days = len(officer_missions[officer_missions['Day Type'] == 'วันหยุด'])
            reports_done = len(df_filtered[df_filtered['Reporter'] == officer])
            stats.append({
                "ชื่อเจ้าหน้าที่": officer,
                "รวม": total_missions,
                "ปกติ (ในเวลา)": normal_inside,
                "ปกติ (นอกเวลา)": normal_outside,
                "วันหยุด": holiday_days,
                "ทำรายงาน": reports_done
            })
            
        stats_df = pd.DataFrame(stats)
        
        def highlight_min_red(s):
            is_min = s == s.min()
            return ['background-color: #ffcccc; color: black' if v else '' for v in is_min]

        def highlight_min_blue(s):
            is_min = s == s.min()
            return ['background-color: #cce5ff; color: black' if v else '' for v in is_min]
            
        def highlight_min_yellow(s):
            is_min = s == s.min()
            return ['background-color: #ffffe0; color: black' if v else '' for v in is_min]

        styled_df = (stats_df.style
                     .apply(highlight_min_red, subset=['วันหยุด'])
                     .apply(highlight_min_blue, subset=['ทำรายงาน'])
                     .apply(highlight_min_yellow, subset=['ปกติ (นอกเวลา)']))
        
        st.dataframe(styled_df, use_container_width=True, hide_index=True, height=500)
        
        st.markdown("""
        **คำอธิบายสีไฮไลท์ (ชี้เป้าคนที่ทำงานน้อยที่สุด):**
        - <span style="background-color:#ffffe0; color:black; padding:2px 5px;"> สีเหลืองอ่อน </span>: ผู้ที่มีสถิติออกเวร **ปกติ (นอกเวลา)** น้อยที่สุด
        - <span style="background-color:#ffcccc; color:black; padding:2px 5px;"> สีแดงอ่อน </span>: ผู้ที่มีสถิติออกเวร **วันหยุด** น้อยที่สุด
        - <span style="background-color:#cce5ff; color:black; padding:2px 5px;"> สีฟ้าอ่อน </span>: ผู้ที่มีสถิติ **การทำรายงาน** น้อยที่สุด
        """, unsafe_allow_html=True)
        
        st.divider()
        st.subheader("📋 ตารางแสดงประวัติภารกิจ (ตามช่วงเวลาที่เลือก)")
        
        history_df = df_filtered[['Mission ID', 'Mission Name', 'Date', 'Time', 'Day Type', 'Officers', 'Reporter', 'Report Status', 'Additional Details']].copy()
        history_df.reset_index(drop=True, inplace=True)
        history_df['Date'] = history_df['Date'].apply(to_thai_date)
        history_df.rename(columns={
            "Mission Name": "ชื่อภารกิจ",
            "Date": "วันที่",
            "Time": "เวลา",
            "Day Type": "ประเภทวัน",
            "Officers": "เจ้าหน้าที่ปฏิบัติงาน",
            "Reporter": "ผู้ทำรายงานผล",
            "Report Status": "สถานะรายงาน",
            "Additional Details": "รายละเอียดเพิ่มเติม/การเบิกจ่าย"
        }, inplace=True)
        
        st.markdown("💡 **Tip:** คุณสามารถคลิกที่ช่อง **'สถานะรายงาน'** หรือ **'รายละเอียดเพิ่มเติม'** ในตารางด้านล่าง เพื่อพิมพ์ข้อมูลอัปเดตได้เลย")
        
        edited_df = st.data_editor(
            history_df,
            column_config={
                "Mission ID": None, # ซ่อนไอดีไว้ไม่ต้องให้ User เห็น
                "ชื่อภารกิจ": st.column_config.TextColumn("ชื่อภารกิจ", width="large", disabled=True),
                "วันที่": st.column_config.TextColumn("วันที่", disabled=True),
                "เวลา": st.column_config.TextColumn("เวลา", disabled=True),
                "ประเภทวัน": st.column_config.TextColumn("ประเภทวัน", disabled=True),
                "เจ้าหน้าที่ปฏิบัติงาน": st.column_config.TextColumn("เจ้าหน้าที่ปฏิบัติงาน", width="large", disabled=True),
                "ผู้ทำรายงานผล": st.column_config.TextColumn("ผู้ทำรายงานผล", disabled=True),
                "สถานะรายงาน": st.column_config.SelectboxColumn("สถานะรายงาน", options=["ยังไม่ส่ง", "ส่งแล้ว"], disabled=False),
                "รายละเอียดเพิ่มเติม/การเบิกจ่าย": st.column_config.TextColumn("รายละเอียดเพิ่มเติม/การเบิกจ่าย", width="large", disabled=False)
            },
            use_container_width=True,
            hide_index=True,
            key="report_editor"
        )
        
        if st.session_state.get("report_editor") and st.session_state["report_editor"]["edited_rows"]:
            if st.button("💾 ยืนยันการบันทึกการแก้ไขรายงาน", type="primary"):
                changes_count = 0
                edited_rows = st.session_state["report_editor"]["edited_rows"]
                
                for idx_str, changes in edited_rows.items():
                    idx = int(idx_str)
                    m_id = history_df.iloc[idx]['Mission ID']
                    # ค่าเริ่มต้นเป็นค่าเดิมใน history_df
                    new_status = changes.get("สถานะรายงาน", history_df.iloc[idx]['สถานะรายงาน'])
                    new_details = changes.get("รายละเอียดเพิ่มเติม/การเบิกจ่าย", history_df.iloc[idx]['รายละเอียดเพิ่มเติม/การเบิกจ่าย'])
                    
                    update_mission_details(m_id, new_status, new_details)
                    changes_count += 1
                
                if changes_count > 0:
                    st.success(f"อัปเดตข้อมูลรายงานสำเร็จ {changes_count} รายการ!")
                    # Clear session state so the save button disappears
                    del st.session_state["report_editor"]
                    st.cache_data.clear()
                    time.sleep(1)
                    st.rerun()
        
    else:
        st.info("ยังไม่มีข้อมูลสำหรับแสดงสถิติ กรุณาบันทึกข้อมูลก่อน")

# ==========================================
# 5. UI Components (Main Structure)
# ==========================================

# ระบบล็อกรหัสผ่านสำหรับ Admin
if "is_admin" not in st.session_state:
    st.session_state["is_admin"] = False

with st.sidebar:
    st.markdown("### 🔐 เข้าสู่ระบบ Admin")
    if not st.session_state["is_admin"]:
        password_input = st.text_input("รหัสผ่านจัดการข้อมูล", type="password")
        # ใช้รหัสผ่านจาก Streamlit Secrets (ถ้าไม่มีให้ใช้ nacc1234 เป็นค่าเริ่มต้น)
        correct_password = st.secrets.get("admin_password", "nacc1234")
        if st.button("เข้าสู่ระบบ"):
            if password_input == correct_password:
                st.session_state["is_admin"] = True
                st.rerun()
            elif password_input != "":
                st.error("รหัสผ่านไม่ถูกต้อง")
    else:
        st.success("✅ สถานะ: Admin")
        if st.button("ออกจากระบบ"):
            st.session_state["is_admin"] = False
            st.rerun()
            
    st.divider()
    
    # ถ้าเป็น Admin จะเห็นครบทุกเมนู, ถ้าไม่ใช่จะเห็นแค่ Dashboard
    if st.session_state["is_admin"]:
        menu = ["📊 ข้อมูลภารกิจ VIP Protection", "📝 ลงข้อมูลภารกิจ", "✅ ภารกิจรอเห็นชอบ", "✏️ การแก้ไข/ลบ"]
    else:
        menu = ["📊 ข้อมูลภารกิจ VIP Protection"]
        
    choice = st.radio("เมนูนำทาง", menu)

if choice == "📝 ลงข้อมูลภารกิจ" and st.session_state["is_admin"]:
    st.header("📝 ระบบจัดการภารกิจรักษาความปลอดภัย (Admin)")
    df = get_data()
    
    col_left, col_right = st.columns([1, 2.5])
    
    with col_left:
        st.subheader("✍️ ฟอร์มบันทึกภารกิจ")
        
        mission_name = st.text_area("ชื่อภารกิจ", height=100)
        
        date, date_error = thai_date_picker("วันที่ปฏิบัติงาน", key_prefix="entry")
        if date_error:
            st.error(date_error)
            
        time_val = st.time_input("เวลานัดหมาย / เวลาปฏิบัติงาน")
        day_type = st.selectbox("ประเภทวัน", DAY_TYPES)
        
        officer_stats = {}
        for officer in OFFICERS:
            if not df.empty:
                count = len(df[(df['Officers'].fillna('').str.contains(officer)) & (df['Day Type'] == day_type)])
            else:
                count = 0
            officer_stats[officer] = count
            
        sorted_officers = sorted(officer_stats.items(), key=lambda x: x[1])
        
        if day_type == "วันหยุด" or day_type == "วันทำงานปกติ (นอกเวลา)":
            top_3 = sorted_officers[:3]
            suggestion_text = ", ".join([f"**{name}** ({count} ครั้ง)" for name, count in top_3])
            st.info(f"💡 **Smart Suggestion:** ผู้ที่มีสถิติ **{day_type}** น้อยที่สุด 3 อันดับแรก คือ {suggestion_text}")
            
        dynamic_officer_options = [f"{name} ({day_type}: {count} ครั้ง)" for name, count in officer_stats.items()]
        selected_dynamic_officers = st.multiselect("เจ้าหน้าที่ปฏิบัติงาน", dynamic_officer_options)
        
        reporter_options = selected_dynamic_officers if selected_dynamic_officers else ["กรุณาเลือกเจ้าหน้าที่ปฏิบัติงานก่อน"]
        reporter = st.selectbox("ผู้ทำรายงานผล", options=reporter_options)
        
        submit = st.button("💾 บันทึกข้อมูล", type="primary")
        
        if submit:
            if not mission_name or not selected_dynamic_officers:
                st.error("กรุณากรอกข้อมูลให้ครบถ้วน")
            elif date_error:
                st.error("ไม่สามารถบันทึกได้ กรุณาตรวจสอบวันที่ให้ถูกต้อง")
            elif reporter == "กรุณาเลือกเจ้าหน้าที่ปฏิบัติงานก่อน":
                st.error("กรุณาระบุผู้ทำรายงานผล")
            else:
                add_mission(mission_name, date, time_val, day_type, selected_dynamic_officers, reporter)
                st.rerun()

    with col_right:
        st.subheader("📊 สถิติการปฏิบัติงาน")
        render_dashboard(df)

elif choice == "✅ ภารกิจรอเห็นชอบ" and st.session_state["is_admin"]:
    st.header("✅ ระบบจัดการการอนุมัติภารกิจ (รอเห็นชอบ)")
    df = get_data()
    pending_df = df[df['Approval Status'] == 'รอเห็นชอบ'].copy()
    
    if not pending_df.empty:
        st.subheader(f"รายการที่รอเห็นชอบ ({len(pending_df)} รายการ)")
        
        for idx, row in pending_df.iterrows():
            date_str = to_thai_date(row['Date'])
            time_str = str(row['Time'])[:5]
            time_display = f" เวลา {time_str}" if time_str else ""
            
            with st.container(border=True):
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"**ภารกิจ:** {row['Mission Name']}")
                    st.markdown(f"**วัน/เวลา:** {date_str}{time_display}")
                    st.markdown(f"**เจ้าหน้าที่:** {row['Officers']}")
                with col2:
                    st.write("") # เว้นบรรทัด
                    st.write("") 
                    if st.button("✅ ยืนยันเห็นชอบ", key=f"app_{row['Mission ID']}", type="primary"):
                        approve_mission(row['Mission ID'])
                        st.rerun()
    else:
        st.success("🎉 ไม่มีภารกิจที่รอเห็นชอบในขณะนี้")

elif choice == "✏️ การแก้ไข/ลบ" and st.session_state["is_admin"]:
    st.header("แก้ไข / ลบ ข้อมูลภารกิจ")
    df = get_data()
    if not df.empty:
        df['Thai Date'] = df['Date'].apply(to_thai_date)
        df['Time'] = df['Time'].fillna('').astype(str)
        display_time = df['Time'].apply(lambda x: f" เวลา {x[:5]}" if x.strip() != "" else "")
        
        mission_list = df['Mission Name'] + " (" + df['Thai Date'] + display_time + ")"
        
        selected_mission_str = st.selectbox("เลือกภารกิจที่ต้องการจัดการ", mission_list)
        idx = mission_list[mission_list == selected_mission_str].index[0]
        selected_data = df.iloc[idx]
        mission_id = selected_data['Mission ID']
        
        new_name = st.text_area("ชื่อภารกิจ", value=selected_data['Mission Name'], height=100)
        
        try:
            current_date = datetime.strptime(str(selected_data['Date']), '%Y-%m-%d').date()
        except:
            current_date = datetime.today().date()
            
        try:
            time_str = str(selected_data['Time'])
            current_time = datetime.strptime(time_str[:8], '%H:%M:%S').time() if time_str else datetime.now().time()
        except:
            current_time = datetime.now().time()

        new_date, date_error = thai_date_picker("วันที่ปฏิบัติงาน", default_date=current_date, key_prefix="edit")
        if date_error:
            st.error(date_error)
            
        new_time = st.time_input("เวลานัดหมาย / เวลาปฏิบัติงาน", value=current_time)
        
        new_day_type = st.selectbox("ประเภทวัน", DAY_TYPES, index=DAY_TYPES.index(selected_data['Day Type']) if selected_data['Day Type'] in DAY_TYPES else 0)
        
        current_officers = [x.strip() for x in str(selected_data['Officers']).split(',')]
        valid_current_officers = [x for x in current_officers if x in OFFICERS]
        new_officers = st.multiselect("เจ้าหน้าที่ปฏิบัติงาน (แก้ไข)", OFFICERS, default=valid_current_officers)
        
        options_for_reporter = new_officers if new_officers else ["กรุณาเลือกเจ้าหน้าที่ปฏิบัติงานก่อน"]
        if selected_data['Reporter'] in options_for_reporter:
            default_reporter_idx = options_for_reporter.index(selected_data['Reporter'])
        else:
            default_reporter_idx = 0
            
        new_reporter = st.selectbox("ผู้ทำรายงานผล (แก้ไข)", options=options_for_reporter, index=default_reporter_idx)
        
        col_btn1, col_btn2 = st.columns([1, 5])
        with col_btn1:
            update_btn = st.button("💾 บันทึกการแก้ไข", type="primary")
        with col_btn2:
            delete_btn = st.button("🗑️ ลบภารกิจนี้")
            
        if delete_btn:
            delete_mission(mission_id)
            st.rerun()
            
        if update_btn:
            if options_for_reporter[0] == "กรุณาเลือกเจ้าหน้าที่ปฏิบัติงานก่อน":
                 st.error("กรุณาระบุเจ้าหน้าที่และผู้ทำรายงานผล")
            elif date_error:
                 st.error("ไม่สามารถบันทึกการแก้ไขได้ กรุณาตรวจสอบวันที่ให้ถูกต้อง")
            else:
                 update_mission(mission_id, new_name, new_date, new_time, new_day_type, new_officers, new_reporter)
    else:
        st.info("ยังไม่มีข้อมูลภารกิจในระบบ")

elif choice == "📊 ข้อมูลภารกิจ VIP Protection":
    st.header("📊 สถิติภารกิจรักษาความปลอดภัย (Dashboard)")
    df = get_data()
    render_dashboard(df)
