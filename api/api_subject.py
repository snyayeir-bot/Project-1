from flask import Blueprint, request, jsonify
from db import get_db_connection
import json

subject_bp = Blueprint('subject_bp', __name__)

# Helper to parse subject_name into array if JSON
def parse_subject_name(val):
    if not val:
        return []
    if isinstance(val, (list, dict)):
        return val
    try:
        parsed = json.loads(val)
        return parsed
    except Exception:
        # If plain text string, wrap as single subject item
        return [{"id": "subj-1", "name": str(val).strip(), "max": 100, "checked": True}]

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
    return None

# 1. Get all subject bundles / subjects (subject_name parsed as Array)
@subject_bp.route("/api/subjects", methods=["GET"])
@subject_bp.route("/api/subject", methods=["GET"])
def get_subjects():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM subjects ORDER BY subject_id ASC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Parse subject_name to JSON array for each row
        result = []
        for r in rows:
            parsed_array = parse_subject_name(r.get("subject_name"))
            result.append({
                "subject_id": r.get("subject_id"),
                "subject_name": parsed_array,
                "credit": r.get("credit", 1)
            })

        return jsonify({
            "status": "success",
            "subjects": result,
            "total": len(result)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Endpoint to get specific or latest subjects array directly
@subject_bp.route("/api/subjects/get_bundle", methods=["GET"])
def get_bundle():
    bundle_id = request.args.get("subject_id") or request.args.get("id")
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        if bundle_id:
            cursor.execute("SELECT * FROM subjects WHERE subject_id = %s", (bundle_id,))
        else:
            cursor.execute("SELECT * FROM subjects ORDER BY subject_id DESC LIMIT 1")
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({"status": "error", "message": "No subjects found", "subjects": []}), 404

        parsed_array = parse_subject_name(row.get("subject_name"))
        return jsonify({
            "status": "success",
            "subject_id": row.get("subject_id"),
            "subjects": parsed_array,
            "credit": row.get("credit", len(parsed_array))
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500



# 2. Save/Insert Subject Array into subject_name in Database
@subject_bp.route("/api/subjects", methods=["POST"])
@subject_bp.route("/api/addsubject", methods=["POST"])
@subject_bp.route("/api/subjects/save_bundle", methods=["POST"])
def add_subject():
    data = get_request_data()

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    # Support receiving direct list, or field subject_name as list/string
    if isinstance(data, list):
        subjects_array = data
        credit = len(data)
    else:
        raw_subj = data.get("subject_name") or data.get("subjects") or data.get("name")
        if isinstance(raw_subj, list):
            subjects_array = raw_subj
        elif isinstance(raw_subj, str):
            try:
                subjects_array = json.loads(raw_subj)
            except Exception:
                subjects_array = [{"id": "subj-1", "name": raw_subj.strip(), "max": int(data.get("max") or 100), "checked": True}]
        else:
            subjects_array = []
        credit = int(data.get("credit") or len(subjects_array) or 1)

    if not subjects_array:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលមុខវិជ្ជា (Subjects array cannot be empty)"}), 400

    # If subject_id provided in body, update instead of insert
    subject_id = data.get("subject_id") if isinstance(data, dict) else None

    # Encode array as JSON string to store in subject_name column
    subject_json_str = json.dumps(subjects_array, ensure_ascii=False)

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        if subject_id:
            cursor.execute(
                "UPDATE subjects SET subject_name = %s, credit = %s WHERE subject_id = %s",
                (subject_json_str, credit, subject_id)
            )
            conn.commit()
            target_id = subject_id
        else:
            cursor.execute(
                "INSERT INTO subjects (subject_name, credit) VALUES (%s, %s)",
                (subject_json_str, credit)
            )
            conn.commit()
            target_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានរក្សាទុកមុខវិជ្ជាជា Array ({len(subjects_array)} មុខវិជ្ជា) ក្នុង Database ជោគជ័យ!",
            "subject": {
                "subject_id": target_id,
                "subject_name": subjects_array,
                "credit": credit
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


# 3. Edit/Update Subject Array by subject_id
@subject_bp.route("/api/subjects/<int:subject_id>", methods=["PUT", "POST"])
@subject_bp.route("/api/editsubject/<int:subject_id>", methods=["PUT", "POST"])
@subject_bp.route("/api/editsubject", methods=["PUT", "POST"])
def edit_subject(subject_id=None):
    data = get_request_data()

    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    if subject_id is None and isinstance(data, dict):
        subject_id = data.get("subject_id")

    if not subject_id:
        return jsonify({"status": "error", "message": "Subject ID is required"}), 400

    # Extract subjects array
    if isinstance(data, list):
        subjects_array = data
        credit = len(data)
    else:
        raw_subj = data.get("subject_name") or data.get("subjects") or data.get("name")
        if isinstance(raw_subj, list):
            subjects_array = raw_subj
        elif isinstance(raw_subj, str):
            try:
                subjects_array = json.loads(raw_subj)
            except Exception:
                subjects_array = [{"id": "subj-1", "name": raw_subj.strip(), "max": int(data.get("max") or 100), "checked": True}]
        else:
            subjects_array = []
        credit = int(data.get("credit") or len(subjects_array) or 1)

    if not subjects_array:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលមុខវិជ្ជា (Subjects array cannot be empty)"}), 400

    subject_json_str = json.dumps(subjects_array, ensure_ascii=False)

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(
            "UPDATE subjects SET subject_name = %s, credit = %s WHERE subject_id = %s",
            (subject_json_str, credit, subject_id)
        )
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានកែប្រែទិន្នន័យមុខវិជ្ជាជា Array ជោគជ័យ!",
            "subject": {
                "subject_id": subject_id,
                "subject_name": subjects_array,
                "credit": credit
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


# 4. Delete subject by subject_id
@subject_bp.route("/api/subjects/<int:subject_id>", methods=["DELETE", "POST"])
@subject_bp.route("/api/deletesubject/<int:subject_id>", methods=["DELETE", "POST"])
@subject_bp.route("/api/deletesubject", methods=["DELETE", "POST"])
def delete_subject(subject_id=None):
    data = get_request_data()
    if subject_id is None and isinstance(data, dict):
        subject_id = data.get("subject_id")

    if not subject_id:
        return jsonify({"status": "error", "message": "Subject ID is required"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("DELETE FROM subjects WHERE subject_id = %s", (subject_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()

        if affected == 0:
            return jsonify({"status": "error", "message": "រកមិនឃើញទិន្នន័យនេះទេ"}), 404

        return jsonify({
            "status": "success",
            "message": "បានលុបទិន្នន័យជោគជ័យ!",
            "subject_id": subject_id
        })
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500

