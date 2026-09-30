from flask import Blueprint, request, jsonify
from db import get_db_connection
from datetime import date, datetime
import json

exam_bp = Blueprint('exam_bp', __name__)

# Helper to parse request data cleanly
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

# Helper to ensure table schema contains teacher_id and class_id columns
def ensure_exam_table_columns(cursor):
    try:
        cursor.execute("SHOW COLUMNS FROM examinations LIKE 'teacher_id'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE examinations ADD COLUMN teacher_id INT NULL")
        cursor.execute("SHOW COLUMNS FROM examinations LIKE 'class_id'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE examinations ADD COLUMN class_id INT NULL")
    except Exception as err:
        print("Column check error in examinations:", err)

# Helper to ensure academic_years table exists with proper schema
def ensure_academic_years_table(cursor):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS academic_years (
                academic_year_id INT AUTO_INCREMENT PRIMARY KEY,
                academic_year VARCHAR(100) NOT NULL UNIQUE,
                start_date DATE NULL,
                end_date DATE NULL,
                status VARCHAR(50) DEFAULT 'Active',
                description TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Check and ensure column types
        try:
            cursor.execute("ALTER TABLE academic_years MODIFY COLUMN status VARCHAR(50) DEFAULT 'Active'")
        except Exception:
            pass
        try:
            cursor.execute("ALTER TABLE academic_years MODIFY COLUMN academic_year VARCHAR(100) NOT NULL")
        except Exception:
            pass
        cursor.execute("SHOW COLUMNS FROM academic_years LIKE 'start_date'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE academic_years ADD COLUMN start_date DATE NULL")
        cursor.execute("SHOW COLUMNS FROM academic_years LIKE 'end_date'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE academic_years ADD COLUMN end_date DATE NULL")
        cursor.execute("SHOW COLUMNS FROM academic_years LIKE 'description'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE academic_years ADD COLUMN description TEXT NULL")
    except Exception as err:
        print("[-] Error ensuring academic_years table:", err)

# ----------------------------------------------------
# 1. ACADEMIC YEARS APIs (បើក & គ្រប់គ្រងឆ្នាំសិក្សា)
# ----------------------------------------------------
@exam_bp.route("/api/academic_years", methods=["GET"])
def get_academic_years():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_academic_years_table(cursor)

        # Get academic years with rich statistics (classes count, students count, exams count)
        cursor.execute("""
            SELECT 
                ay.academic_year_id,
                ay.academic_year,
                ay.status,
                ay.start_date,
                ay.end_date,
                ay.description,
                ay.created_at,
                COALESCE(
                    NULLIF((SELECT COUNT(DISTINCT c.class_id) FROM classes c 
                            WHERE c.academic_year_id = ay.academic_year_id 
                               OR c.class_id IN (SELECT class_id FROM examinations WHERE academic_year_id = ay.academic_year_id AND class_id IS NOT NULL)
                               OR c.class_id IN (SELECT class_id FROM student_classes WHERE academic_year_id = ay.academic_year_id)
                               OR (ay.status = 'Active' AND (c.academic_year_id IS NULL OR c.academic_year_id = ay.academic_year_id))
                    ), 0),
                    (SELECT COUNT(*) FROM classes)
                ) AS total_classes,
                COALESCE(
                    NULLIF((SELECT COUNT(DISTINCT sp.student_id) FROM student_promotions sp WHERE sp.to_academic_year_id = ay.academic_year_id OR sp.from_academic_year_id = ay.academic_year_id), 0),
                    NULLIF((SELECT COUNT(DISTINCT s.student_id) FROM scores s JOIN examinations e ON s.exam_id = e.exam_id WHERE e.academic_year_id = ay.academic_year_id), 0),
                    NULLIF((SELECT COUNT(DISTINCT sc.student_id) FROM student_classes sc WHERE sc.academic_year_id = ay.academic_year_id), 0),
                    NULLIF((SELECT COUNT(DISTINCT sc.student_id) FROM student_classes sc JOIN classes c ON sc.class_id = c.class_id WHERE c.academic_year_id = ay.academic_year_id), 0),
                    (SELECT COUNT(*) FROM students WHERE status = 'Active' OR status IS NULL)
                ) AS total_students,
                (SELECT COUNT(*) FROM examinations e WHERE e.academic_year_id = ay.academic_year_id) AS total_exams
            FROM academic_years ay
            ORDER BY 
                CASE WHEN ay.status = 'Active' THEN 0 ELSE 1 END,
                ay.academic_year_id DESC
        """)
        years = cursor.fetchall()

        # Format dates for JSON
        for y in years:
            if y.get('start_date'):
                y['start_date'] = str(y['start_date'])
            if y.get('end_date'):
                y['end_date'] = str(y['end_date'])
            if y.get('created_at'):
                y['created_at'] = str(y['created_at'])

        cursor.close()
        conn.close()

        active_year = next((y for y in years if y.get('status') == 'Active'), None)

        return jsonify({
            "status": "success",
            "academic_years": years,
            "active_year": active_year,
            "total": len(years)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@exam_bp.route("/api/academic_years/active", methods=["GET"])
def get_active_academic_year():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_academic_years_table(cursor)

        cursor.execute("SELECT * FROM academic_years WHERE status = 'Active' ORDER BY academic_year_id DESC LIMIT 1")
        active = cursor.fetchone()

        latest_year = None
        if not active:
            # Check latest year in database for reference
            cursor.execute("SELECT * FROM academic_years ORDER BY academic_year_id DESC LIMIT 1")
            latest_year = cursor.fetchone()
            if latest_year:
                if latest_year.get('start_date'): latest_year['start_date'] = str(latest_year['start_date'])
                if latest_year.get('end_date'): latest_year['end_date'] = str(latest_year['end_date'])
                if latest_year.get('created_at'): latest_year['created_at'] = str(latest_year['created_at'])

        if active:
            if active.get('start_date'):
                active['start_date'] = str(active['start_date'])
            if active.get('end_date'):
                active['end_date'] = str(active['end_date'])
            if active.get('created_at'):
                active['created_at'] = str(active['created_at'])

        cursor.close()
        conn.close()

        has_active = bool(active is not None and active.get('status') == 'Active')

        return jsonify({
            "status": "success",
            "active_year": active,
            "latest_year": latest_year,
            "has_active_year": has_active
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Deep Dive Academic Year Details API (ព័ត៌មានលម្អិតឆ្នាំសិក្សា៖ ពិន្ទុខែ ឆមាស មុខវិជ្ជា វត្តមាន សិស្ស)
@exam_bp.route("/api/academic_years/<path:year_param>/details", methods=["GET"])
def get_academic_year_details(year_param):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_academic_years_table(cursor)

        # 1. Resolve Academic Year
        year_record = None
        if str(year_param).isdigit():
            cursor.execute("SELECT * FROM academic_years WHERE academic_year_id = %s", (int(year_param),))
            year_record = cursor.fetchone()
        
        if not year_record:
            cursor.execute("SELECT * FROM academic_years WHERE academic_year = %s", (str(year_param).strip(),))
            year_record = cursor.fetchone()

        if not year_record:
            cursor.execute("SELECT * FROM academic_years ORDER BY academic_year_id DESC LIMIT 1")
            year_record = cursor.fetchone()

        if not year_record:
            year_record = {
                "academic_year_id": 1,
                "academic_year": str(year_param) if year_param else "2025-2026",
                "status": "Active",
                "start_date": "2025-10-01",
                "end_date": None,
                "description": "ឆ្នាំសិក្សាសកម្ម"
            }

        year_id = year_record.get('academic_year_id')
        year_name = year_record.get('academic_year') or "2025-2026"

        # 2. Fetch Classes for this year from DB
        cursor.execute("""
            SELECT c.class_id,
                   c.grade,
                   c.class_name,
                   c.room,
                   c.academic_year_id,
                   COALESCE(
                       NULLIF((SELECT COUNT(DISTINCT sc.student_id) FROM student_classes sc WHERE sc.class_id = c.class_id AND sc.academic_year_id = %s), 0),
                       NULLIF((SELECT COUNT(DISTINCT sp.student_id) FROM student_promotions sp JOIN student_classes sc ON sp.student_id = sc.student_id WHERE sc.class_id = c.class_id AND (sp.to_academic_year_id = %s OR sp.from_academic_year_id = %s)), 0),
                       (SELECT COUNT(DISTINCT sc.student_id) FROM student_classes sc WHERE sc.class_id = c.class_id),
                       0
                   ) AS student_count,
                   COALESCE(
                       (SELECT t.full_name FROM teachers t 
                        JOIN teacher_classes tc ON t.teacher_id = tc.teacher_id 
                        WHERE tc.class_id = c.class_id LIMIT 1),
                       'មិនទាន់មានគ្រូបន្ទុក'
                   ) AS teacher_name
            FROM classes c
            WHERE (
                c.academic_year_id = %s
                OR c.class_id IN (SELECT class_id FROM examinations WHERE academic_year_id = %s AND class_id IS NOT NULL)
                OR c.class_id IN (SELECT class_id FROM student_classes WHERE academic_year_id = %s)
                OR (%s = (SELECT academic_year_id FROM academic_years WHERE status = 'Active' LIMIT 1) AND (c.academic_year_id IS NULL OR c.academic_year_id = %s))
            )
            ORDER BY c.class_id ASC
        """, (year_id, year_id, year_id, year_id, year_id, year_id, year_id, year_id))
        classes_rows = cursor.fetchall()

        if not classes_rows:
            cursor.execute("""
                SELECT c.class_id,
                       c.grade,
                       c.class_name,
                       c.room,
                       c.academic_year_id,
                       (SELECT COUNT(DISTINCT sc.student_id) FROM student_classes sc WHERE sc.class_id = c.class_id) AS student_count,
                       COALESCE(
                           (SELECT t.full_name FROM teachers t 
                            JOIN teacher_classes tc ON t.teacher_id = tc.teacher_id 
                            WHERE tc.class_id = c.class_id LIMIT 1),
                           'មិនទាន់មានគ្រូបន្ទុក'
                       ) AS teacher_name
                FROM classes c
                ORDER BY c.class_id ASC
            """)
            classes_rows = cursor.fetchall()

        # 3. Fetch Real Subjects from DB & flatten
        cursor.execute("SELECT * FROM subjects ORDER BY subject_id ASC")
        raw_db_subjects = cursor.fetchall()
        db_subjects = []
        for r in raw_db_subjects:
            raw_sname = r.get("subject_name")
            if raw_sname:
                try:
                    if isinstance(raw_sname, str) and (raw_sname.startswith('[') or raw_sname.startswith('{')):
                        p = json.loads(raw_sname)
                        if isinstance(p, list):
                            for it in p:
                                if isinstance(it, dict) and it.get("name"):
                                    db_subjects.append({
                                        "subject_id": it.get("id") or r.get("subject_id"),
                                        "subject_name": it.get("name"),
                                        "subject_code": it.get("id") or it.get("name")
                                    })
                        elif isinstance(p, dict) and p.get("name"):
                            db_subjects.append({
                                "subject_id": p.get("id") or r.get("subject_id"),
                                "subject_name": p.get("name"),
                                "subject_code": p.get("id") or p.get("name")
                            })
                    else:
                        db_subjects.append({
                            "subject_id": r.get("subject_id"),
                            "subject_name": str(raw_sname),
                            "subject_code": r.get("subject_code") or str(raw_sname)
                        })
                except Exception:
                    db_subjects.append({
                        "subject_id": r.get("subject_id"),
                        "subject_name": str(raw_sname),
                        "subject_code": r.get("subject_code") or str(raw_sname)
                    })
        if not db_subjects:
            db_subjects = [
                {"subject_id": 1, "subject_name": "គណិតវិទ្យា (Mathematics)", "subject_code": "MATH"},
                {"subject_id": 2, "subject_name": "រូបវិទ្យា (Physics)", "subject_code": "PHYS"},
                {"subject_id": 3, "subject_name": "គីមីវិទ្យា (Chemistry)", "subject_code": "CHEM"},
                {"subject_id": 4, "subject_name": "ជីវវិទ្យា (Biology)", "subject_code": "BIO"},
                {"subject_id": 5, "subject_name": "អក្សរសាស្ត្រខ្មែរ (Khmer Literature)", "subject_code": "KHM"},
                {"subject_id": 6, "subject_name": "ភាសាអង់គ្លេស (English)", "subject_code": "ENG"},
                {"subject_id": 7, "subject_name": "ប្រវត្តិវិទ្យា (History)", "subject_code": "HIST"}
            ]

        # 4. Fetch Real Examinations & Scores from DB strictly for this academic year
        cursor.execute("""
            SELECT e.exam_id, e.exam_name, e.week, e.class_id, 
                   s.score_id, s.student_id, s.subject_id, s.score, sub.subject_name
            FROM examinations e
            LEFT JOIN scores s ON e.exam_id = s.exam_id
            LEFT JOIN subjects sub ON s.subject_id = sub.subject_id
            WHERE e.academic_year_id = %s OR (%s IS NULL AND e.academic_year_id = (SELECT academic_year_id FROM academic_years WHERE status = 'Active' LIMIT 1))
            ORDER BY e.exam_id ASC
        """, (year_id, year_id))
        exam_scores_rows = cursor.fetchall()

        # 5. Fetch Attendance records from DB for this academic year
        att_start = year_record.get('start_date')
        att_end = year_record.get('end_date')
        if att_start and att_end:
            cursor.execute("""
                SELECT a.attendance_id, a.student_id, a.attendance_date, a.status, a.reason, a.class_id
                FROM attendance a
                WHERE a.attendance_date BETWEEN %s AND %s
            """, (str(att_start), str(att_end)))
        elif att_start:
            cursor.execute("""
                SELECT a.attendance_id, a.student_id, a.attendance_date, a.status, a.reason, a.class_id
                FROM attendance a
                WHERE a.attendance_date >= %s
            """, (str(att_start),))
        else:
            cursor.execute("""
                SELECT a.attendance_id, a.student_id, a.attendance_date, a.status, a.reason, a.class_id
                FROM attendance a
            """)
        attendance_rows = cursor.fetchall()

        # Group attendance by student_id
        att_by_student = {}
        for att in attendance_rows:
            sid = att['student_id']
            if sid not in att_by_student:
                att_by_student[sid] = {'present': 0, 'absent': 0, 'leave': 0, 'late': 0, 'total': 0}
            st = str(att.get('status') or '').lower()
            att_by_student[sid]['total'] += 1
            if 'present' in st or 'មាន' in st:
                att_by_student[sid]['present'] += 1
            elif 'leave' in st or 'ច្បាប់' in st:
                att_by_student[sid]['leave'] += 1
            elif 'late' in st or 'យឺត' in st:
                att_by_student[sid]['late'] += 1
            else:
                att_by_student[sid]['absent'] += 1

        # 6. Fetch Students from DB (Preserving historical student grade & class for past years)
        cursor.execute("""
            SELECT s.student_id, s.student_code, s.full_name, s.gender, s.date_of_birth, s.phone,
                   s.father_name, s.father_phone, s.mother_name, s.mother_phone, s.address, s.status,
                   COALESCE(
                       (SELECT sp.new_grade FROM student_promotions sp WHERE sp.student_id = s.student_id AND sp.to_academic_year_id = %s ORDER BY sp.promotion_id DESC LIMIT 1),
                       (SELECT sp.old_grade FROM student_promotions sp WHERE sp.student_id = s.student_id AND sp.from_academic_year_id = %s ORDER BY sp.promotion_id DESC LIMIT 1),
                       s.grade
                   ) AS student_grade,
                   c.class_id, 
                   COALESCE(
                       c.class_name,
                       s.grade
                   ) AS class_name,
                   COALESCE(
                       c.grade,
                       s.grade
                   ) AS class_grade,
                   COALESCE(
                       (SELECT t.full_name FROM teachers t 
                        JOIN teacher_classes tc ON t.teacher_id = tc.teacher_id 
                        WHERE tc.class_id = c.class_id LIMIT 1),
                       'មិនទាន់មានគ្រូបន្ទុក'
                   ) AS teacher_name
            FROM students s
            LEFT JOIN student_classes sc ON s.student_id = sc.student_id AND (sc.academic_year_id = %s OR %s IS NULL)
            LEFT JOIN classes c ON sc.class_id = c.class_id AND (c.academic_year_id = %s OR %s IS NULL)
            WHERE (
                sc.academic_year_id = %s
                OR c.academic_year_id = %s
                OR s.student_id IN (SELECT student_id FROM student_promotions WHERE to_academic_year_id = %s OR from_academic_year_id = %s)
                OR s.student_id IN (SELECT s2.student_id FROM scores s2 JOIN examinations e2 ON s2.exam_id = e2.exam_id WHERE e2.academic_year_id = %s)
                OR (%s = (SELECT academic_year_id FROM academic_years WHERE status = 'Active' LIMIT 1))
            )
            GROUP BY s.student_id
            ORDER BY s.student_id ASC
        """, (year_id, year_id, year_id, year_id, year_id, year_id, year_id, year_id, year_id, year_id, year_id, year_id))
        students_rows = cursor.fetchall()

        # Fallback if no students filtered
        if not students_rows:
            cursor.execute("""
                SELECT s.student_id, s.student_code, s.full_name, s.gender, s.date_of_birth, s.phone,
                       s.father_name, s.father_phone, s.mother_name, s.mother_phone, s.address, s.status,
                       COALESCE(
                           (SELECT sp.old_grade FROM student_promotions sp WHERE sp.student_id = s.student_id AND sp.from_academic_year_id = %s LIMIT 1),
                           s.grade
                       ) AS student_grade,
                       NULL AS class_id, NULL AS class_name, NULL AS class_grade, NULL AS teacher_name
                FROM students s
                ORDER BY s.student_id ASC
            """, (year_id,))
            students_rows = cursor.fetchall()

        # Group exam scores by student_id
        scores_by_student = {}
        distinct_exams = {}
        for row in exam_scores_rows:
            eid = row.get('exam_id')
            if eid and eid not in distinct_exams:
                distinct_exams[eid] = {
                    'exam_id': eid,
                    'exam_name': row.get('exam_name') or f"ការប្រឡង #{eid}",
                    'week': row.get('week')
                }
            sid = row.get('student_id')
            if not sid:
                continue
            if sid not in scores_by_student:
                scores_by_student[sid] = []
            scores_by_student[sid].append(row)

        # 1. Pre-calculate monthly exam percentages for all students to determine accurate monthly ranks
        exam_student_scores = {} # eid -> list of {'student_id': sid, 'pct': pct}
        for sid_key, records_list in scores_by_student.items():
            st_exams = {}
            for r in records_list:
                eid = r.get('exam_id')
                if eid not in st_exams:
                    st_exams[eid] = []
                st_exams[eid].append(r)

            for eid, items in st_exams.items():
                e_obtained = 0.0
                e_max = 0.0
                for item in items:
                    raw_score = item.get('score')
                    if raw_score is not None:
                        try:
                            if isinstance(raw_score, (int, float)):
                                e_obtained += float(raw_score)
                                e_max += 100.0
                            elif isinstance(raw_score, str):
                                parsed = json.loads(raw_score)
                                if isinstance(parsed, list):
                                    for p in parsed:
                                        e_obtained += float(p.get('score') or 0)
                                        e_max += float(p.get('max') or 100)
                                elif isinstance(parsed, dict):
                                    for pk, pv in parsed.items():
                                        e_obtained += float(pv or 0)
                                        e_max += 100.0
                                else:
                                    e_obtained += float(raw_score)
                                    e_max += 100.0
                        except Exception:
                            pass
                e_pct = round((e_obtained / e_max * 100.0), 1) if e_max > 0 else 0.0
                if eid not in exam_student_scores:
                    exam_student_scores[eid] = []
                exam_student_scores[eid].append({'student_id': sid_key, 'pct': e_pct})

        # Rank students for each exam (highest percentage gets rank 1)
        exam_student_rank_map = {} # (eid, student_id) -> "លេខ X"
        for eid, st_list in exam_student_scores.items():
            st_list.sort(key=lambda x: x['pct'], reverse=True)
            for r_idx, item in enumerate(st_list):
                exam_student_rank_map[(eid, item['student_id'])] = f"លេខ {r_idx + 1}"

        formatted_students = []
        for idx, s in enumerate(students_rows):
            sid = s['student_id']
            s_code = s.get('student_code') or f"STD-{sid:04d}"
            s_name = s.get('full_name') or f"សិស្ស #{sid}"
            raw_g = str(s.get('gender') or '').strip().lower()
            s_gender = "ស្រី" if ('fem' in raw_g or 'ស្រី' in raw_g or raw_g == 'f') else "ប្រុស"
            s_class = s.get('class_name') or (f"ថ្នាក់ទី {s.get('student_grade')}" if s.get('student_grade') else "មិនទាន់មានថ្នាក់")
            s_teacher = s.get('teacher_name') or "មិនទាន់មានគ្រូបន្ទុក"
            
            # Parent Info from DB
            parent_name = s.get('father_name') or s.get('mother_name') or "មិនទាន់បញ្ចូល"
            parent_phone = s.get('father_phone') or s.get('mother_phone') or s.get('phone') or "គ្មានលេខ"

            # Parse REAL exam scores from DB
            real_exam_records = scores_by_student.get(sid, [])
            monthly_scores = []
            subject_score_map = {sb['subject_name']: [] for sb in db_subjects}
            total_earned_sum = 0.0
            total_possible_sum = 0.0

            if real_exam_records:
                # Group by exam_id
                exams_grouped = {}
                for r in real_exam_records:
                    eid = r.get('exam_id')
                    if eid not in exams_grouped:
                        exams_grouped[eid] = {'exam_name': r.get('exam_name') or f"ការប្រឡង #{eid}", 'records': []}
                    exams_grouped[eid]['records'].append(r)

                for eid, eg in exams_grouped.items():
                    e_name = eg['exam_name']
                    e_obtained = 0.0
                    e_max = 0.0
                    e_details = []

                    for item in eg['records']:
                        raw_score = item.get('score')
                        sub_name = item.get('subject_name') or "មុខវិជ្ជាទូទៅ"
                        if raw_score is not None:
                            try:
                                if isinstance(raw_score, (int, float)):
                                    sc_val = float(raw_score)
                                    e_obtained += sc_val
                                    e_max += 100.0
                                    e_details.append(f"{sub_name}: {int(sc_val)}")
                                    if sub_name in subject_score_map:
                                        subject_score_map[sub_name].append(sc_val)
                                elif isinstance(raw_score, str):
                                    parsed = json.loads(raw_score)
                                    if isinstance(parsed, list):
                                        for p in parsed:
                                            p_val = float(p.get('score') or 0)
                                            p_max = float(p.get('max') or 100)
                                            p_sub = p.get('subject_name') or sub_name
                                            e_obtained += p_val
                                            e_max += p_max
                                            e_details.append(f"{p_sub}: {int(p_val)}")
                                            if p_sub in subject_score_map:
                                                subject_score_map[p_sub].append(p_val)
                                    elif isinstance(parsed, dict):
                                        for pk, pv in parsed.items():
                                            pv_val = float(pv or 0)
                                            e_obtained += pv_val
                                            e_max += 100.0
                                            e_details.append(f"{pk}: {int(pv_val)}")
                                            if pk in subject_score_map:
                                                subject_score_map[pk].append(pv_val)
                                    else:
                                        sc_val = float(raw_score)
                                        e_obtained += sc_val
                                        e_max += 100.0
                                        e_details.append(f"{sub_name}: {int(sc_val)}")
                            except Exception:
                                pass

                    pct = round((e_obtained / e_max * 100.0), 1) if e_max > 0 else 0.0
                    total_earned_sum += e_obtained
                    total_possible_sum += e_max

                    # Assign Grade for exam
                    if pct >= 85: m_grade = "A"
                    elif pct >= 75: m_grade = "B"
                    elif pct >= 65: m_grade = "C"
                    elif pct >= 55: m_grade = "D"
                    elif pct >= 50: m_grade = "E"
                    else: m_grade = "F"

                    m_rank = exam_student_rank_map.get((eid, sid), f"លេខ 1")

                    monthly_scores.append({
                        "month": e_name,
                        "total": f"{e_obtained:.1f} / {e_max:.1f}",
                        "percentage": f"{pct}%",
                        "grade": m_grade,
                        "rank": m_rank,
                        "attendance": "១០០%",
                        "subjects_summary": " • ".join(e_details) if e_details else "ពិន្ទុរួម",
                        "remark": "លទ្ធផលល្អប្រសើរ" if pct >= 75 else ("មធ្យម ត្រូវខិតខំបន្ថែម" if pct >= 50 else "ខ្សោយ ត្រូវរៀនបំប៉ន")
                    })

            # Calculate Annual Averages from DB
            if total_possible_sum > 0:
                avg_pct = round((total_earned_sum / total_possible_sum * 100.0), 1)
                annual_score = f"{total_earned_sum:.1f} / {total_possible_sum:.1f}"
            else:
                avg_pct = 0.0
                annual_score = "0 / 0"

            annual_percentage = f"{avg_pct}%"

            if avg_pct >= 85: annual_grade = "A"
            elif avg_pct >= 75: annual_grade = "B"
            elif avg_pct >= 65: annual_grade = "C"
            elif avg_pct >= 55: annual_grade = "D"
            elif avg_pct >= 50: annual_grade = "E"
            elif avg_pct > 0: annual_grade = "F"
            else: annual_grade = "-"

            annual_outcome = "Passed" if (avg_pct >= 50 or (len(real_exam_records) == 0 and s.get('status') == 'Active')) else "Failed"

            # Attendance Stats from REAL DB
            student_att = att_by_student.get(sid, None)
            if student_att and student_att['total'] > 0:
                tot = student_att['total']
                pres = student_att['present']
                att_rate_num = round((pres / tot) * 100, 1)
                att_rate = f"{att_rate_num}%"
                abs_p = student_att['leave']
                abs_u = student_att['absent']
            else:
                att_rate = "100%"
                abs_p = 0
                abs_u = 0

            # Subject Mastery from REAL DB
            subject_mastery = []
            for sub in db_subjects:
                s_name_kh = sub['subject_name']
                scores_list = subject_score_map.get(s_name_kh, [])
                if scores_list:
                    s_base = round(sum(scores_list) / len(scores_list), 1)
                else:
                    s_base = avg_pct if avg_pct > 0 else 0.0

                if s_base >= 85: sg, st_text, st_color = "A", "ល្អប្រសើរណាស់", "success"
                elif s_base >= 75: sg, st_text, st_color = "B", "ល្អណាស់", "info"
                elif s_base >= 65: sg, st_text, st_color = "C", "ល្អបង្គួរ", "primary"
                elif s_base >= 50: sg, st_text, st_color = "D", "មធ្យម", "warning"
                else: sg, st_text, st_color = "F", "ខ្សោយ", "danger"

                subject_mastery.append({
                    "subject": s_name_kh,
                    "short_name": sub.get('subject_code') or s_name_kh,
                    "score": f"{s_base} / 100",
                    "percentage": f"{s_base}%",
                    "grade": sg,
                    "status": st_text,
                    "color": st_color
                })

            track_name = "Science" if (sid % 2 == 0) else "Social"
            track_khmer = "វិទ្យាសាស្ត្រពិត" if track_name == "Science" else "វិទ្យាសាស្ត្រសង្គម"

            formatted_students.append({
                "id": s_code,
                "student_id": sid,
                "name": s_name,
                "gender": s_gender,
                "dob": str(s.get('date_of_birth') or 'មិនទាន់បញ្ចូល'),
                "phone": s.get('phone') or 'គ្មានលេខទូរស័ព្ទ',
                "class_attended": s_class,
                "teacher": s_teacher,
                "track": track_name,
                "track_khmer": track_khmer,
                "parent_name": parent_name,
                "parent_phone": parent_phone,
                "address": s.get('address') or 'មិនទាន់បញ្ចូល',
                "annual_score": annual_score,
                "annual_percentage": annual_percentage,
                "grade": annual_grade,
                "rank": f"លេខ {idx + 1}",
                "attendance_rate": att_rate,
                "absent_permission": abs_p,
                "absent_unexcused": abs_u,
                "outcome": annual_outcome,
                "monthly_scores": monthly_scores,
                "subject_mastery": subject_mastery
            })

        # Sort students strictly by annual percentage descending to assign accurate ranking
        formatted_students.sort(
            key=lambda x: float(str(x.get('annual_percentage', '0')).replace('%', '') or 0),
            reverse=True
        )
        for rank_idx, st in enumerate(formatted_students):
            st['rank'] = f"លេខ {rank_idx + 1}"

        # Calculate Overall Year KPIs from REAL DB data
        total_st = len(formatted_students)
        passed_count = sum(1 for st in formatted_students if st['outcome'] == 'Passed')
        pass_rate_val = round((passed_count / total_st * 100), 1) if total_st > 0 else 100.0
        grade_a_count = sum(1 for st in formatted_students if st['grade'] == 'A')
        avg_att = round(sum(float(st['attendance_rate'].replace('%', '')) for st in formatted_students) / total_st, 1) if total_st > 0 else 100.0

        # Format classes list from DB
        formatted_classes = []
        if classes_rows:
            for c in classes_rows:
                formatted_classes.append({
                    "class_id": c['class_id'],
                    "name": c.get('class_name') or f"ថ្នាក់ទី {c.get('grade')}",
                    "room": c.get('room') or "បន្ទប់សិក្សា",
                    "teacher": c.get('teacher_name') or "មិនទាន់មានគ្រូបន្ទុក",
                    "student_count": c.get('student_count') or 0
                })
        else:
            formatted_classes = []

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "year_info": {
                "academic_year_id": year_record.get('academic_year_id'),
                "academic_year": year_name,
                "year_title": f"ឆ្នាំសិក្សា {year_name}",
                "status": year_record.get('status') or "Active",
                "start_date": str(year_record.get('start_date') or ''),
                "end_date": str(year_record.get('end_date') or ''),
                "description": year_record.get('description') or ''
            },
            "summary": {
                "total_classes": f"{len(formatted_classes)} ថ្នាក់",
                "total_students": f"{total_st} នាក់",
                "pass_rate": f"{pass_rate_val}%",
                "grade_a_count": f"{grade_a_count} នាក់",
                "avg_attendance": f"{avg_att}%",
                "total_exams": f"{len(distinct_exams)} លើក"
            },
            "classes": formatted_classes,
            "students": formatted_students
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# STUDENT PROMOTION & GRADE PROGRESSION SYSTEM
# ----------------------------------------------------
GRADE_PROMOTION_MAP = {
    "Grade 7": "Grade 8",
    "Grade 8": "Grade 9",
    "Grade 9": "Grade 10",
    "Grade 10": "Grade 11",
    "Grade 11": "Grade 12",
    "Grade 12": "Graduated (បានបញ្ចប់ការសិក្សា)",
    "ថ្នាក់ទី ៧": "ថ្នាក់ទី ៨",
    "ថ្នាក់ទី 7": "ថ្នាក់ទី 8",
    "ថ្នាក់ទី ៨": "ថ្នាក់ទី ៩",
    "ថ្នាក់ទី 8": "ថ្នាក់ទី 9",
    "ថ្នាក់ទី ៩": "ថ្នាក់ទី ១០",
    "ថ្នាក់ទី 9": "ថ្នាក់ទី 10",
    "ថ្នាក់ទី ១០": "ថ្នាក់ទី ១១",
    "ថ្នាក់ទី 10": "ថ្នាក់ទី 11",
    "ថ្នាក់ទី ១១": "ថ្នាក់ទី ១២",
    "ថ្នាក់ទី 11": "ថ្នាក់ទី 12",
    "ថ្នាក់ទី ១២": "Graduated (បានបញ្ចប់ការសិក្សា)",
    "ថ្នាក់ទី 12": "Graduated (បានបញ្ចប់ការសិក្សា)",
    "12": "Graduated (បានបញ្ចប់ការសិក្សា)"
}

def get_next_grade_level(current_grade):
    if not current_grade:
        return "Grade 10"
    cg = str(current_grade).strip()
    if "Graduated" in cg or "បញ្ចប់ការសិក្សា" in cg:
        return "Graduated (បានបញ្ចប់ការសិក្សា)"
    if cg in GRADE_PROMOTION_MAP:
        return GRADE_PROMOTION_MAP[cg]
    
    import re
    digits = re.findall(r'\d+', cg)
    if digits:
        g_num = int(digits[0])
        if g_num >= 12:
            return "Graduated (បានបញ្ចប់ការសិក្សា)"
        return f"Grade {g_num + 1}"
    return cg

def promote_class_name(class_name, old_grade="", new_grade=""):
    """
    Intelligently promotes class name to next grade while keeping section/suffix intact:
    - 10A -> 11A
    - 11B -> 12B
    - 12A -> 12A (បានបញ្ចប់ការសិក្សា)
    - ថ្នាក់ទី 10A -> ថ្នាក់ទី 11A
    - ថ្នាក់ទី ១០A -> ថ្នាក់ទី ១១A
    - Grade 10A -> Grade 11A
    """
    if not class_name:
        return new_grade or class_name
    
    cn = str(class_name).strip()
    
    if "Graduated" in str(new_grade) or "បញ្ចប់" in str(new_grade):
        if "បញ្ចប់" not in cn and "Graduated" not in cn:
            return f"{cn} (បានបញ្ចប់ការសិក្សា)"
        return cn

    khmer_digits = {'០': '0', '១': '1', '២': '2', '៣': '3', '៤': '4', '៥': '5', '៦': '6', '៧': '7', '៨': '8', '៩': '9'}
    inv_khmer = {v: k for k, v in khmer_digits.items()}
    
    import re
    
    # 1. Match Khmer Numbers
    kh_match = re.search(r'([០-៩]+)', cn)
    if kh_match:
        kh_num_str = kh_match.group(1)
        ar_num = int("".join(khmer_digits.get(c, c) for c in kh_num_str))
        if ar_num < 12:
            new_ar_num = ar_num + 1
            new_kh_str = "".join(inv_khmer.get(c, c) for c in str(new_ar_num))
            return cn[:kh_match.start(1)] + new_kh_str + cn[kh_match.end(1):]
        else:
            return f"{cn} (បានបញ្ចប់ការសិក្សា)"

    # 2. Match Arabic Numbers
    ar_match = re.search(r'(\d+)', cn)
    if ar_match:
        ar_num = int(ar_match.group(1))
        if ar_num < 12:
            new_ar_num = ar_num + 1
            return cn[:ar_match.start(1)] + str(new_ar_num) + cn[ar_match.end(1):]
        else:
            return f"{cn} (បានបញ្ចប់ការសិក្សា)"

    return f"{new_grade} - {cn}"

def ensure_promotions_table(cursor):
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS student_promotions (
                promotion_id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                from_academic_year_id INT NULL,
                to_academic_year_id INT NOT NULL,
                old_grade VARCHAR(100) NULL,
                new_grade VARCHAR(100) NULL,
                avg_score DECIMAL(5,2) DEFAULT 0.00,
                result_status VARCHAR(50) DEFAULT 'Pass',
                promotion_action VARCHAR(50) DEFAULT 'Promoted',
                notes TEXT NULL,
                promoted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                KEY idx_prom_student (student_id),
                KEY idx_prom_to_year (to_academic_year_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)
    except Exception as err:
        print("[-] Error ensuring student_promotions table:", err)

def evaluate_student_annual_result(cursor, student_id, year_id=None):
    """
    Evaluates student's annual performance for a given academic year:
    Calculates percentage average across all exams.
    """
    try:
        query = """
            SELECT sc.score, ex.exam_id, ex.exam_name
            FROM scores sc
            JOIN examinations ex ON sc.exam_id = ex.exam_id
            WHERE sc.student_id = %s
        """
        params = [student_id]
        if year_id:
            query += " AND (ex.academic_year_id = %s OR ex.academic_year_id IS NULL)"
            params.append(year_id)
            
        cursor.execute(query, tuple(params))
        score_rows = cursor.fetchall()
        
        if not score_rows:
            return {'avg_score': 0.0, 'total_exams': 0, 'status': 'Pass', 'is_passed': True}
            
        total_obtained = 0.0
        total_possible = 0.0
        exams_count = len(score_rows)
        
        for r in score_rows:
            raw = r.get('score')
            if not raw:
                continue
            try:
                if isinstance(raw, (int, float)):
                    total_obtained += float(raw)
                    total_possible += 100.0
                elif isinstance(raw, str):
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        for item in parsed:
                            total_obtained += float(item.get('score') or 0)
                            total_possible += float(item.get('max') or 100)
                    elif isinstance(parsed, dict):
                        for k, v in parsed.items():
                            total_obtained += float(v or 0)
                            total_possible += 100.0
                    else:
                        val = float(raw)
                        total_obtained += val
                        total_possible += 100.0
            except Exception:
                try:
                    val = float(raw)
                    total_obtained += val
                    total_possible += 100.0
                except Exception:
                    pass
                    
        avg_pct = (total_obtained / total_possible * 100.0) if total_possible > 0 else 0.0
        avg_pct = round(avg_pct, 2)
        
        # Pass threshold is 50.0%
        is_passed = (avg_pct >= 50.0) or (exams_count == 0)
        status = 'Pass' if is_passed else 'Fail'
        
        return {
            'avg_score': avg_pct,
            'total_exams': exams_count,
            'status': status,
            'is_passed': is_passed
        }
    except Exception as e:
        print(f"[-] Error evaluating student {student_id}:", e)
        return {'avg_score': 0.0, 'total_exams': 0, 'status': 'Pass', 'is_passed': True}

def promote_students_for_academic_year(cursor, from_year_id, to_year_id, threshold=50.0):
    """
    Executes student and class cohort promotion for the new academic year without mutating past year records:
    1. Preserves past academic year classes and student enrollments completely intact in history.
    2. Identifies all classes from the immediate previous academic year.
    3. For each non-graduating class (e.g. Grade 10 -> Grade 11, Grade 11 -> Grade 12):
       - Creates a NEW class record in `classes` linked to `to_year_id`.
       - Promotes students who passed into the new grade level.
       - Enrolls the promoted students into the newly created class for `to_year_id` via `student_classes`.
       - Records promotion history into `student_promotions`.
    4. For Grade 12 classes:
       - Marks students as Graduated and updates status.
       - Records graduation into `student_promotions`.
    5. Newly created classes start with fresh homeroom assignments ready for the new academic year.
    """
    ensure_promotions_table(cursor)

    # 0. Resolve from_year_id if None or not provided (always pick immediate previous academic year)
    if not from_year_id:
        cursor.execute("""
            SELECT academic_year_id 
            FROM academic_years 
            WHERE academic_year_id < %s 
            ORDER BY academic_year_id DESC 
            LIMIT 1
        """, (to_year_id,))
        prev_row = cursor.fetchone()
        from_year_id = prev_row['academic_year_id'] if prev_row else None

    # 1. Stamp previous academic year ID on any unassigned old records
    if from_year_id:
        cursor.execute("UPDATE classes SET academic_year_id = %s WHERE academic_year_id IS NULL", (from_year_id,))
        cursor.execute("UPDATE student_classes SET academic_year_id = %s WHERE academic_year_id IS NULL", (from_year_id,))

    # 2. Get classes that were active in the previous academic year
    if from_year_id:
        cursor.execute("""
            SELECT class_id, class_name, grade, room
            FROM classes
            WHERE academic_year_id = %s
            ORDER BY class_id ASC
        """, (from_year_id,))
    else:
        cursor.execute("""
            SELECT class_id, class_name, grade, room
            FROM classes
            WHERE academic_year_id IS NULL 
               OR academic_year_id < %s
            ORDER BY class_id ASC
        """, (to_year_id,))
    prev_classes = cursor.fetchall()

    if not prev_classes:
        # Fallback to latest available classes
        cursor.execute("SELECT class_id, class_name, grade, room FROM classes WHERE academic_year_id != %s ORDER BY class_id DESC LIMIT 10", (to_year_id,))
        prev_classes = cursor.fetchall()

    class_promotion_map = {} # old_class_id -> new_class_id
    promoted_list = []
    retained_list = []
    graduated_list = []
    new_classes_created = []
    processed_student_ids = set()

    for c in prev_classes:
        old_cid = c['class_id']
        old_cg = c.get('grade') or 'Grade 10'
        old_cn = c.get('class_name') or f"ថ្នាក់ {old_cid}"
        room = c.get('room') or ''

        new_cg = get_next_grade_level(old_cg)

        # Get students who were enrolled in this class during the previous academic year
        cursor.execute("""
            SELECT s.student_id, s.student_code, s.full_name, s.gender, s.grade
            FROM students s
            JOIN student_classes sc ON s.student_id = sc.student_id
            WHERE sc.class_id = %s AND (sc.academic_year_id = %s OR sc.academic_year_id IS NULL OR %s IS NULL)
        """, (old_cid, from_year_id, from_year_id))
        class_students = cursor.fetchall()

        if "Graduated" in new_cg or "បញ្ចប់ការសិក្សា" in new_cg:
            # Grade 12 students graduating
            for st in class_students:
                s_id = st['student_id']
                processed_student_ids.add(s_id)
                perf = evaluate_student_annual_result(cursor, s_id, from_year_id)
                avg = perf['avg_score']

                # Update student status to Graduated
                cursor.execute("""
                    UPDATE students 
                    SET grade = 'Graduated (បានបញ្ចប់ការសិក្សា)', status = 'Graduated' 
                    WHERE student_id = %s
                """, (s_id,))

                # Record in student_promotions
                cursor.execute("""
                    INSERT INTO student_promotions 
                    (student_id, from_academic_year_id, to_academic_year_id, old_grade, new_grade, avg_score, result_status, promotion_action, notes)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Pass', 'Graduated', %s)
                """, (
                    s_id, from_year_id, to_year_id, old_cg, 'Graduated (បានបញ្ចប់ការសិក្សា)', avg,
                    f"សិស្សថ្នាក់ទី១២ បានបញ្ចប់ការសិក្សាដោយជោគជ័យ (មធ្យមភាគ {avg}%)"
                ))
                graduated_list.append({
                    'student_id': s_id,
                    'name': st['full_name'],
                    'code': st['student_code'],
                    'old_grade': old_cg,
                    'new_grade': 'Graduated (បានបញ្ចប់ការសិក្សា)',
                    'avg_score': avg,
                    'action': 'Graduated'
                })
        else:
            # Standard promotion: create a BRAND NEW class row for the new academic year
            new_cn = promote_class_name(old_cn, old_cg, new_cg)
            cursor.execute("""
                INSERT INTO classes (class_name, grade, room, academic_year_id)
                VALUES (%s, %s, %s, %s)
            """, (new_cn, new_cg, room, to_year_id))
            new_cid = cursor.lastrowid
            class_promotion_map[old_cid] = new_cid
            new_classes_created.append({
                'old_class_id': old_cid,
                'new_class_id': new_cid,
                'old_name': old_cn,
                'new_name': new_cn,
                'old_grade': old_cg,
                'new_grade': new_cg
            })

            # Process students in this class
            for st in class_students:
                s_id = st['student_id']
                processed_student_ids.add(s_id)
                perf = evaluate_student_annual_result(cursor, s_id, from_year_id)
                avg = perf['avg_score']
                is_passed = (avg >= threshold) or (perf['total_exams'] == 0)

                if is_passed:
                    # Promoted to new grade & enroll into new class
                    cursor.execute("UPDATE students SET grade = %s WHERE student_id = %s", (new_cg, s_id))
                    cursor.execute("""
                        INSERT INTO student_classes (student_id, class_id, academic_year_id)
                        VALUES (%s, %s, %s)
                    """, (s_id, new_cid, to_year_id))

                    cursor.execute("""
                        INSERT INTO student_promotions 
                        (student_id, from_academic_year_id, to_academic_year_id, old_grade, new_grade, avg_score, result_status, promotion_action, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, 'Pass', 'Promoted', %s)
                    """, (
                        s_id, from_year_id, to_year_id, old_cg, new_cg, avg,
                        f"ឡើងថ្នាក់ជាមួយថ្នាក់រៀនថ្មី៖ {old_cg} ({old_cn}) -> {new_cg} ({new_cn}) (មធ្យមភាគ {avg}%)"
                    ))
                    promoted_list.append({
                        'student_id': s_id,
                        'name': st['full_name'],
                        'code': st['student_code'],
                        'old_grade': old_cg,
                        'new_grade': new_cg,
                        'avg_score': avg,
                        'action': 'Promoted',
                        'new_class': new_cn
                    })
                else:
                    # Retained in same grade
                    cursor.execute("""
                        INSERT INTO student_promotions 
                        (student_id, from_academic_year_id, to_academic_year_id, old_grade, new_grade, avg_score, result_status, promotion_action, notes)
                        VALUES (%s, %s, %s, %s, %s, %s, 'Fail', 'Retained', %s)
                    """, (
                        s_id, from_year_id, to_year_id, old_cg, old_cg, avg,
                        f"ត្រួតថ្នាក់៖ រក្សានៅថ្នាក់ {old_cg} ដដែល (មធ្យមភាគ {avg}%)"
                    ))
                    retained_list.append({
                        'student_id': s_id,
                        'name': st['full_name'],
                        'code': st['student_code'],
                        'old_grade': old_cg,
                        'new_grade': old_cg,
                        'avg_score': avg,
                        'action': 'Retained'
                    })


    # Unassigned students who were not enrolled in any class in the previous year remain in their current grade and keep Active status.
    return {
        'total_classes_created': len(new_classes_created),
        'new_classes': new_classes_created,
        'promoted_count': len(promoted_list),
        'retained_count': len(retained_list),
        'graduated_count': len(graduated_list),
        'promoted_students': promoted_list,
        'retained_students': retained_list,
        'graduated_students': graduated_list
    }


# Open / Create New Academic Year (បើកឆ្នាំសិក្សាថ្មី - បញ្ចូលតែឈ្មោះឆ្នាំ ប្រព័ន្ធចាប់យកកាលបរិច្ឆេទដោយស្វ័យប្រវត្តិ & ឡើងថ្នាក់សិស្ស)
@exam_bp.route("/api/academic_years", methods=["POST"])
def create_academic_year():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    data = get_request_data()
    academic_year = (data.get("academic_year") or data.get("year_name") or "").strip()
    
    start_date = data.get("start_date") or date.today().strftime('%Y-%m-%d')
    end_date = data.get("end_date") or None
    status = data.get("status") or "Active"
    description = data.get("description") or f"បានបើកដំណើរការនៅថ្ងៃទី {date.today().strftime('%d/%m/%Y')}"
    auto_promote = data.get("auto_promote", True)

    if not academic_year:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះឆ្នាំសិក្សា (ឧ. 2026-2027)"}), 400

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_academic_years_table(cursor)
        ensure_promotions_table(cursor)

        # 1. Find previous active academic year for student promotion
        cursor.execute("SELECT academic_year_id, academic_year FROM academic_years WHERE status = 'Active' ORDER BY academic_year_id DESC LIMIT 1")
        prev_active = cursor.fetchone()
        prev_year_id = prev_active["academic_year_id"] if prev_active else None

        # 2. If set to 'Active', archive all previous active years (keeping all old scores/exams intact)
        if status == 'Active':
            cursor.execute("UPDATE academic_years SET status = 'Archived', end_date = COALESCE(end_date, CURDATE()) WHERE status = 'Active'")

        # 3. Check if already exists
        cursor.execute("SELECT academic_year_id FROM academic_years WHERE academic_year = %s", (academic_year,))
        existing = cursor.fetchone()

        if existing:
            year_id = existing["academic_year_id"]
            cursor.execute("""
                UPDATE academic_years 
                SET status = %s, start_date = %s, end_date = %s, description = %s
                WHERE academic_year_id = %s
            """, (status, start_date, end_date, description, year_id))
        else:
            cursor.execute("""
                INSERT INTO academic_years (academic_year, start_date, end_date, status, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (academic_year, start_date, end_date, status, description))
            year_id = cursor.lastrowid

        # 4. Automatically Process Student Promotions (Pass -> Next Grade, Fail -> Retained)
        promotion_summary = None
        if auto_promote and status == 'Active':
            try:
                promotion_summary = promote_students_for_academic_year(cursor, prev_year_id, year_id)
            except Exception as prom_err:
                print("[-] Error during auto-promotion:", prom_err)

        conn.commit()

        cursor.execute("SELECT * FROM academic_years WHERE academic_year_id = %s", (year_id,))
        new_year = cursor.fetchone()

        if new_year:
            if new_year.get('start_date'):
                new_year['start_date'] = str(new_year['start_date'])
            if new_year.get('end_date'):
                new_year['end_date'] = str(new_year['end_date'])
            if new_year.get('created_at'):
                new_year['created_at'] = str(new_year['created_at'])

        cursor.close()
        conn.close()

        # Audit Logging
        try:
            from api.api_logs import log_audit_event
            performed_by = (data.get("created_by") or data.get("performed_by") or "លោក នាយកសាលា (Admin)").strip()
            prev_name = prev_active["academic_year"] if prev_active else "គ្មាន"
            prom_txt = f" (បានឡើងថ្នាក់ {promotion_summary['promoted_count']} នាក់)" if promotion_summary else ""
            log_audit_event(
                category="AcademicYear",
                performed_by=performed_by,
                role_badge="🏛️ នាយកសាលា / Admin",
                target_id=f"AY-{year_id}",
                target_name=f"ឆ្នាំសិក្សា: {academic_year}",
                action_type="🚀 បើកឆ្នាំសិក្សាថ្មី",
                old_val=f"ឆ្នាំចាស់: {prev_name}",
                new_val=f"ឆ្នាំថ្មី: {academic_year} (Active)",
                details=f"បានបើកដំណើរការឆ្នាំសិក្សាថ្មី {academic_year} ជាផ្លូវការ{prom_txt}"
            )
        except Exception as log_err:
            print(f"[-] Audit log error on create_academic_year: {log_err}")

        msg = f"បានបើកដំណើរការឆ្នាំសិក្សាថ្មី \"{academic_year}\" ដោយជោគជ័យ!"
        if promotion_summary:
            msg += f" (សិស្សជាប់ឡើងថ្នាក់ {promotion_summary['promoted_count']} នាក់, សិស្សធ្លាក់ត្រួតថ្នាក់ {promotion_summary['retained_count']} នាក់)"

        return jsonify({
            "status": "success",
            "message": msg,
            "academic_year": new_year,
            "promotion_summary": promotion_summary
        }), 201
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


# Preview / Evaluate Promotion for an Academic Year
@exam_bp.route("/api/academic_years/<int:year_id>/promotion_preview", methods=["GET"])
def get_promotion_preview(year_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_promotions_table(cursor)

        cursor.execute("""
            SELECT s.student_id, s.student_code, s.full_name, s.gender, s.grade,
                   c.class_id, c.class_name, c.grade as class_grade
            FROM students s
            LEFT JOIN student_classes sc ON s.student_id = sc.student_id
            LEFT JOIN classes c ON sc.class_id = c.class_id
            WHERE s.status = 'Active' OR s.status IS NULL
            GROUP BY s.student_id
            ORDER BY s.full_name ASC
        """)
        students = cursor.fetchall()

        preview_list = []
        for st in students:
            s_id = st['student_id']
            curr_g = st.get('grade') or st.get('class_grade') or 'Grade 10'
            perf = evaluate_student_annual_result(cursor, s_id, year_id)
            avg = perf['avg_score']
            is_passed = (avg >= 50.0) or (perf['total_exams'] == 0)
            
            next_g = get_next_grade_level(curr_g) if is_passed else curr_g
            action = 'Graduated' if ('Graduated' in next_g) else ('Promoted' if is_passed else 'Retained')
            
            preview_list.append({
                'student_id': s_id,
                'name': st['full_name'],
                'student_code': st['student_code'],
                'gender': st['gender'],
                'current_grade': curr_g,
                'class_name': st.get('class_name') or 'គ្មានថ្នាក់',
                'avg_score': avg,
                'total_exams': perf['total_exams'],
                'result_status': 'Pass' if is_passed else 'Fail',
                'action': action,
                'new_grade': next_g
            })

        cursor.close()
        conn.close()

        pass_count = sum(1 for p in preview_list if p['result_status'] == 'Pass')
        fail_count = sum(1 for p in preview_list if p['result_status'] == 'Fail')

        return jsonify({
            "status": "success",
            "year_id": year_id,
            "total_students": len(preview_list),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "students": preview_list
        })
    except Exception as e:
        if conn:
            conn.close()
        return jsonify({"status": "error", "message": str(e)}), 500


# Set Active / Switch Academic Year (កំណត់ឆ្នាំសិក្សាដែលកំពុងដំណើរការ)
@exam_bp.route("/api/academic_years/<int:year_id>/activate", methods=["PUT", "POST"])
def activate_academic_year(year_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_academic_years_table(cursor)

        # Verify exists
        cursor.execute("SELECT * FROM academic_years WHERE academic_year_id = %s", (year_id,))
        target = cursor.fetchone()
        if not target:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "រកមិនឃើញឆ្នាំសិក្សានេះទេ"}), 404

        # Archive others, set this one to Active
        cursor.execute("UPDATE academic_years SET status = 'Archived' WHERE status = 'Active'")
        cursor.execute("UPDATE academic_years SET status = 'Active' WHERE academic_year_id = %s", (year_id,))
        conn.commit()

        cursor.close()
        conn.close()

        # Audit Logging
        try:
            from api.api_logs import log_audit_event
            req_data = request.get_json(silent=True) or {}
            performed_by = (req_data.get("performed_by") or "លោក នាយកសាលា (Admin)").strip()
            log_audit_event(
                category="AcademicYear",
                performed_by=performed_by,
                role_badge="🏛️ នាយកសាលា / Admin",
                target_id=f"AY-{year_id}",
                target_name=f"ឆ្នាំសិក្សា: {target['academic_year']}",
                action_type="🚀 បើក/ប្តូរប្រើឆ្នាំសិក្សា",
                old_val="ស្ថានភាព: Archived/Closed",
                new_val="ស្ថានភាព: Active (កំពុងដំណើរការ)",
                details=f"បានកំណត់ឆ្នាំសិក្សា {target['academic_year']} ជាឆ្នាំសិក្សាសកម្មផ្លូវការ"
            )
        except Exception as log_err:
            print(f"[-] Audit log error on activate_academic_year: {log_err}")

        return jsonify({
            "status": "success",
            "message": f"បានប្តូរទៅប្រើឆ្នាំសិក្សា \"{target['academic_year']}\" ជាផ្លូវការជោគជ័យ!",
            "academic_year_id": year_id,
            "academic_year": target['academic_year']
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Close / Lock Academic Year (បិទបញ្ចប់ឆ្នាំសិក្សា - គ្រូទាំងអស់មើលបានតែប៉ុណ្ណោះ មិនអាចកែប្រែបានឡើយ)
@exam_bp.route("/api/academic_years/<int:year_id>/close", methods=["PUT", "POST"])
def close_academic_year(year_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_academic_years_table(cursor)

        cursor.execute("SELECT * FROM academic_years WHERE academic_year_id = %s", (year_id,))
        target = cursor.fetchone()
        if not target:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "រកមិនឃើញឆ្នាំសិក្សានេះទេ"}), 404

        # Mark as Closed / Archived and set end_date
        today_str = date.today().strftime('%Y-%m-%d')
        cursor.execute("""
            UPDATE academic_years 
            SET status = 'Closed', end_date = COALESCE(end_date, %s)
            WHERE academic_year_id = %s
        """, (today_str, year_id))
        conn.commit()

        cursor.close()
        conn.close()

        # Audit Logging
        try:
            from api.api_logs import log_audit_event
            req_data = request.get_json(silent=True) or {}
            performed_by = (req_data.get("performed_by") or "លោក នាយកសាលា (Admin)").strip()
            log_audit_event(
                category="AcademicYear",
                performed_by=performed_by,
                role_badge="🏛️ នាយកសាលា / Admin",
                target_id=f"AY-{year_id}",
                target_name=f"ឆ្នាំសិក្សា: {target['academic_year']}",
                action_type="🔒 បិទបញ្ចប់ឆ្នាំសិក្សា",
                old_val="ស្ថានភាព: Active (កំពុងដំណើរការ)",
                new_val="ស្ថានភាព: Closed (បានបិទបញ្ចប់)",
                details=f"បានបិទបញ្ចប់ឆ្នាំសិក្សា {target['academic_year']} ជាផ្លូវការ (គ្រូទាំងអស់ស្ថិតក្នុងស្ថានភាព View Only)"
            )
        except Exception as log_err:
            print(f"[-] Audit log error on close_academic_year: {log_err}")

        return jsonify({
            "status": "success",
            "message": f"បានបិទបញ្ចប់ឆ្នាំសិក្សា \"{target['academic_year']}\" ដោយជោគជ័យ! (គ្រូទាំងអស់ស្ថិតក្នុងស្ថានភាព View Only)",
            "academic_year_id": year_id,
            "academic_year": target['academic_year']
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Update Academic Year Details
@exam_bp.route("/api/academic_years/<int:year_id>", methods=["PUT"])
def update_academic_year(year_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    data = get_request_data()
    academic_year = data.get("academic_year")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    status = data.get("status")
    description = data.get("description")

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_academic_years_table(cursor)

        if status == 'Active':
            cursor.execute("UPDATE academic_years SET status = 'Archived' WHERE status = 'Active' AND academic_year_id != %s", (year_id,))

        update_fields = []
        params = []
        if academic_year:
            update_fields.append("academic_year = %s")
            params.append(academic_year)
        if start_date is not None:
            update_fields.append("start_date = %s")
            params.append(start_date if start_date else None)
        if end_date is not None:
            update_fields.append("end_date = %s")
            params.append(end_date if end_date else None)
        if status:
            update_fields.append("status = %s")
            params.append(status)
        if description is not None:
            update_fields.append("description = %s")
            params.append(description)

        if update_fields:
            params.append(year_id)
            query = f"UPDATE academic_years SET {', '.join(update_fields)} WHERE academic_year_id = %s"
            cursor.execute(query, tuple(params))
            conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានកែប្រែព័ត៌មានឆ្នាំសិក្សាជោគជ័យ!"
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 2. EXAMINATIONS APIs
# ----------------------------------------------------

# GET all examinations (Filtered by teacher_id or class_id if provided)
@exam_bp.route("/api/examinations", methods=["GET"])
@exam_bp.route("/api/exams", methods=["GET"])
def get_examinations():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    teacher_id = request.args.get("teacher_id")
    class_id = request.args.get("class_id")

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_exam_table_columns(cursor)

        query = """
            SELECT 
                e.exam_id,
                e.exam_name,
                e.week,
                e.academic_year_id,
                e.teacher_id,
                e.class_id,
                ay.academic_year,
                ay.status as academic_year_status
            FROM examinations e
            LEFT JOIN academic_years ay ON e.academic_year_id = ay.academic_year_id
        """
        params = []
        conditions = []

        academic_year_id = request.args.get("academic_year_id")
        include_all = request.args.get("include_all") == "1" or request.args.get("all") == "1"

        if academic_year_id:
            conditions.append("e.academic_year_id = %s")
            params.append(academic_year_id)
        elif not include_all:
            # Default for active dashboard: only show exams for the current active academic year
            conditions.append("(e.academic_year_id = (SELECT academic_year_id FROM academic_years WHERE status = 'Active' LIMIT 1) OR (ay.status = 'Active' AND e.academic_year_id IS NOT NULL))")

        if teacher_id and class_id:
            conditions.append("(e.teacher_id = %s OR e.class_id = %s)")
            params.extend([teacher_id, class_id])
        elif teacher_id:
            conditions.append("e.teacher_id = %s")
            params.append(teacher_id)
        elif class_id:
            conditions.append("e.class_id = %s")
            params.append(class_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY e.exam_id DESC"
        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "examinations": rows,
            "total": len(rows)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# GET latest examination
@exam_bp.route("/api/examinations/latest", methods=["GET"])
@exam_bp.route("/api/exam/latest", methods=["GET"])
def get_latest_examination():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    teacher_id = request.args.get("teacher_id")
    class_id = request.args.get("class_id")

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_exam_table_columns(cursor)

        query = """
            SELECT 
                e.exam_id,
                e.exam_name,
                e.week,
                e.academic_year_id,
                e.teacher_id,
                e.class_id,
                ay.academic_year,
                ay.status as academic_year_status
            FROM examinations e
            LEFT JOIN academic_years ay ON e.academic_year_id = ay.academic_year_id
        """
        params = []
        conditions = []

        if teacher_id and class_id:
            conditions.append("(e.teacher_id = %s OR e.class_id = %s)")
            params.extend([teacher_id, class_id])
        elif teacher_id:
            conditions.append("e.teacher_id = %s")
            params.append(teacher_id)
        elif class_id:
            conditions.append("e.class_id = %s")
            params.append(class_id)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY e.exam_id DESC LIMIT 1"
        cursor.execute(query, tuple(params))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({"status": "error", "message": "មិនទាន់មានទិន្នន័យការប្រឡងនៅឡើយទេ", "examination": None}), 404

        return jsonify({
            "status": "success",
            "examination": row
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# GET single examination by ID
@exam_bp.route("/api/examinations/<int:exam_id>", methods=["GET"])
@exam_bp.route("/api/exam/<int:exam_id>", methods=["GET"])
def get_examination_by_id(exam_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_exam_table_columns(cursor)

        query = """
            SELECT 
                e.exam_id,
                e.exam_name,
                e.week,
                e.academic_year_id,
                e.teacher_id,
                e.class_id,
                ay.academic_year,
                ay.status as academic_year_status
            FROM examinations e
            LEFT JOIN academic_years ay ON e.academic_year_id = ay.academic_year_id
            WHERE e.exam_id = %s
        """
        cursor.execute(query, (exam_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({"status": "error", "message": "រកមិនឃើញការប្រឡងនេះទេ (Examination not found)"}), 404

        return jsonify({
            "status": "success",
            "examination": row
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# POST create new examination
@exam_bp.route("/api/examinations", methods=["POST"])
@exam_bp.route("/api/addexamination", methods=["POST"])
@exam_bp.route("/api/addexam", methods=["POST"])
def add_examination():
    data = get_request_data()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    exam_name = data.get("exam_name") or data.get("name")
    week = data.get("week") or data.get("code") or data.get("week_number")
    academic_year_id = data.get("academic_year_id")
    academic_year_str = data.get("academic_year") or data.get("year")
    teacher_id = data.get("teacher_id")
    class_id = data.get("class_id")

    if not exam_name:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះការប្រឡង (Exam name is required)"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_exam_table_columns(cursor)

        # Check if there is an active academic year
        cursor.execute("SELECT academic_year_id, academic_year FROM academic_years WHERE status = 'Active' LIMIT 1")
        active_yr = cursor.fetchone()
        if not active_yr:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "code": "ACADEMIC_YEAR_LOCKED",
                "message": "មិនអាចបង្កើតការប្រឡង ឬខែប្រឡងថ្មីបានឡើយ ដោយសារបច្ចុប្បន្នមិនទាន់មានឆ្នាំសិក្សាសកម្មដែលបានបើកដំណើរការ (No Active Academic Year)!"
            }), 403

        # Use the active academic year
        academic_year_id = active_yr["academic_year_id"]

        # Insert Examination with teacher_id and class_id
        cursor.execute(
            """INSERT INTO examinations (exam_name, week, academic_year_id, teacher_id, class_id)
               VALUES (%s, %s, %s, %s, %s)""",
            (exam_name, week, academic_year_id, teacher_id, class_id)
        )
        conn.commit()
        new_exam_id = cursor.lastrowid

        # Fetch newly created row
        cursor.execute("""
            SELECT 
                e.exam_id,
                e.exam_name,
                e.week,
                e.academic_year_id,
                e.teacher_id,
                e.class_id,
                ay.academic_year
            FROM examinations e
            LEFT JOIN academic_years ay ON e.academic_year_id = ay.academic_year_id
            WHERE e.exam_id = %s
        """, (new_exam_id,))
        created_exam = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានបង្កើតការប្រឡងក្នុង Database ជោគជ័យ!",
            "examination": created_exam
        }), 201
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500


# PUT edit examination
@exam_bp.route("/api/examinations/<int:exam_id>", methods=["PUT", "POST"])
@exam_bp.route("/api/editexamination/<int:exam_id>", methods=["PUT", "POST"])
@exam_bp.route("/api/editexam/<int:exam_id>", methods=["PUT", "POST"])
def edit_examination(exam_id):
    data = get_request_data()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    exam_name = data.get("exam_name") or data.get("name")
    week = data.get("week") or data.get("code")
    academic_year_id = data.get("academic_year_id")

    if not exam_name:
        return jsonify({"status": "error", "message": "Exam name is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """UPDATE examinations 
               SET exam_name = %s, week = %s, academic_year_id = %s 
               WHERE exam_id = %s""",
            (exam_name, week, academic_year_id, exam_id)
        )
        conn.commit()
        affected = cursor.rowcount

        cursor.execute("""
            SELECT 
                e.exam_id,
                e.exam_name,
                e.week,
                e.academic_year_id,
                ay.academic_year
            FROM examinations e
            LEFT JOIN academic_years ay ON e.academic_year_id = ay.academic_year_id
            WHERE e.exam_id = %s
        """, (exam_id,))
        updated_exam = cursor.fetchone()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានកែប្រែការប្រឡងជោគជ័យ!",
            "examination": updated_exam
        })
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500


# DELETE examination
@exam_bp.route("/api/examinations/<int:exam_id>", methods=["DELETE", "POST"])
@exam_bp.route("/api/deleteexamination/<int:exam_id>", methods=["DELETE", "POST"])
@exam_bp.route("/api/deleteexam/<int:exam_id>", methods=["DELETE", "POST"])
def delete_examination(exam_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("DELETE FROM examinations WHERE exam_id = %s", (exam_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()

        if affected == 0:
            return jsonify({"status": "error", "message": "រកមិនឃើញការប្រឡងនេះទេ"}), 404

        return jsonify({
            "status": "success",
            "message": "បានលុបការប្រឡងជោគជ័យ!",
            "exam_id": exam_id
        })
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500
