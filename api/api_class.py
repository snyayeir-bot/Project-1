from api import api_aeccunt_teachers
from flask import Blueprint, request, jsonify
from db import get_db_connection

class_bp = Blueprint('class_bp', __name__)

# ----------------------------------------------------
# 0. GET AVAILABLE / UNASSIGNED TEACHERS FOR HOMEROOM
# ----------------------------------------------------
@class_bp.route("/api/available_teachers", methods=["GET"])
@class_bp.route("/api/unassigned_teachers", methods=["GET"])
def get_available_teachers():
    """
    Returns teachers who do NOT have a homeroom class assigned yet in the active academic year.
    Every teacher becomes available anew to be assigned in each new academic year.
    Optional query param: ?include_class_id=<id> to also include the current teacher of that class when editing.
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    include_class_id = request.args.get("include_class_id") or request.args.get("class_id")
    target_year_id = request.args.get("academic_year_id") or request.args.get("year_id")

    try:
        cursor = conn.cursor(dictionary=True)

        # Get active year if target_year_id not specified
        if not target_year_id:
            cursor.execute("SELECT academic_year_id FROM academic_years WHERE status = 'Active' ORDER BY academic_year_id DESC LIMIT 1")
            act_row = cursor.fetchone()
            target_year_id = act_row['academic_year_id'] if act_row else None

        # Query teachers available for the target/active academic year
        if include_class_id and str(include_class_id).isdigit():
            query = """
                SELECT t.teacher_id, t.teacher_code, t.full_name, t.gender, t.specialty, t.phone, t.email, t.status
                FROM teachers t
                WHERE t.teacher_id NOT IN (
                    SELECT tc.teacher_id 
                    FROM teacher_classes tc 
                    JOIN classes c ON tc.class_id = c.class_id 
                    WHERE (c.academic_year_id = %s OR (%s IS NULL AND c.academic_year_id IS NULL))
                      AND c.class_id != %s
                )
                ORDER BY t.full_name ASC
            """
            cursor.execute(query, (target_year_id, target_year_id, int(include_class_id)))
        else:
            query = """
                SELECT t.teacher_id, t.teacher_code, t.full_name, t.gender, t.specialty, t.phone, t.email, t.status
                FROM teachers t
                WHERE t.teacher_id NOT IN (
                    SELECT tc.teacher_id 
                    FROM teacher_classes tc 
                    JOIN classes c ON tc.class_id = c.class_id 
                    WHERE (c.academic_year_id = %s OR (%s IS NULL AND c.academic_year_id IS NULL))
                )
                ORDER BY t.full_name ASC
            """
            cursor.execute(query, (target_year_id, target_year_id))

        teachers = cursor.fetchall()
        cursor.close()
        conn.close()

        # Format date objects for JSON serialization
        for t in teachers:
            if t.get('date_of_birth'):
                t['date_of_birth'] = str(t['date_of_birth'])

        return jsonify({
            "status": "success",
            "message": "Available teachers retrieved successfully",
            "teachers": teachers,
            "count": len(teachers)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error fetching available teachers: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 0.1 GET AVAILABLE / UNASSIGNED STUDENTS FOR CLASS
# ----------------------------------------------------
@class_bp.route("/api/available_students", methods=["GET"])
@class_bp.route("/api/unassigned_students", methods=["GET"])
def get_available_students():
    """
    Returns students for class assignment.
    Supports query parameters:
      - ?q=<search term>
      - ?unassigned_only=1 (to only return students with no class)
      - ?class_id=<id> (to exclude students already in this class)
      - ?include_all=1 (return all students with their current class info)
    """
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    q = (request.args.get("q") or request.args.get("query") or "").strip()
    unassigned_only = request.args.get("unassigned_only") == "1"
    target_class_id = request.args.get("class_id") or request.args.get("target_class_id")

    try:
        cursor = conn.cursor(dictionary=True)
        
        base_query = """
            SELECT s.*, sc.class_id AS current_class_id, c.class_name AS current_class_name
            FROM students s
            LEFT JOIN student_classes sc ON s.student_id = sc.student_id
            LEFT JOIN classes c ON sc.class_id = c.class_id
            WHERE 1=1
        """
        params = []

        if unassigned_only:
            base_query += " AND sc.class_id IS NULL "
        elif target_class_id:
            # Exclude students who are ALREADY in this target class
            base_query += " AND (sc.class_id IS NULL OR sc.class_id != %s) "
            params.append(target_class_id)

        if q:
            base_query += """
                AND (s.full_name LIKE %s 
                     OR s.student_code LIKE %s 
                     OR s.student_id = %s 
                     OR s.phone LIKE %s)
            """
            params.extend([f"%{q}%", f"%{q}%", int(q) if q.isdigit() else 0, f"%{q}%"])

        base_query += " ORDER BY (sc.class_id IS NULL) DESC, s.student_id DESC"

        cursor.execute(base_query, tuple(params))
        students = cursor.fetchall()
        cursor.close()
        conn.close()

        for s in students:
            if s.get('date_of_birth'):
                s['date_of_birth'] = str(s['date_of_birth'])
            else:
                s['date_of_birth'] = ""

        return jsonify({
            "status": "success",
            "message": "Students retrieved successfully for class assignment",
            "students": students,
            "count": len(students)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error fetching available students: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 1. GET ALL CLASSES (WITH ASSIGNED HOMEROOM TEACHERS)
# ----------------------------------------------------
@class_bp.route("/api/classes", methods=["GET"])
@class_bp.route("/api/class", methods=["GET"])
def get_classes():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    year_param = request.args.get('academic_year_id') or request.args.get('year_id')
    all_years = request.args.get('all') in ('true', '1', 'yes')

    try:
        cursor = conn.cursor(dictionary=True)
        where_clause = ""
        params = []

        if year_param and str(year_param).isdigit():
            where_clause = "WHERE c.academic_year_id = %s"
            params.append(int(year_param))
        elif not all_years:
            # Strictly return active classes of the CURRENT active academic year (never show past promoted classes)
            where_clause = """
                WHERE c.academic_year_id = (SELECT academic_year_id FROM academic_years WHERE status = 'Active' ORDER BY academic_year_id DESC LIMIT 1)
                   OR (c.academic_year_id IS NULL AND (SELECT COUNT(*) FROM academic_years WHERE status = 'Active') = 0)
            """

        query = f"""
            SELECT c.*, 
                   ay.academic_year,
                   t.teacher_id, 
                   t.teacher_code, 
                   t.full_name AS instructor, 
                   t.gender AS instructor_gender,
                   t.specialty AS instructor_specialty,
                   t.phone AS instructor_phone,
                   t.email AS instructor_email,
                   COUNT(DISTINCT sc.student_id) AS students_count,
                   COUNT(DISTINCT CASE WHEN s.gender IN ('ស្រី', 'Female', 'female', 'F', 'f') THEN sc.student_id END) AS female_count,
                   COUNT(DISTINCT CASE WHEN s.gender IN ('ប្រុស', 'Male', 'male', 'M', 'm') THEN sc.student_id END) AS male_count
            FROM classes c
            LEFT JOIN academic_years ay ON c.academic_year_id = ay.academic_year_id
            LEFT JOIN teacher_classes tc ON c.class_id = tc.class_id
            LEFT JOIN teachers t ON tc.teacher_id = t.teacher_id
            LEFT JOIN student_classes sc ON c.class_id = sc.class_id AND (sc.academic_year_id = c.academic_year_id OR sc.academic_year_id IS NULL)
            LEFT JOIN students s ON sc.student_id = s.student_id
            {where_clause}
            GROUP BY c.class_id, t.teacher_id, ay.academic_year
            ORDER BY c.class_id DESC
        """
        cursor.execute(query, params)
        class_all = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "classes": class_all,
            "count": len(class_all)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500
        

# ----------------------------------------------------
# 2. CREATE NEW CLASS (AND LINK HOMEROOM INSTRUCTOR)
# ----------------------------------------------------
@class_bp.route("/api/create_class", methods=["POST"])
@class_bp.route("/api/addclass", methods=["POST"])
def create_class():
    data = request.get_json(silent=True) or request.form

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    class_name = (data.get("class_name") or data.get("name") or "").strip()
    grade = (data.get("grade") or data.get("class_grade") or data.get("grade_level") or "").strip()
    room = (data.get("room") or data.get("class_room") or "").strip()
    teacher_id = data.get("teacher_id") or data.get("instructor_id")
    academic_year_id = data.get("academic_year_id")

    if not class_name:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះថ្នាក់រៀន (Class Name is required)"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        if not academic_year_id:
            cursor.execute("SELECT academic_year_id FROM academic_years WHERE status = 'Active' ORDER BY academic_year_id DESC LIMIT 1")
            act_yr = cursor.fetchone()
            academic_year_id = act_yr['academic_year_id'] if act_yr else None

        cursor.execute(
            """
                INSERT INTO classes (class_name, grade, room, academic_year_id)
                VALUES (%s, %s, %s, %s)
            """,
            (class_name, grade, room, academic_year_id)
        )
        conn.commit()
        new_id = cursor.lastrowid

        teacher_info = None
        # If homeroom teacher was chosen, link in teacher_classes
        if teacher_id and str(teacher_id).strip() and str(teacher_id) != "0":
            try:
                cursor.execute("DELETE FROM teacher_classes WHERE class_id = %s", (new_id,))
                cursor.execute(
                    "INSERT INTO teacher_classes (teacher_id, class_id) VALUES (%s, %s)",
                    (teacher_id, new_id)
                )
                conn.commit()

                cursor.execute(
                    "SELECT teacher_id, teacher_code, full_name, specialty, phone, email FROM teachers WHERE teacher_id = %s", 
                    (teacher_id,)
                )
                teacher_info = cursor.fetchone()
            except Exception as e_tch:
                print(f"Warning linking teacher to class: {e_tch}")

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Class created successfully",
            "class": {
                "class_id": new_id,
                "class_name": class_name,
                "grade": grade,
                "room": room,
                "teacher_id": teacher_id,
                "instructor": teacher_info.get("full_name") if teacher_info else None,
                "teacher": teacher_info
            }
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
# 3. EDIT CLASS (AND UPDATE HOMEROOM INSTRUCTOR)
# ----------------------------------------------------
@class_bp.route("/api/editclass/<int:class_id>", methods=["PUT", "POST"])
@class_bp.route("/api/editclass", methods=["PUT", "POST"])
def edit_class(class_id=None):
    data = request.get_json(silent=True) or request.form

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    if class_id is None:
        class_id = data.get("class_id")

    if not class_id:
        return jsonify({"status": "error", "message": "Class ID is required"}), 400

    class_name = (data.get("class_name") or data.get("name") or "").strip()
    grade = (data.get("grade") or data.get("class_grade") or data.get("grade_level") or "").strip()
    room = (data.get("room") or data.get("class_room") or "").strip()
    teacher_id = data.get("teacher_id") or data.get("instructor_id")

    if not class_name:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះថ្នាក់រៀន (Class Name is required)"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """
                UPDATE classes 
                SET class_name = %s, grade = %s, room = %s 
                WHERE class_id = %s
            """,
            (class_name, grade, room, class_id)
        )
        conn.commit()

        teacher_info = None
        if teacher_id is not None:
            # Update teacher assigned to this class
            cursor.execute("DELETE FROM teacher_classes WHERE class_id = %s", (class_id,))
            if str(teacher_id).strip() and str(teacher_id) != "0":
                cursor.execute(
                    "INSERT INTO teacher_classes (teacher_id, class_id) VALUES (%s, %s)",
                    (teacher_id, class_id)
                )
                cursor.execute(
                    "SELECT teacher_id, teacher_code, full_name, specialty, phone, email FROM teachers WHERE teacher_id = %s", 
                    (teacher_id,)
                )
                teacher_info = cursor.fetchone()
            conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Class updated successfully",
            "class": {
                "class_id": class_id,
                "class_name": class_name,
                "grade": grade,
                "room": room,
                "teacher_id": teacher_id,
                "instructor": teacher_info.get("full_name") if teacher_info else None,
                "teacher": teacher_info
            }
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
# 3.1 ASSIGN HOMEROOM TEACHER TO CLASS (ចាត់តាំងគ្រូបន្ទុកថ្នាក់)
# ----------------------------------------------------
@class_bp.route("/api/classes/<int:class_id>/assign_teacher", methods=["POST", "PUT"])
@class_bp.route("/api/assign_teacher_to_class", methods=["POST", "PUT"])
def assign_teacher_to_class(class_id=None):
    data = request.get_json(silent=True) or request.form or {}
    
    if class_id is None:
        class_id = data.get("class_id") or data.get("target_class_id")
        
    try:
        class_id = int(str(class_id).replace("class-", ""))
    except Exception:
        return jsonify({"status": "error", "message": "Invalid class ID"}), 400

    teacher_id = data.get("teacher_id") or data.get("instructor_id")
    
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        
        # Verify class exists
        cursor.execute("SELECT class_id, class_name, grade, room FROM classes WHERE class_id = %s", (class_id,))
        cls_info = cursor.fetchone()
        if not cls_info:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": f"រកមិនឃើញថ្នាក់រៀន ID: {class_id}"}), 404

        # Remove existing teacher for this class
        cursor.execute("DELETE FROM teacher_classes WHERE class_id = %s", (class_id,))
        
        teacher_info = None
        if teacher_id and str(teacher_id).strip() and str(teacher_id) != "0":
            t_id = int(str(teacher_id).strip())

            # Also unassign this teacher if they were assigned to another class in the SAME academic year
            cursor.execute("""
                DELETE FROM teacher_classes 
                WHERE teacher_id = %s 
                  AND class_id IN (
                      SELECT class_id FROM classes 
                      WHERE academic_year_id = (SELECT academic_year_id FROM classes WHERE class_id = %s)
                         OR (academic_year_id IS NULL)
                  )
            """, (t_id, class_id))
            
            # Assign to current class
            cursor.execute(
                "INSERT INTO teacher_classes (teacher_id, class_id) VALUES (%s, %s)",
                (t_id, class_id)
            )
            
            cursor.execute(
                "SELECT teacher_id, teacher_code, full_name, specialty, phone, email, gender FROM teachers WHERE teacher_id = %s",
                (t_id,)
            )
            teacher_info = cursor.fetchone()

        conn.commit()
        cursor.close()
        conn.close()

        teacher_name = teacher_info.get("full_name") if teacher_info else "មិនទាន់មានគ្រូបន្ទុក"
        msg = f"បានចាត់តាំងលោកគ្រូ/អ្នកគ្រូ \"{teacher_name}\" ជាគ្រូបន្ទុកថ្នាក់ \"{cls_info.get('class_name')}\" ដោយជោគជ័យ!" if teacher_info else f"បានដកការចាត់តាំងគ្រូបន្ទុកថ្នាក់ចេញពី \"{cls_info.get('class_name')}\" រួចរាល់!"

        return jsonify({
            "status": "success",
            "message": msg,
            "class_id": class_id,
            "class_name": cls_info.get("class_name"),
            "teacher_id": teacher_id if teacher_info else None,
            "instructor": teacher_name,
            "teacher": teacher_info
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
# 4. DELETE CLASS
# ----------------------------------------------------
@class_bp.route("/api/deleteclass/<int:class_id>", methods=["DELETE", "POST"])
@class_bp.route("/api/deleteclass", methods=["DELETE", "POST"])
def delete_class(class_id=None):
    if class_id is None:
        data = request.get_json(silent=True) or request.form
        class_id = data.get("class_id") if data else None

    if not class_id:
        return jsonify({"status": "error", "message": "Class ID is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        # Delete related records in teacher_classes and student_classes first
        try:
            cursor.execute("DELETE FROM teacher_classes WHERE class_id = %s", (class_id,))
            cursor.execute("DELETE FROM student_classes WHERE class_id = %s", (class_id,))
            conn.commit()
        except Exception:
            pass

        cursor.execute("DELETE FROM classes WHERE class_id = %s", (class_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()

        if affected == 0:
            return jsonify({"status": "error", "message": "រកមិនឃើញថ្នាក់រៀននេះទេ"}), 404

        return jsonify({
            "status": "success",
            "message": "Class deleted successfully",
            "class_id": class_id
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
# 5. GET ALL STUDENTS IN A SPECIFIC CLASS
# ----------------------------------------------------
@class_bp.route("/api/class/<int:class_id>/students", methods=["GET"])
@class_bp.route("/api/class_students/<int:class_id>", methods=["GET"])
def get_class_students(class_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT s.*, sc.student_class_id, sc.class_id, c.grade AS class_grade, c.class_name
            FROM students s
            JOIN student_classes sc ON s.student_id = sc.student_id
            JOIN classes c ON sc.class_id = c.class_id
            WHERE sc.class_id = %s
            ORDER BY s.student_id DESC
        """
        cursor.execute(query, (class_id,))
        students = cursor.fetchall()
        cursor.close()
        conn.close()

        for s in students:
            if s.get('date_of_birth'):
                s['date_of_birth'] = str(s['date_of_birth'])
            else:
                s['date_of_birth'] = ""

        return jsonify({
            "status": "success",
            "class_id": class_id,
            "students": students,
            "count": len(students)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 6. ADD / LINK STUDENT TO CLASS (student_classes)
# ----------------------------------------------------
@class_bp.route("/api/add_student_to_class", methods=["POST"])
@class_bp.route("/api/class_students", methods=["POST"])
def add_student_to_class():
    data = request.get_json(silent=True) or request.form
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    class_id = data.get("class_id")
    if not class_id:
        return jsonify({"status": "error", "message": "Class ID is required"}), 400

    student_ids = data.get("student_ids")
    student_id = data.get("student_id")
    student_code = (data.get("student_code") or "").strip()
    full_name = (data.get("full_name") or data.get("name") or "").strip()
    gender = (data.get("gender") or "Male").strip()
    date_of_birth = (data.get("date_of_birth") or data.get("dob") or "").strip() or None
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    father_name = (data.get("father_name") or "").strip()
    father_phone = (data.get("father_phone") or "").strip()
    mother_name = (data.get("mother_name") or "").strip()
    mother_phone = (data.get("mother_phone") or "").strip()
    status = (data.get("status") or "Active").strip()

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        # Get academic_year_id of this class
        cursor.execute("SELECT academic_year_id FROM classes WHERE class_id = %s", (class_id,))
        cls_row = cursor.fetchone()
        class_yr_id = cls_row['academic_year_id'] if cls_row else None
        if not class_yr_id:
            cursor.execute("SELECT academic_year_id FROM academic_years WHERE status = 'Active' ORDER BY academic_year_id DESC LIMIT 1")
            act_yr = cursor.fetchone()
            class_yr_id = act_yr['academic_year_id'] if act_yr else None

        # Handle Batch / Multiple Students Array
        if isinstance(student_ids, list) and len(student_ids) > 0:
            added_students = []
            for sid in student_ids:
                try:
                    num_sid = int(sid)
                except (ValueError, TypeError):
                    continue

                # Check if student exists
                cursor.execute("SELECT * FROM students WHERE student_id = %s", (num_sid,))
                st = cursor.fetchone()
                if not st:
                    continue

                # Cleanly assign student to this class for this academic year (preserves historical year enrollments)
                cursor.execute("DELETE FROM student_classes WHERE student_id = %s AND (academic_year_id = %s OR academic_year_id IS NULL)", (num_sid, class_yr_id))
                cursor.execute("INSERT INTO student_classes (student_id, class_id, academic_year_id) VALUES (%s, %s, %s)", (num_sid, class_id, class_yr_id))
                if st.get('date_of_birth'):
                    st['date_of_birth'] = str(st['date_of_birth'])
                added_students.append(st)

            conn.commit()
            cursor.close()
            conn.close()

            return jsonify({
                "status": "success",
                "message": f"បានបញ្ចូលសិស្សចំនួន {len(added_students)} នាក់ទៅក្នុងថ្នាក់ដោយជោគជ័យ!",
                "added_count": len(added_students),
                "students": added_students,
                "class_id": class_id
            }), 200

        final_student_id = None

        # Case 1: Existing student ID provided
        if student_id:
            cursor.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
            st_row = cursor.fetchone()
            if st_row:
                final_student_id = st_row['student_id']

        # Case 2: Match by student_code
        if not final_student_id and student_code:
            cursor.execute("SELECT * FROM students WHERE student_code = %s", (student_code,))
            st_row = cursor.fetchone()
            if st_row:
                final_student_id = st_row['student_id']

        # Case 3: Match by full_name
        if not final_student_id and full_name:
            cursor.execute("SELECT * FROM students WHERE full_name = %s", (full_name,))
            st_row = cursor.fetchone()
            if st_row:
                final_student_id = st_row['student_id']

        # Case 4: Student does not exist in DB yet -> Create new student record
        if not final_student_id:
            if not full_name:
                return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះសិស្ស (Student name is required)"}), 400

            if not student_code:
                cursor.execute("SELECT MAX(student_id) AS max_id FROM students")
                max_id = (cursor.fetchone()['max_id'] or 0) + 1
                student_code = f"STD-2026-{max_id:03d}"

            cursor.execute(
                """INSERT INTO students 
                   (student_code, full_name, gender, date_of_birth, phone, address, father_name, father_phone, mother_name, mother_phone, status) 
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (student_code, full_name, gender, date_of_birth, phone, address, father_name, father_phone, mother_name, mother_phone, status)
            )
            conn.commit()
            final_student_id = cursor.lastrowid

        # Cleanly link student to class in student_classes for this academic year
        cursor.execute("DELETE FROM student_classes WHERE student_id = %s AND (academic_year_id = %s OR academic_year_id IS NULL)", (final_student_id, class_yr_id))
        cursor.execute("INSERT INTO student_classes (student_id, class_id, academic_year_id) VALUES (%s, %s, %s)", (final_student_id, class_id, class_yr_id))
        conn.commit()

        # Fetch complete student data for frontend
        cursor.execute("SELECT * FROM students WHERE student_id = %s", (final_student_id,))
        student_data = cursor.fetchone()
        if student_data and student_data.get('date_of_birth'):
            student_data['date_of_birth'] = str(student_data['date_of_birth'])

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានបញ្ចូលសិស្ស '{student_data.get('full_name')}' ក្នុងថ្នាក់ដោយជោគជ័យ!",
            "student": student_data,
            "class_id": class_id
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        print(f"[-] Error adding student to class: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 7. REMOVE STUDENT FROM CLASS
# ----------------------------------------------------
@class_bp.route("/api/remove_student_from_class", methods=["POST", "DELETE"])
@class_bp.route("/api/remove_student_from_class/<int:class_id>/<int:student_id>", methods=["POST", "DELETE"])
def remove_student_from_class(class_id=None, student_id=None):
    if class_id is None or student_id is None:
        data = request.get_json(silent=True) or request.form or {}
        class_id = class_id or data.get("class_id")
        student_id = student_id or data.get("student_id")

    if not class_id or not student_id:
        return jsonify({"status": "error", "message": "Class ID and Student ID are required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "DELETE FROM student_classes WHERE class_id = %s AND student_id = %s",
            (class_id, student_id)
        )
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "Student removed from class successfully",
            "affected": affected
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500

