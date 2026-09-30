from flask import Blueprint, request, jsonify
from db import get_db_connection
from api.api_login import extract_token_from_request, verify_token
import json
from datetime import datetime

attendance_bp = Blueprint('attendance_bp', __name__)

# Helper to parse JSON or form request body
def get_request_data():
    data = request.get_json(force=True, silent=True)
    if data is not None:
        return data
    if request.form:
        return request.form.to_dict()
    if request.data:
        try:
            return json.loads(request.data.decode('utf-8'))
        except Exception:
            pass
    return {}

# Helper to ensure attendance table exists with all required columns
def ensure_attendance_table(cursor):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS attendance (
                attendance_id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                class_id INT NOT NULL,
                teacher_id INT NULL,
                attendance_date DATE NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'present',
                period VARCHAR(120) DEFAULT 'ពេញមួយថ្ងៃ (07:00 - 16:30)',
                reason TEXT NULL,
                guardian_note VARCHAR(255) NULL,
                recorded_by VARCHAR(100) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                KEY idx_att_class_date (class_id, attendance_date),
                KEY idx_att_student (student_id),
                KEY idx_att_teacher (teacher_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # Check existing columns and alter table if any column is missing
        cursor.execute("SHOW COLUMNS FROM attendance")
        cols = [r['Field'] if isinstance(r, dict) else r[0] for r in cursor.fetchall()]

        if "class_id" not in cols:
            cursor.execute("ALTER TABLE attendance ADD COLUMN class_id INT NOT NULL DEFAULT 1")
        if "teacher_id" not in cols:
            cursor.execute("ALTER TABLE attendance ADD COLUMN teacher_id INT NULL")
        if "attendance_date" not in cols:
            if "date" in cols:
                cursor.execute("ALTER TABLE attendance CHANGE COLUMN `date` `attendance_date` DATE NOT NULL")
            else:
                cursor.execute("ALTER TABLE attendance ADD COLUMN attendance_date DATE NOT NULL")
        if "status" not in cols:
            cursor.execute("ALTER TABLE attendance ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'present'")
        if "period" not in cols:
            cursor.execute("ALTER TABLE attendance ADD COLUMN period VARCHAR(120) DEFAULT 'ពេញមួយថ្ងៃ (07:00 - 16:30)'")
        if "reason" not in cols:
            cursor.execute("ALTER TABLE attendance ADD COLUMN reason TEXT NULL")
        if "guardian_note" not in cols:
            cursor.execute("ALTER TABLE attendance ADD COLUMN guardian_note VARCHAR(255) NULL")
        if "recorded_by" not in cols:
            cursor.execute("ALTER TABLE attendance ADD COLUMN recorded_by VARCHAR(100) NULL")

    except Exception as err:
        print("Attendance table init check / migration error:", err)

# Helper function to auto-resolve teacher_id
def resolve_teacher_id(cursor, teacher_id=None, recorded_by=None, class_id=None):
    if teacher_id:
        return teacher_id

    # 1. From Token
    token = extract_token_from_request()
    if token:
        payload, _ = verify_token(token)
        if payload:
            if payload.get("teacher_id"):
                return payload.get("teacher_id")
            uname = payload.get("username") or payload.get("full_name") or payload.get("name")
            if uname:
                cursor.execute("SELECT teacher_id FROM teachers WHERE full_name = %s OR teacher_code = %s LIMIT 1", (uname, uname))
                t_row = cursor.fetchone()
                if t_row:
                    return t_row["teacher_id"]

    # 2. From recorded_by name
    if recorded_by and recorded_by not in ["គ្រូបន្ទុកថ្នាក់", "System", "Admin"]:
        cursor.execute("SELECT teacher_id FROM teachers WHERE full_name = %s OR teacher_code = %s LIMIT 1", (recorded_by, recorded_by))
        t_row = cursor.fetchone()
        if t_row:
            return t_row["teacher_id"]

    # 3. From class_id via teacher_classes
    if class_id:
        cursor.execute("SELECT teacher_id FROM teacher_classes WHERE class_id = %s LIMIT 1", (class_id,))
        tc_row = cursor.fetchone()
        if tc_row and tc_row.get("teacher_id"):
            return tc_row["teacher_id"]

    # 4. Fallback to first teacher in teachers table
    try:
        cursor.execute("SELECT teacher_id FROM teachers ORDER BY teacher_id ASC LIMIT 1")
        t_fallback = cursor.fetchone()
        if t_fallback:
            return t_fallback["teacher_id"]
    except Exception:
        pass

# ----------------------------------------------------
# 0. GET SCHOOL-WIDE ATTENDANCE SUMMARY & CLASS RANKINGS
# ----------------------------------------------------
@attendance_bp.route("/api/attendance/summary", methods=["GET"])
def get_attendance_summary():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_attendance_table(cursor)

        # 1. Total active students count
        cursor.execute("SELECT COUNT(*) as total_students FROM students")
        total_students_res = cursor.fetchone()
        total_students = total_students_res["total_students"] if total_students_res else 0

        # 2. Total attendance overview (Present, Leave, Absent)
        cursor.execute("SELECT COUNT(*) as cnt FROM attendance WHERE status = 'leave'")
        excused_res = cursor.fetchone()
        excused_total = excused_res["cnt"] if excused_res else 0

        cursor.execute("SELECT COUNT(*) as cnt FROM attendance WHERE status = 'absent'")
        unexcused_res = cursor.fetchone()
        unexcused_total = unexcused_res["cnt"] if unexcused_res else 0

        total_absences = excused_total + unexcused_total
        
        # Calculate attendance rate
        if total_students > 0:
            rate = max(0, min(100, round(100 - ((unexcused_total + (excused_total * 0.3)) / (total_students * 20 or 1)) * 100, 1)))
        else:
            rate = 100.0

        present_estimate = max(0, total_students - unexcused_total - excused_total)

        # 3. Monthly statistics (Current Year)
        current_year = datetime.now().year
        cursor.execute("""
            SELECT 
                MONTH(attendance_date) as month_num,
                SUM(CASE WHEN status = 'leave' THEN 1 ELSE 0 END) as excused_cnt,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as unexcused_cnt
            FROM attendance
            WHERE YEAR(attendance_date) = %s
            GROUP BY MONTH(attendance_date)
            ORDER BY month_num ASC
        """, (current_year,))
        monthly_rows = cursor.fetchall()
        
        monthly_stats = {
            "labels": ["មករា", "កុម្ភៈ", "មីនា", "មេសា", "ឧសភា", "មិថុនា", "កក្កដា", "សីហា", "កញ្ញា", "តុលា", "វិច្ឆិកា", "ធ្នូ"],
            "excused": [0]*12,
            "unexcused": [0]*12
        }
        for r in monthly_rows:
            m_idx = int(r["month_num"]) - 1
            if 0 <= m_idx < 12:
                monthly_stats["excused"][m_idx] = int(r["excused_cnt"] or 0)
                monthly_stats["unexcused"][m_idx] = int(r["unexcused_cnt"] or 0)

        # 4. Yearly statistics
        cursor.execute("""
            SELECT 
                YEAR(attendance_date) as yr,
                SUM(CASE WHEN status = 'leave' THEN 1 ELSE 0 END) as excused_cnt,
                SUM(CASE WHEN status = 'absent' THEN 1 ELSE 0 END) as unexcused_cnt
            FROM attendance
            GROUP BY YEAR(attendance_date)
            ORDER BY yr ASC
        """)
        yearly_rows = cursor.fetchall()
        yearly_labels = []
        yearly_excused = []
        yearly_unexcused = []
        for yr_row in yearly_rows:
            if yr_row.get("yr"):
                yearly_labels.append(f"ឆ្នាំ {yr_row['yr']}")
                yearly_excused.append(int(yr_row["excused_cnt"] or 0))
                yearly_unexcused.append(int(yr_row["unexcused_cnt"] or 0))
        
        if not yearly_labels:
            yearly_labels = [f"ឆ្នាំ {current_year-1}", f"ឆ្នាំ {current_year}"]
            yearly_excused = [excused_total, excused_total]
            yearly_unexcused = [unexcused_total, unexcused_total]

        # 5. Classes breakdown & Highest absences ranking
        cursor.execute("""
            SELECT 
                c.class_id, 
                c.class_name, 
                c.grade, 
                c.room,
                t.teacher_id,
                t.full_name as teacher_name,
                t.gender as teacher_gender,
                COUNT(DISTINCT sc.student_id) as total_students
            FROM classes c
            LEFT JOIN teacher_classes tc ON c.class_id = tc.class_id
            LEFT JOIN teachers t ON tc.teacher_id = t.teacher_id
            LEFT JOIN student_classes sc ON c.class_id = sc.class_id
            GROUP BY c.class_id, t.teacher_id
            ORDER BY c.class_id ASC
        """)
        classes_rows = cursor.fetchall()

        # Query all absences with student and class info
        cursor.execute("""
            SELECT 
                a.attendance_id,
                a.student_id,
                a.class_id,
                a.teacher_id,
                DATE_FORMAT(a.attendance_date, '%Y-%m-%d') as attendance_date,
                a.status,
                a.period,
                a.reason,
                a.guardian_note,
                a.recorded_by,
                s.student_code,
                s.full_name as student_name,
                s.gender as student_gender,
                s.phone as student_phone,
                t.full_name as teacher_name
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            LEFT JOIN teachers t ON a.teacher_id = t.teacher_id
            ORDER BY a.attendance_date DESC
        """)
        all_att = cursor.fetchall()

        classes_list = []
        risk_classes_count = 0

        for c_row in classes_rows:
            cid = c_row["class_id"]
            class_records = [r for r in all_att if r["class_id"] == cid]
            
            excused_cnt = sum(1 for r in class_records if r["status"] == "leave")
            unexcused_cnt = sum(1 for r in class_records if r["status"] == "absent")
            total_absent_cnt = excused_cnt + unexcused_cnt
            st_count = c_row["total_students"] or 0

            # Determine risk level
            if unexcused_cnt >= 5 or total_absent_cnt >= 10:
                risk_level = "🔴 ខ្ពស់បំផុត"
                risk_badge_class = "bg-danger text-white"
                risk_classes_count += 1
            elif unexcused_cnt >= 2 or total_absent_cnt >= 5:
                risk_level = "🟡 មធ្យម"
                risk_badge_class = "bg-warning text-dark"
            else:
                risk_level = "🟢 ទាប/ធម្មតា"
                risk_badge_class = "bg-success text-white"

            # Calculate class attendance rate
            if st_count > 0:
                class_rate_pct = max(70, min(100, round(100 - ((unexcused_cnt + (excused_cnt * 0.4)) / (st_count * 15 or 1)) * 100)))
            else:
                class_rate_pct = 100

            # Group student absence records inside this class
            student_group = {}
            for r in class_records:
                sid = r["student_id"]
                if sid not in student_group:
                    student_group[sid] = {
                        "student_id": r.get("student_code") or f"STD-{sid}",
                        "raw_id": sid,
                        "name": r["student_name"],
                        "gender": r["student_gender"] or "ប្រុស",
                        "phone": r.get("student_phone") or "012 345 678",
                        "parent_name": f"អាណាព្យាបាល {r['student_name']}",
                        "parent_phone": r.get("student_phone") or "012 345 678",
                        "excused_count": 0,
                        "unexcused_count": 0,
                        "total_days": 0,
                        "latest_date": r["attendance_date"],
                        "status": "តាមដាន ⚠️" if r["status"] == "absent" else "សកម្ម",
                        "dates": []
                    }
                
                if r["status"] == "leave":
                    student_group[sid]["excused_count"] += 1
                else:
                    student_group[sid]["unexcused_count"] += 1
                student_group[sid]["total_days"] += 1

                student_group[sid]["dates"].append({
                    "attendance_id": r["attendance_id"],
                    "date": r["attendance_date"],
                    "dateKhmer": f"កាលបរិច្ឆេទ: {r['attendance_date']}",
                    "type": r["status"],
                    "period": r["period"] or "ពេញមួយថ្ងៃ (០៧:០០ - ១៦:៣០)",
                    "reason": r["reason"] or ("អវត្តមានមានច្បាប់" if r["status"] == "leave" else "អវត្តមានអត់ច្បាប់"),
                    "guardianNote": r["guardian_note"] or "គ្មានដំណឹងបន្ថែម",
                    "action": "បានកត់ត្រាក្នុងបញ្ជីវត្តមាន"
                })

            t_gender = (c_row.get("teacher_gender") or "").lower()
            default_avatar = 'https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=80&auto=format&fit=crop&q=80' if 'fem' in t_gender else 'https://images.unsplash.com/photo-1472099645785-5658abf4ff4e?w=80&auto=format&fit=crop&q=80'

            classes_list.append({
                "id": f"CLS-{cid}",
                "class_id": cid,
                "class_name": c_row["class_name"] or f"ថ្នាក់ទី {c_row['grade']}",
                "teacher": c_row["teacher_name"] or "មិនទាន់មានគ្រូបន្ទុក",
                "teacher_avatar": c_row.get("teacher_photo") or default_avatar,
                "room": c_row["room"] or "បន្ទប់ ៣០២",
                "total_students": st_count,
                "risk_level": risk_level,
                "risk_badge_class": risk_badge_class,
                "excused_days": excused_cnt,
                "unexcused_days": unexcused_cnt,
                "total_absent_days": total_absent_cnt,
                "attendance_rate": f"{class_rate_pct}%",
                "students": list(student_group.values())
            })

        # Sort classes by total absent days descending (highest absences first)
        classes_list.sort(key=lambda x: (x["total_absent_days"], x["unexcused_days"]), reverse=True)

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "kpi": {
                "total_students": total_students,
                "present_count": present_estimate,
                "attendance_rate": f"{rate}%",
                "excused_count": excused_total,
                "unexcused_count": unexcused_total,
                "risk_classes_count": risk_classes_count
            },
            "charts": {
                "monthly": monthly_stats,
                "yearly": {
                    "labels": yearly_labels,
                    "excused": yearly_excused,
                    "unexcused": yearly_unexcused
                }
            },
            "highest_absent_classes": classes_list
        }), 200

    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 1. GET ATTENDANCE LIST (Filtered by Teacher's Class)
# ----------------------------------------------------
@attendance_bp.route("/api/attendance", methods=["GET"])
def get_attendance():
    """
    Fetch attendance records strictly for students belonging to the teacher's class.
    Query params: ?class_id=X&teacher_id=Y&date=YYYY-MM-DD&month=YYYY-MM
    """
    class_id = request.args.get("class_id")
    teacher_id = request.args.get("teacher_id")
    target_date = request.args.get("date")
    target_month = request.args.get("month")
    student_id = request.args.get("student_id")

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_attendance_table(cursor)

        # 1. If teacher_id is provided without class_id, find teacher's homeroom class
        if teacher_id and not class_id:
            cursor.execute("""
                SELECT tc.class_id, c.class_name 
                FROM teacher_classes tc
                JOIN classes c ON tc.class_id = c.class_id
                WHERE tc.teacher_id = %s
                LIMIT 1
            """, (teacher_id,))
            t_class = cursor.fetchone()
            if t_class:
                class_id = t_class["class_id"]

        # 2. Get students of this class
        students = []
        if class_id:
            cursor.execute("""
                SELECT 
                    s.student_id, 
                    s.student_code, 
                    s.full_name, 
                    s.gender, 
                    s.date_of_birth,
                    s.phone,
                    c.class_id, 
                    c.class_name,
                    c.grade,
                    c.room
                FROM students s
                JOIN student_classes sc ON s.student_id = sc.student_id
                JOIN classes c ON sc.class_id = c.class_id
                WHERE c.class_id = %s
                ORDER BY s.full_name ASC
            """, (class_id,))
            students = cursor.fetchall()
        else:
            cursor.execute("""
                SELECT 
                    s.student_id, 
                    s.student_code, 
                    s.full_name, 
                    s.gender, 
                    s.date_of_birth,
                    s.phone,
                    c.class_id, 
                    c.class_name,
                    c.grade,
                    c.room
                FROM students s
                LEFT JOIN student_classes sc ON s.student_id = sc.student_id
                LEFT JOIN classes c ON sc.class_id = c.class_id
                ORDER BY s.student_id ASC
                LIMIT 100
            """)
            students = cursor.fetchall()

        # 3. Query Attendance records with teacher details
        query = """
            SELECT 
                a.attendance_id,
                a.student_id,
                a.class_id,
                a.teacher_id,
                DATE_FORMAT(a.attendance_date, '%Y-%m-%d') as attendance_date,
                a.status,
                a.period,
                a.reason,
                a.guardian_note,
                a.recorded_by,
                s.student_code,
                s.full_name as student_name,
                s.gender,
                t.full_name as teacher_name,
                t.teacher_code
            FROM attendance a
            JOIN students s ON a.student_id = s.student_id
            LEFT JOIN teachers t ON a.teacher_id = t.teacher_id
            WHERE 1=1
        """
        params = []

        if class_id:
            query += " AND a.class_id = %s"
            params.append(class_id)
        if target_date:
            query += " AND a.attendance_date = %s"
            params.append(target_date)
        if target_month:
            query += " AND DATE_FORMAT(a.attendance_date, '%Y-%m') = %s"
            params.append(target_month)
        if student_id:
            query += " AND a.student_id = %s"
            params.append(student_id)

        query += " ORDER BY a.attendance_date DESC, a.attendance_id DESC"
        cursor.execute(query, tuple(params))
        attendance_rows = cursor.fetchall()

        # 4. Map records per student
        student_attendance_map = {}
        for row in attendance_rows:
            st_id = row["student_id"]
            if st_id not in student_attendance_map:
                student_attendance_map[st_id] = []
            student_attendance_map[st_id].append({
                "id": f"REC-{row['attendance_id']}",
                "attendance_id": row["attendance_id"],
                "teacher_id": row["teacher_id"],
                "teacher_name": row.get("teacher_name") or row.get("recorded_by") or "គ្រូបន្ទុកថ្នាក់",
                "teacher_code": row.get("teacher_code") or "",
                "recorded_by": row["recorded_by"] or row.get("teacher_name") or "គ្រូបន្ទុកថ្នាក់",
                "date": row["attendance_date"],
                "period": row["period"] or "ពេញមួយថ្ងៃ (07:00 - 16:30)",
                "type": row["status"],
                "reason": row["reason"] or "",
                "guardianNote": row["guardian_note"] or "គ្មានលិខិត"
            })

        # Today's date
        today_str = target_date or datetime.now().strftime('%Y-%m-%d')

        student_list_result = []
        total_present = 0
        total_leave = 0
        total_absent = 0

        for st in students:
            st_id = st["student_id"]
            history = student_attendance_map.get(st_id, [])

            # Check status for today
            today_record = next((r for r in history if r["date"] == today_str), None)
            status_today = today_record["type"] if today_record else "present"

            leave_count = sum(1 for r in history if r["type"] == "leave")
            absent_count = sum(1 for r in history if r["type"] == "absent")

            if status_today == "present":
                total_present += 1
            elif status_today == "leave":
                total_leave += 1
            elif status_today == "absent":
                total_absent += 1

            student_list_result.append({
                "student_id": st["student_id"],
                "id": st.get("student_code") or f"STD-{st['student_id']}",
                "name": st.get("full_name") or "សិស្ស",
                "gender": st.get("gender") or "Male",
                "class_id": st.get("class_id"),
                "class_name": st.get("class_name") or "ថ្នាក់",
                "statusToday": status_today,
                "leaveDays": leave_count,
                "absentDays": absent_count,
                "totalAbsences": len(history),
                "absenceHistory": history
            })

        total_students = len(student_list_result)
        rate_pct = round((total_present / total_students) * 100, 1) if total_students > 0 else 100.0

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "class_id": class_id,
            "teacher_id": teacher_id,
            "date": today_str,
            "summary": {
                "total_students": total_students,
                "present_count": total_present,
                "leave_count": total_leave,
                "absent_count": total_absent,
                "attendance_rate": f"{rate_pct}%"
            },
            "students": student_list_result,
            "raw_records": attendance_rows
        }), 200

    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 2. POST RECORD OR UPDATE ATTENDANCE (Single Entry)
