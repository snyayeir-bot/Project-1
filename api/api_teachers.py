from flask import Blueprint, request, jsonify
from db import get_db_connection
import datetime

teachers_bp = Blueprint('teachers_bp', __name__)

def sanitize_date(val):
    if not val or str(val).strip() == "" or str(val).strip() == "—" or str(val).strip() == "null" or str(val).strip() == "None":
        return None
    val_str = str(val).strip()
    try:
        datetime.datetime.strptime(val_str, "%Y-%m-%d")
        return val_str
    except Exception:
        return None

def sanitize_gender(val):
    if not val:
        return "Male"
    v = str(val).strip().lower()
    if "fem" in v or "ស្រី" in v or v == "female":
        return "Female"
    return "Male"

def sanitize_status(val):
    if not val:
        return "Active"
    v = str(val).strip().lower()
    if "inact" in v or "អសកម្ម" in v or v == "inactive":
        return "Inactive"
    return "Active"

# 1. Get all teachers & Add teacher aliases
@teachers_bp.route("/api/teachers", methods=["GET", "POST"])
@teachers_bp.route("/api/teacher", methods=["GET", "POST"])
@teachers_bp.route("/api/addteacher", methods=["GET", "POST"])
@teachers_bp.route("/api/add_teacher", methods=["GET", "POST"])
@teachers_bp.route("/api/teachers/add", methods=["GET", "POST"])
def teachers_route_handler():
    if request.method == 'GET':
        return get_teachers()
    return addteacher()

