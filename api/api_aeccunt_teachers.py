from flask import Blueprint, request, jsonify
from db import get_db_connection
from api.api_login import extract_token_from_request, verify_token

aeccunt_bp = Blueprint("aeccunt_bp", __name__)

@aeccunt_bp.route("/api/aeccunt_teachers", methods=["POST", "GET"])
@aeccunt_bp.route("/api/aeccunt", methods=["POST", "GET"])
@aeccunt_bp.route("/api/teacher/my_class", methods=["POST", "GET"])
@aeccunt_bp.route("/api/teacher_class", methods=["POST", "GET"])
@aeccunt_bp.route("/api/my_class", methods=["POST", "GET"])
def aeccunt_teachers():
    # 1. Extract search parameters from JSON, Form, Query String, or Token
    teachers_name = ""
    teacher_id = None
    data = {}

    if request.is_json:
        data = request.get_json(silent=True) or {}
    elif request.form:
        data = request.form.to_dict()

    if isinstance(data, dict):
        teachers_name = data.get("name") or data.get("username") or data.get("full_name") or data.get("teacher_code") or ""
        teacher_id = data.get("teacher_id") or data.get("id")
        # If payload nested under "data"
        if not teachers_name and isinstance(data.get("data"), dict):
            nested = data.get("data")
            teachers_name = nested.get("name") or nested.get("username") or nested.get("full_name") or ""
            teacher_id = nested.get("teacher_id") or nested.get("id")
            if not teachers_name and isinstance(nested.get("user"), dict):
                teachers_name = nested.get("user", {}).get("username") or nested.get("user", {}).get("name") or ""

    if not teachers_name:
        teachers_name = request.args.get("name") or request.args.get("username") or request.args.get("full_name") or request.args.get("teacher_code") or ""
    if not teacher_id:
        teacher_id = request.args.get("teacher_id") or request.args.get("id")

    # Fallback to token if name still empty
    if not teachers_name and not teacher_id:
        token = extract_token_from_request()
        if token:
            payload, _ = verify_token(token)
            if payload:
                teachers_name = payload.get("username") or payload.get("full_name") or payload.get("name") or ""
                teacher_id = payload.get("teacher_id")

    try:
        # Safe logging without console encoding crash
        pass
    except Exception:
        pass

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        base_query = """
            SELECT 
                t.*,
                tc.teacher_class_id,
                c.class_id,
                c.class_name,
                c.grade,
                c.room,
                c.academic_year_id,
                (SELECT COUNT(*) FROM student_classes sc WHERE sc.class_id = c.class_id AND (sc.academic_year_id = c.academic_year_id OR sc.academic_year_id IS NULL)) AS student_count
            FROM teachers t
            LEFT JOIN teacher_classes tc ON t.teacher_id = tc.teacher_id
            LEFT JOIN classes c ON tc.class_id = c.class_id AND (c.academic_year_id = (SELECT academic_year_id FROM academic_years WHERE status = 'Active' ORDER BY academic_year_id DESC LIMIT 1) OR c.academic_year_id IS NULL)
        """

        teachers = []

        if teacher_id:
            query = base_query + " WHERE t.teacher_id = %s ORDER BY (c.class_id IS NOT NULL) DESC, c.class_id DESC LIMIT 1"
            cursor.execute(query, (teacher_id,))
            teachers = cursor.fetchall()

        if not teachers and teachers_name:
            query = base_query + """
                WHERE t.full_name = %s 
                   OR t.full_name LIKE %s 
                   OR t.teacher_code = %s 
                   OR t.email = %s
                   OR t.phone = %s
                ORDER BY (c.class_id IS NOT NULL) DESC, c.class_id DESC
                LIMIT 10
            """
            cursor.execute(query, (teachers_name, f"%{teachers_name}%", teachers_name, teachers_name, teachers_name))
            teachers = cursor.fetchall()
            
            # If nothing matched and we have teachers in DB, try selecting first or all
            if not teachers:
                cursor.execute(base_query + " ORDER BY (c.class_id IS NOT NULL) DESC, t.teacher_id ASC LIMIT 1")
                teachers = cursor.fetchall()
        elif not teachers:
            # If no parameter specified, return first or all teachers with classes
            cursor.execute(base_query + " ORDER BY (c.class_id IS NOT NULL) DESC, t.teacher_id ASC LIMIT 10")
            teachers = cursor.fetchall()

        cursor.close()
        conn.close()

        # Format date for JSON
        for t in teachers:
            if t.get('date_of_birth'):
                t['date_of_birth'] = str(t['date_of_birth'])
            else:
                t['date_of_birth'] = ""

        teacher_profile = teachers[0] if teachers else None

        homeroom_class = None
        if teacher_profile and teacher_profile.get('class_id'):
            homeroom_class = {
                'teacher_id': teacher_profile.get('teacher_id'),
                'teacher_name': teacher_profile.get('full_name'),
                'teacher_code': teacher_profile.get('teacher_code'),
                'class_id': teacher_profile.get('class_id'),
                'class_name': teacher_profile.get('class_name'),
                'grade': teacher_profile.get('grade'),
                'room': teacher_profile.get('room'),
                'student_count': teacher_profile.get('student_count', 0),
                'display_name': f"{teacher_profile.get('class_name')} ({teacher_profile.get('grade')}{(' - ' + teacher_profile.get('room')) if teacher_profile.get('room') else ''})"
            }

        return jsonify({
            "status": "success",
            "message": "Teacher account data and assigned class retrieved successfully",
            "teacher": teacher_profile,
            "teachers": teachers,
            "homeroom_class": homeroom_class,
            "class_id": teacher_profile.get('class_id') if teacher_profile else None,
            "class_name": teacher_profile.get('class_name') if teacher_profile else None,
            "searched_name": teachers_name
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500


@aeccunt_bp.route("/api/get_all_student_teachers", methods=["POST", "GET"])
# get all data from database
def get_all_student_teachers():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM teachers ORDER BY teacher_id DESC")
        teachers = cursor.fetchall()
        cursor.close()
        conn.close()

        for t in teachers:
            if t.get('date_of_birth'):
                t['date_of_birth'] = str(t['date_of_birth'])

        return jsonify({"status": "success", "message": "Teacher data retrieved successfully", "data": teachers}), 200
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error querying teachers: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500