# ----------------------------------------------------
@attendance_bp.route("/api/attendance", methods=["POST"])
@attendance_bp.route("/api/attendance/record", methods=["POST"])
def record_attendance():
    data = get_request_data()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    student_id = data.get("student_id")
    student_code = data.get("student_code") or data.get("id")
    class_id = data.get("class_id")
    teacher_id = data.get("teacher_id")
    att_date = data.get("date") or data.get("attendance_date") or datetime.now().strftime('%Y-%m-%d')
    status = data.get("status") or data.get("type") or "present"
    period = data.get("period") or "ពេញមួយថ្ងៃ (07:00 - 16:30)"
    reason = data.get("reason") or data.get("notes") or ""
    guardian_note = data.get("guardian_note") or data.get("guardianNote") or ""
    recorded_by = data.get("recorded_by") or "គ្រូបន្ទុកថ្នាក់"

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_attendance_table(cursor)

        # 0. Enforce Active Academic Year Check
        cursor.execute("SELECT academic_year_id, academic_year FROM academic_years WHERE status = 'Active' LIMIT 1")
        active_yr = cursor.fetchone()
        if not active_yr:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "code": "ACADEMIC_YEAR_LOCKED",
                "message": "មិនអាចកត់ត្រាវត្តមាន ឬអវត្តមានបានឡើយ ដោយសារបច្ចុប្បន្នមិនទាន់មានឆ្នាំសិក្សាសកម្មដែលបានបើកដំណើរការ (No Active Academic Year)!"
            }), 403

        # 1. Resolve student_id and verify class
        if not student_id and student_code:
            cursor.execute("SELECT student_id, full_name FROM students WHERE student_code = %s", (student_code,))
            s_row = cursor.fetchone()
            if s_row:
                student_id = s_row["student_id"]
            else:
                return jsonify({"status": "error", "message": f"រកមិនឃើញសិស្សដែលមានអត្តលេខ {student_code} ឡើយ"}), 404

        if not student_id:
            return jsonify({"status": "error", "message": "សូមជ្រើសរើសសិស្សដើម្បីកត់ត្រាវត្តមាន (Student is required)"}), 400

        # 2. Verify student's class
        if not class_id:
            cursor.execute("SELECT class_id FROM student_classes WHERE student_id = %s LIMIT 1", (student_id,))
            sc = cursor.fetchone()
            if sc:
                class_id = sc["class_id"]
            else:
                class_id = 1

        # 3. Auto-resolve teacher_id if missing
        teacher_id = resolve_teacher_id(cursor, teacher_id=teacher_id, recorded_by=recorded_by, class_id=class_id)

        # Check if attendance record for same student, date, and period already exists
        cursor.execute("""
            SELECT attendance_id FROM attendance 
            WHERE student_id = %s AND attendance_date = %s AND period = %s
        """, (student_id, att_date, period))
        existing = cursor.fetchone()

        if existing:
            if status == "present":
                # If marked present and had absence entry, remove it
                cursor.execute("DELETE FROM attendance WHERE attendance_id = %s", (existing["attendance_id"],))
                target_id = existing["attendance_id"]
                conn.commit()
            else:
                cursor.execute("""
                    UPDATE attendance 
                    SET status = %s, reason = %s, guardian_note = %s, recorded_by = %s, class_id = %s, teacher_id = %s
                    WHERE attendance_id = %s
                """, (status, reason, guardian_note, recorded_by, class_id, teacher_id, existing["attendance_id"]))
                target_id = existing["attendance_id"]
                conn.commit()
        else:
            if status != "present":
                cursor.execute("""
                    INSERT INTO attendance (student_id, class_id, teacher_id, attendance_date, status, period, reason, guardian_note, recorded_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (student_id, class_id, teacher_id, att_date, status, period, reason, guardian_note, recorded_by))
                target_id = cursor.lastrowid
                conn.commit()
            else:
                target_id = None

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានកត់ត្រាវត្តមានសិស្សដោយជោគជ័យ!",
            "attendance_id": target_id,
            "student_id": student_id,
            "class_id": class_id,
            "teacher_id": teacher_id,
            "status": status,
            "date": att_date
        }), 201

    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 3. POST BATCH ATTENDANCE FOR AN ENTIRE CLASS
# ----------------------------------------------------
@attendance_bp.route("/api/attendance/batch", methods=["POST"])
def batch_record_attendance():
    data = get_request_data()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    class_id = data.get("class_id")
    teacher_id = data.get("teacher_id")
    att_date = data.get("date") or datetime.now().strftime('%Y-%m-%d')
    records = data.get("records") or []

    if not isinstance(records, list) or len(records) == 0:
        return jsonify({"status": "error", "message": "No student attendance records provided"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_attendance_table(cursor)

        # 0. Enforce Active Academic Year Check
        cursor.execute("SELECT academic_year_id, academic_year FROM academic_years WHERE status = 'Active' LIMIT 1")
        active_yr = cursor.fetchone()
        if not active_yr:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "code": "ACADEMIC_YEAR_LOCKED",
                "message": "មិនអាចកត់ត្រាវត្តមាន ឬអវត្តមានបានឡើយ ដោយសារបច្ចុប្បន្នមិនទាន់មានឆ្នាំសិក្សាសកម្មដែលបានបើកដំណើរការ (No Active Academic Year)!"
            }), 403

        teacher_id = resolve_teacher_id(cursor, teacher_id=teacher_id, class_id=class_id)

        saved_count = 0
        for item in records:
            st_id = item.get("student_id")
            st_code = item.get("student_code") or item.get("id")
            st_status = item.get("status") or "present"
            st_period = item.get("period") or "ពេញមួយថ្ងៃ (07:00 - 16:30)"
            st_reason = item.get("reason") or ""
            st_guardian = item.get("guardian_note") or ""
            st_recorded_by = item.get("recorded_by") or "គ្រូបន្ទុកថ្នាក់"

            if not st_id and st_code:
                cursor.execute("SELECT student_id FROM students WHERE student_code = %s", (st_code,))
                r = cursor.fetchone()
                if r:
                    st_id = r["student_id"]

            if not st_id:
                continue

            cursor.execute("""
                SELECT attendance_id FROM attendance 
                WHERE student_id = %s AND attendance_date = %s
            """, (st_id, att_date))
            exist = cursor.fetchone()

            if exist:
                if st_status == "present":
                    cursor.execute("DELETE FROM attendance WHERE attendance_id = %s", (exist["attendance_id"],))
                else:
                    cursor.execute("""
                        UPDATE attendance 
                        SET status = %s, period = %s, reason = %s, guardian_note = %s, recorded_by = %s, class_id = %s, teacher_id = %s
                        WHERE attendance_id = %s
                    """, (st_status, st_period, st_reason, st_guardian, st_recorded_by, class_id, teacher_id, exist["attendance_id"]))
            else:
                if st_status != "present":
                    cursor.execute("""
                        INSERT INTO attendance (student_id, class_id, teacher_id, attendance_date, status, period, reason, guardian_note, recorded_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (st_id, class_id, teacher_id, att_date, st_status, st_period, st_reason, st_guardian, st_recorded_by))

            saved_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានកត់ត្រាវត្តមានសិស្សចំនួន {saved_count} នាក់ក្នុងថ្នាក់ជោគជ័យ!",
            "saved_count": saved_count,
            "teacher_id": teacher_id,
            "date": att_date
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 4. DELETE AN ATTENDANCE / ABSENCE RECORD
# ----------------------------------------------------
@attendance_bp.route("/api/attendance/<int:attendance_id>", methods=["DELETE"])
def delete_attendance(attendance_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_attendance_table(cursor)

        # 0. Enforce Active Academic Year Check
        cursor.execute("SELECT academic_year_id, academic_year FROM academic_years WHERE status = 'Active' LIMIT 1")
        active_yr = cursor.fetchone()
        if not active_yr:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "code": "ACADEMIC_YEAR_LOCKED",
                "message": "មិនអាចលុប ឬកែប្រែទិន្នន័យបានឡើយ ដោយសារបច្ចុប្បន្នមិនទាន់មានឆ្នាំសិក្សាសកម្មដែលបានបើកដំណើរការ (No Active Academic Year)!"
            }), 403

        cursor.execute("DELETE FROM attendance WHERE attendance_id = %s", (attendance_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានលុបកំណត់ត្រាអវត្តមានដោយជោគជ័យ!"
        }), 200
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500