def get_teachers():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM teachers ORDER BY teacher_id DESC")
        teachers = cursor.fetchall()
        cursor.close()
        conn.close()

        # Convert date objects to string for JSON serialization
        for t in teachers:
            if t.get('date_of_birth'):
                t['date_of_birth'] = str(t['date_of_birth'])
            else:
                t['date_of_birth'] = ""

        return jsonify({
            "status": "success",
            "teachers": teachers
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 2. Add new teacher logic
def addteacher():
    data = request.get_json(silent=True) or request.form

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    teacher_code = (data.get("teacher_code") or data.get("code") or "").strip()
    full_name = (data.get("full_name") or data.get("name") or data.get("username") or "").strip()
    gender = sanitize_gender(data.get("gender"))
    date_of_birth = sanitize_date(data.get("date_of_birth") or data.get("dob"))
    status = sanitize_status(data.get("status"))
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    specialty = (data.get("specialty") or data.get("subject") or "").strip()
    address = (data.get("address") or "").strip()
    raw_role = (data.get("role") or "Teacher").strip()
    role = "Admin" if raw_role.lower() == "admin" else "Teacher"

    if not full_name:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះគ្រូបង្រៀន (Full Name is required)"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        # Ensure teacher_code is unique
        if teacher_code:
            cursor.execute("SELECT teacher_id FROM teachers WHERE teacher_code = %s", (teacher_code,))
            if cursor.fetchone():
                teacher_code = ""

        if not teacher_code:
            cursor.execute("SELECT MAX(teacher_id) AS max_id FROM teachers")
            row = cursor.fetchone()
            next_num = (row['max_id'] or 0) + 1
            teacher_code = f"TCH-2026-{next_num:03d}"
            
            # Double check uniqueness
            cursor.execute("SELECT teacher_id FROM teachers WHERE teacher_code = %s", (teacher_code,))
            if cursor.fetchone():
                import time
                teacher_code = f"TCH-2026-{int(time.time()) % 10000:04d}"

        cursor.execute(
            """INSERT INTO teachers 
               (teacher_code, full_name, gender, date_of_birth, status, phone, email, specialty, address, role) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (teacher_code, full_name, gender, date_of_birth, status, phone, email, specialty, address, role)
        )
        conn.commit()
        new_id = cursor.lastrowid

        # Auto-create or sync user account in users table
        try:
            cursor.execute("SELECT id FROM users WHERE username = %s", (full_name,))
            existing_user = cursor.fetchone()
            if not existing_user:
                from werkzeug.security import generate_password_hash
                default_pwd = phone if phone else "123456"
                cursor.execute(
                    "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                    (full_name, generate_password_hash(default_pwd), role)
                )
                conn.commit()
            else:
                cursor.execute("UPDATE users SET role = %s WHERE id = %s", (role, existing_user['id']))
                conn.commit()
        except Exception:
            pass

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានបញ្ចូលទិន្នន័យគ្រូបង្រៀនដោយជោគជ័យ",
            "teacher_id": new_id,
            "teacher": {
                "teacher_id": new_id,
                "teacher_code": teacher_code,
                "full_name": full_name,
                "gender": gender,
                "date_of_birth": str(date_of_birth) if date_of_birth else "",
                "status": status,
                "phone": phone,
                "email": email,
                "specialty": specialty,
                "address": address,
                "role": role
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

# 3. Delete teacher
@teachers_bp.route("/api/deleteteacher/<int:teacher_id>", methods=["DELETE", "POST"])
@teachers_bp.route("/api/deleteteacher", methods=["DELETE", "POST"])
def delete_teacher(teacher_id=None):
    if teacher_id is None:
        data = request.get_json(silent=True) or request.form
        teacher_id = data.get("teacher_id") if data else None

    if not teacher_id:
        return jsonify({"status": "error", "message": "Teacher ID is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("DELETE FROM teachers WHERE teacher_id = %s", (teacher_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()

        if affected == 0:
            return jsonify({"status": "error", "message": "Teacher not found"}), 404

        return jsonify({
            "status": "success",
            "message": "បានលុបទិន្នន័យគ្រូបង្រៀនដោយជោគជ័យ",
            "teacher_id": teacher_id
        })
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500

# 4. Edit/Update teacher
@teachers_bp.route("/api/editteacher/<int:teacher_id>", methods=["PUT", "POST"])
@teachers_bp.route("/api/editteacher", methods=["PUT", "POST"])
def edit_teacher(teacher_id=None):
    data = request.get_json(silent=True) or request.form
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    if teacher_id is None:
        teacher_id = data.get("teacher_id")

    if not teacher_id:
        return jsonify({"status": "error", "message": "Teacher ID is required"}), 400

    teacher_code = (data.get("teacher_code") or "").strip()
    full_name = (data.get("full_name") or "").strip()
    gender = sanitize_gender(data.get("gender"))
    date_of_birth = sanitize_date(data.get("date_of_birth"))
    status = sanitize_status(data.get("status"))
    phone = (data.get("phone") or "").strip()
    email = (data.get("email") or "").strip()
    specialty = (data.get("specialty") or "").strip()
    address = (data.get("address") or "").strip()
    raw_role = (data.get("role") or "Teacher").strip()
    role = "Admin" if raw_role.lower() == "admin" else "Teacher"

    if not full_name:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះគ្រូបង្រៀន (Full Name is required)"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            """UPDATE teachers 
               SET teacher_code = %s, full_name = %s, gender = %s, date_of_birth = %s, 
                   status = %s, phone = %s, email = %s, specialty = %s, address = %s, role = %s 
               WHERE teacher_id = %s""",
            (teacher_code, full_name, gender, date_of_birth, status, phone, email, specialty, address, role, teacher_id)
        )
        conn.commit()

        # Update role in users table if matching username or teacher_code
        try:
            cursor.execute(
                "UPDATE users SET role = %s WHERE username = %s OR username = %s",
                (role, full_name, teacher_code)
            )
            conn.commit()
        except Exception:
            pass

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានកែប្រែព័ត៌មានគ្រូបង្រៀនដោយជោគជ័យ",
            "teacher": {
                "teacher_id": teacher_id,
                "teacher_code": teacher_code,
                "full_name": full_name,
                "gender": gender,
                "date_of_birth": str(date_of_birth) if date_of_birth else "",
                "status": status,
                "phone": phone,
                "email": email,
                "specialty": specialty,
                "address": address,
                "role": role
            }
        })
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500
