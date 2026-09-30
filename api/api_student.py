from flask import Blueprint, request, jsonify
from db import get_db_connection
import datetime

student_bp = Blueprint('student_bp', __name__)

def sanitize_date(val):
    if not val or str(val).strip() == "" or str(val).strip() == "—" or str(val).strip() == "null" or str(val).strip() == "None":
        return None
    val_str = str(val).strip()
    try:
        # Validate format YYYY-MM-DD
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

# 1. Get all students
@student_bp.route("/api/students", methods=["GET"])
def get_students():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM students ORDER BY student_id DESC")
        students = cursor.fetchall()
        cursor.close()
        conn.close()

        # Convert date objects to string for JSON serialization
        for s in students:
            if s.get('date_of_birth'):
                s['date_of_birth'] = str(s['date_of_birth'])
            else:
                s['date_of_birth'] = ""

        return jsonify({
            "status": "success",
            "students": students,
            "count": len(students)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# 1.1 Search student by Name or Student ID/Code
@student_bp.route("/api/search_student", methods=["GET", "POST"])
@student_bp.route("/api/find_student", methods=["GET", "POST"])
def search_student():
    data = {}
    if request.is_json:
        data = request.get_json(silent=True) or {}
    elif request.form:
        data = request.form.to_dict()

    q = (data.get("q") or data.get("query") or data.get("name") or data.get("student_code") or data.get("code") or request.args.get("q") or request.args.get("query") or request.args.get("name") or request.args.get("code") or "").strip()

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        if q:
            query = """
                SELECT * FROM students 
                WHERE full_name = %s 
                   OR full_name LIKE %s 
                   OR student_code = %s 
                   OR student_code LIKE %s
                   OR phone = %s
                   OR student_id = %s
                ORDER BY student_id DESC
                LIMIT 15
            """
            cursor.execute(query, (q, f"%{q}%", q, f"%{q}%", q, q if q.isdigit() else 0))
            students = cursor.fetchall()
        else:
            cursor.execute("SELECT * FROM students ORDER BY student_id DESC LIMIT 15")
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
            "students": students,
            "student": students[0] if students else None,
            "count": len(students)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500

# 2. Add new student
@student_bp.route("/api/addstudent", methods=["GET", "POST"])
@student_bp.route("/api/students", methods=["POST"])
def add_student():
    if request.method == 'GET':
        return get_students()

    data = request.get_json(silent=True) or request.form

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    student_code = (data.get("student_code") or "").strip()
    full_name = (data.get("full_name") or "").strip()
    gender = sanitize_gender(data.get("gender"))
    date_of_birth = sanitize_date(data.get("date_of_birth"))
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    father_name = (data.get("father_name") or "").strip()
    father_phone = (data.get("father_phone") or "").strip()
    mother_name = (data.get("mother_name") or "").strip()
    mother_phone = (data.get("mother_phone") or "").strip()
    status = sanitize_status(data.get("status"))

    if not full_name:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះសិស្ស (Full Name is required)"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        
        # If student_code is empty, auto-generate one
        if not student_code:
            cursor.execute("SELECT MAX(student_id) AS max_id FROM students")
            row = cursor.fetchone()
            next_num = (row['max_id'] or 0) + 1
            student_code = f"STD-2026-{next_num:03d}"

        # Insert student record
        cursor.execute(
            """INSERT INTO students 
               (student_code, full_name, gender, date_of_birth, phone, address, father_name, father_phone, mother_name, mother_phone, status) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (student_code, full_name, gender, date_of_birth, phone, address, father_name, father_phone, mother_name, mother_phone, status)
        )
        conn.commit()
        new_id = cursor.lastrowid
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានបញ្ចូលទិន្នន័យសិស្សថ្មីដោយជោគជ័យ!",
            "student_id": new_id,
            "student": {
                "student_id": new_id,
                "student_code": student_code,
                "full_name": full_name,
                "gender": gender,
                "date_of_birth": str(date_of_birth) if date_of_birth else "",
                "phone": phone,
                "address": address,
                "father_name": father_name,
                "father_phone": father_phone,
                "mother_name": mother_name,
                "mother_phone": mother_phone,
                "status": status
            }
        })
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": f"បរាជ័យក្នុងការបញ្ចូលទិន្នន័យ: {str(e)}"}), 500

# 3. Edit/Update student
@student_bp.route("/api/editstudent/<int:student_id>", methods=["PUT", "POST"])
@student_bp.route("/api/editstudent", methods=["PUT", "POST"])
def edit_student(student_id=None):
    data = request.get_json(silent=True) or request.form
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    if student_id is None:
        student_id = data.get("student_id")

    if not student_id:
        return jsonify({"status": "error", "message": "Student ID is required"}), 400

    student_code = (data.get("student_code") or "").strip()
    full_name = (data.get("full_name") or "").strip()
    gender = sanitize_gender(data.get("gender"))
    date_of_birth = sanitize_date(data.get("date_of_birth"))
    phone = (data.get("phone") or "").strip()
    address = (data.get("address") or "").strip()
    father_name = (data.get("father_name") or "").strip()
    father_phone = (data.get("father_phone") or "").strip()
    mother_name = (data.get("mother_name") or "").strip()
    mother_phone = (data.get("mother_phone") or "").strip()
    status = sanitize_status(data.get("status"))

    if not full_name:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលឈ្មោះសិស្ស (Full Name is required)"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        # Fetch old student data for audit logging
        cursor.execute("SELECT * FROM students WHERE student_id = %s", (student_id,))
        old_student = cursor.fetchone() or {}

        cursor.execute(
            """UPDATE students 
               SET student_code = %s, full_name = %s, gender = %s, date_of_birth = %s, 
                   phone = %s, address = %s, father_name = %s, father_phone = %s, 
                   mother_name = %s, mother_phone = %s, status = %s 
               WHERE student_id = %s""",
            (student_code, full_name, gender, date_of_birth, phone, address, father_name, father_phone, mother_name, mother_phone, status, student_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

        # Audit Logging
        try:
            from api.api_logs import log_audit_event
            performed_by = (data.get("updated_by") or data.get("performed_by") or "លោក នាយកសាលា (Admin)").strip()
            old_name = old_student.get("full_name") or "—"
            old_code = old_student.get("student_code") or f"STD-{student_id}"
            
            old_parts = []
            new_parts = []
            if old_name != full_name:
                old_parts.append(f"ឈ្មោះ: {old_name}")
                new_parts.append(f"ឈ្មោះ: {full_name}")
            if (old_student.get("gender") or "Male") != gender:
                old_parts.append(f"ភេទ: {old_student.get('gender')}")
                new_parts.append(f"ភេទ: {gender}")
            if (old_student.get("phone") or "") != phone and phone:
                old_parts.append(f"ទូរស័ព្ទ: {old_student.get('phone') or 'គ្មាន'}")
                new_parts.append(f"ទូរស័ព្ទ: {phone}")

            old_val_str = ", ".join(old_parts) if old_parts else f"ឈ្មោះ: {old_name}"
            new_val_str = ", ".join(new_parts) if new_parts else f"ឈ្មោះ: {full_name}"

            log_audit_event(
                category="Student",
                performed_by=performed_by,
                role_badge="🏛️ នាយកសាលា / Admin",
                target_id=student_code or f"STD-{student_id}",
                target_name=f"សិស្ស: {full_name}",
                action_type="✏️ កែប្រែឈ្មោះ/ព័ត៌មានសិស្ស",
                old_val=old_val_str,
                new_val=new_val_str,
                details=f"បានកែប្រែព័ត៌មានសិស្ស {full_name} ({student_code})"
            )
        except Exception as log_err:
            print(f"[-] Log audit error: {log_err}")

        return jsonify({
            "status": "success",
            "message": "បានកែប្រែព័ត៌មានសិស្សដោយជោគជ័យ!",
            "student": {
                "student_id": student_id,
                "student_code": student_code,
                "full_name": full_name,
                "gender": gender,
                "date_of_birth": str(date_of_birth) if date_of_birth else "",
                "phone": phone,
                "address": address,
                "father_name": father_name,
                "father_phone": father_phone,
                "mother_name": mother_name,
                "mother_phone": mother_phone,
                "status": status
            }
        })
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": f"បរាជ័យក្នុងការកែប្រែទិន្នន័យ: {str(e)}"}), 500

# 4. Delete student
@student_bp.route("/api/deletestudent/<int:student_id>", methods=["DELETE", "POST"])
@student_bp.route("/api/deletestudent", methods=["DELETE", "POST"])
def delete_student(student_id=None):
    if student_id is None:
        data = request.get_json(silent=True) or request.form
        student_id = data.get("student_id") if data else None

    if not student_id:
        return jsonify({"status": "error", "message": "Student ID is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("DELETE FROM students WHERE student_id = %s", (student_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()

        if affected == 0:
            return jsonify({"status": "error", "message": "រកមិនឃើញសិស្សនេះទេ"}), 404

        return jsonify({
            "status": "success",
            "message": "បានលុបទិន្នន័យសិស្សដោយជោគជ័យ!",
            "student_id": student_id
        })
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": f"បរាជ័យក្នុងការលុបទិន្នន័យ: {str(e)}"}), 500
