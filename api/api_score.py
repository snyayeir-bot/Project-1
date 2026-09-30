from flask import Blueprint, request, jsonify
from db import get_db_connection
import json

score_bp = Blueprint('score_bp', __name__)

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

# Helper to extract all active subjects and calculate total max points from subjects table
def get_db_subjects_and_total_max():
    conn = get_db_connection()
    if not conn:
        return [], 0
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM subjects ORDER BY subject_id ASC")
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        extracted = []
        total_max = 0

        for r in rows:
            s_id = r.get("subject_id")
            val = r.get("subject_name")
            if not val:
                continue

            # Try parsing as JSON array
            try:
                parsed = json.loads(val)
                if isinstance(parsed, list):
                    for idx, item in enumerate(parsed):
                        if isinstance(item, dict):
                            max_val = int(item.get("max") or 100)
                            extracted.append({
                                "subject_id": s_id,
                                "subject_code": item.get("id") or f"subj-{s_id}-{idx+1}",
                                "subject_name": item.get("name") or f"Subject {idx+1}",
                                "max_score": max_val,
                                "checked": item.get("checked", True)
                            })
                            total_max += max_val
                        else:
                            extracted.append({
                                "subject_id": s_id,
                                "subject_code": f"subj-{s_id}-{idx+1}",
                                "subject_name": str(item),
                                "max_score": 100,
                                "checked": True
                            })
                            total_max += 100
                elif isinstance(parsed, dict):
                    max_val = int(parsed.get("max") or 100)
                    extracted.append({
                        "subject_id": s_id,
                        "subject_code": parsed.get("id") or f"subj-{s_id}",
                        "subject_name": parsed.get("name") or str(parsed),
                        "max_score": max_val,
                        "checked": parsed.get("checked", True)
                    })
                    total_max += max_val
                else:
                    extracted.append({
                        "subject_id": s_id,
                        "subject_code": f"subj-{s_id}",
                        "subject_name": str(parsed),
                        "max_score": 100,
                        "checked": True
                    })
                    total_max += 100
            except Exception:
                # Plain text name
                extracted.append({
                    "subject_id": s_id,
                    "subject_code": f"subj-{s_id}",
                    "subject_name": str(val).strip(),
                    "max_score": 100,
                    "checked": True
                })
                total_max += 100

        if total_max == 0:
            total_max = len(extracted) * 100 if extracted else 100

        return extracted, total_max
    except Exception as e:
        print("Error fetching subjects from DB:", e)
        return [], 0


# ----------------------------------------------------
# 1. GET SUBJECTS & TOTAL MAX POINTS (From Database)
# ----------------------------------------------------
@score_bp.route("/api/scores/subjects", methods=["GET"])
@score_bp.route("/api/score_subjects", methods=["GET"])
def get_score_subjects():
    subjects, total_max = get_db_subjects_and_total_max()
    return jsonify({
        "status": "success",
        "subjects": subjects,
        "total_max_points": total_max,
        "total_subjects": len(subjects)
    })


# ----------------------------------------------------
# 2. INSERT / SAVE STUDENT SCORES AS ARRAY IN DB
# ----------------------------------------------------
@score_bp.route("/api/scores", methods=["POST"])
@score_bp.route("/api/addscore", methods=["POST"])
@score_bp.route("/api/addscores", methods=["POST"])
def add_score():
    data = get_request_data()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    student_id = data.get("student_id")
    student_code = data.get("student_code") or data.get("id")
    exam_id = data.get("exam_id")
    class_id = data.get("class_id")
    scores_input = data.get("scores") or data.get("score_list") or data.get("subject_scores")

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        # 0. Enforce Active Academic Year Check
        cursor.execute("SELECT academic_year_id, academic_year FROM academic_years WHERE status = 'Active' LIMIT 1")
        active_yr = cursor.fetchone()
        if not active_yr:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "code": "ACADEMIC_YEAR_LOCKED",
                "message": "មិនអាចបញ្ចូល ឬកែប្រែពិន្ទុបានឡើយ ដោយសារបច្ចុប្បន្នមិនទាន់មានឆ្នាំសិក្សាសកម្មដែលបានបើកដំណើរការ (No Active Academic Year)!"
            }), 403

        # 1. Resolve student_id if student_code or name provided
        resolved_student_id = None
        if student_id:
            cursor.execute("SELECT student_id, student_code, full_name, gender FROM students WHERE student_id = %s", (student_id,))
            st = cursor.fetchone()
            if st:
                resolved_student_id = st["student_id"]

        if not resolved_student_id and student_code:
            cursor.execute("SELECT student_id, student_code, full_name, gender FROM students WHERE student_code = %s OR full_name = %s LIMIT 1", (student_code, student_code))
            st = cursor.fetchone()
            if st:
                resolved_student_id = st["student_id"]

        if not resolved_student_id:
            cursor.execute("SELECT student_id FROM students ORDER BY student_id ASC LIMIT 1")
            st = cursor.fetchone()
            if st:
                resolved_student_id = st["student_id"]
            else:
                cursor.close()
                conn.close()
                return jsonify({"status": "error", "message": "សូមជ្រើសរើសសិស្ស (Student is required)"}), 400

        student_id = resolved_student_id

        # If class_id is provided, ensure student is linked to class in student_classes
        if class_id:
            try:
                cursor.execute("SELECT * FROM student_classes WHERE student_id = %s AND class_id = %s", (student_id, class_id))
                if not cursor.fetchone():
                    cursor.execute("INSERT INTO student_classes (student_id, class_id) VALUES (%s, %s)", (student_id, class_id))
                    conn.commit()
            except Exception:
                pass

        # 2. Resolve exam_id safely against database
        valid_exam_id = None
        if exam_id:
            cursor.execute("SELECT exam_id FROM examinations WHERE exam_id = %s", (exam_id,))
            ex = cursor.fetchone()
            if ex:
                valid_exam_id = ex["exam_id"]

        if not valid_exam_id:
            cursor.execute("SELECT exam_id FROM examinations ORDER BY exam_id DESC LIMIT 1")
            ex = cursor.fetchone()
            if ex:
                valid_exam_id = ex["exam_id"]
            else:
                cursor.execute("INSERT INTO examinations (exam_name, week) VALUES ('ប្រឡងប្រចាំខែ', '2026-03')")
                conn.commit()
                valid_exam_id = cursor.lastrowid

        exam_id = valid_exam_id

        # 3. Resolve default subject_id (bundle ID) safely against database
        cursor.execute("SELECT subject_id FROM subjects ORDER BY subject_id ASC LIMIT 1")
        default_subj = cursor.fetchone()
        if default_subj:
            default_subject_id = default_subj["subject_id"]
        else:
            cursor.execute("INSERT INTO subjects (subject_name) VALUES ('មុខវិជ្ជាទូទៅ')")
            conn.commit()
            default_subject_id = cursor.lastrowid

        # 4. Standardize scores as Array of subject score objects
        db_subjs, total_max_points = get_db_subjects_and_total_max()
        scores_array = []
        total_score = 0
        total_possible = 0

        if isinstance(scores_input, list):
            for item in scores_input:
                if isinstance(item, dict):
                    name = item.get("subject_name") or item.get("name") or "Subject"
                    score_val = float(item.get("score") or 0)
                    max_val = float(item.get("max") or item.get("max_score") or 100)
                    s_id = default_subject_id
                    scores_array.append({
                        "subject_id": s_id,
                        "subject_name": name,
                        "score": score_val,
                        "max": max_val
                    })
                    total_score += score_val
                    total_possible += max_val
                else:
                    score_val = float(item or 0)
                    scores_array.append({
                        "subject_id": default_subject_id,
                        "subject_name": "Subject",
                        "score": score_val,
                        "max": 100
                    })
                    total_score += score_val
                    total_possible += 100

        elif isinstance(scores_input, dict):
            for k, val in scores_input.items():
                matched_subj = next((s for s in db_subjs if s["subject_code"].lower() == k.lower() or s["subject_name"].lower() == k.lower()), None)
                s_name = matched_subj["subject_name"] if matched_subj else k
                s_max = matched_subj["max_score"] if matched_subj else 100
                s_id = default_subject_id
                score_val = float(val or 0)

                scores_array.append({
                    "subject_id": s_id,
                    "subject_name": s_name,
                    "score": score_val,
                    "max": s_max
                })
                total_score += score_val
                total_possible += s_max
        else:
            score_val = float(data.get("score") or 0)
            scores_array = [{"subject_id": default_subject_id, "subject_name": "Total", "score": score_val, "max": total_max_points}]
            total_score = score_val
            total_possible = total_max_points

        if total_possible == 0:
            total_possible = total_max_points or 100

        # Encode Array as JSON string to store in `score` column
        scores_json_str = json.dumps(scores_array, ensure_ascii=False)

        # 5. Save or Update in database `scores` table
        cursor.execute(
            "SELECT score_id FROM scores WHERE student_id = %s AND exam_id = %s",
            (student_id, exam_id)
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                "UPDATE scores SET score = %s, subject_id = %s WHERE score_id = %s",
                (scores_json_str, default_subject_id, existing["score_id"])
            )
            target_score_id = existing["score_id"]
        else:
            cursor.execute(
                "INSERT INTO scores (student_id, subject_id, exam_id, score) VALUES (%s, %s, %s, %s)",
                (student_id, default_subject_id, exam_id, scores_json_str)
            )
            target_score_id = cursor.lastrowid

        conn.commit()
        cursor.close()
        conn.close()

        avg_pct = round((total_score / total_possible) * 100, 1)
        gpa = "Grade A+" if avg_pct >= 90 else "Grade A" if avg_pct >= 80 else "Grade B" if avg_pct >= 70 else "Grade C" if avg_pct >= 60 else "Grade D" if avg_pct >= 50 else "Grade F"
        result = "pass" if avg_pct >= 50 else "fail"

        return jsonify({
            "status": "success",
            "message": "បានបញ្ចូល និងរក្សាទុកពិន្ទុក្នុង Database ជោគជ័យ!",
            "score_record": {
                "score_id": target_score_id,
                "student_id": student_id,
                "exam_id": exam_id,
                "class_id": class_id,
                "scores": scores_array,
                "total_score": total_score,
                "total_max_points": total_possible,
                "average_pct": f"{avg_pct}%",
                "gpa": gpa,
                "result": result
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
# 2.1 BATCH SAVE SCORES FOR CLASS STUDENTS
# ----------------------------------------------------
@score_bp.route("/api/scores/batch", methods=["POST"])
@score_bp.route("/api/batch_add_scores", methods=["POST"])
def batch_add_scores():
    data = get_request_data()
    if not data:
        return jsonify({"status": "error", "message": "No data provided"}), 400

    exam_id = data.get("exam_id")
    class_id = data.get("class_id")
    student_scores = data.get("student_scores") or data.get("scores") or []

    if not isinstance(student_scores, list) or len(student_scores) == 0:
        return jsonify({"status": "error", "message": "No student scores array provided"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)

        # 0. Enforce Active Academic Year Check
        cursor.execute("SELECT academic_year_id, academic_year FROM academic_years WHERE status = 'Active' LIMIT 1")
        active_yr = cursor.fetchone()
        if not active_yr:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "code": "ACADEMIC_YEAR_LOCKED",
                "message": "មិនអាចបញ្ចូល ឬកែប្រែពិន្ទុបានឡើយ ដោយសារបច្ចុប្បន្នមិនទាន់មានឆ្នាំសិក្សាសកម្មដែលបានបើកដំណើរការ (No Active Academic Year)!"
            }), 403

        # Resolve exam_id safely
        valid_exam_id = None
        if exam_id:
            cursor.execute("SELECT exam_id FROM examinations WHERE exam_id = %s", (exam_id,))
            ex = cursor.fetchone()
            if ex:
                valid_exam_id = ex["exam_id"]

        if not valid_exam_id:
            cursor.execute("SELECT exam_id FROM examinations ORDER BY exam_id DESC LIMIT 1")
            ex = cursor.fetchone()
            if ex:
                valid_exam_id = ex["exam_id"]
            else:
                cursor.execute("INSERT INTO examinations (exam_name, week) VALUES ('ប្រឡងប្រចាំខែ', '2026-03')")
                conn.commit()
                valid_exam_id = cursor.lastrowid

        exam_id = valid_exam_id

        cursor.execute("SELECT subject_id FROM subjects ORDER BY subject_id ASC LIMIT 1")
        default_subj = cursor.fetchone()
        if default_subj:
            default_subject_id = default_subj["subject_id"]
        else:
            cursor.execute("INSERT INTO subjects (subject_name) VALUES ('មុខវិជ្ជាទូទៅ')")
            conn.commit()
            default_subject_id = cursor.lastrowid

        db_subjs, total_max_points = get_db_subjects_and_total_max()
        saved_count = 0

        for row in student_scores:
            s_id = row.get("student_id")
            s_code = row.get("student_code") or row.get("id")
            scores_input = row.get("scores") or row.get("score_list") or row.get("subject_scores")

            if s_id:
                cursor.execute("SELECT student_id FROM students WHERE student_id = %s", (s_id,))
                if not cursor.fetchone():
                    s_id = None

            if not s_id and s_code:
                cursor.execute("SELECT student_id FROM students WHERE student_code = %s OR full_name = %s LIMIT 1", (s_code, s_code))
                st = cursor.fetchone()
                if st:
                    s_id = st["student_id"]

            if not s_id:
                continue

            scores_array = []
            if isinstance(scores_input, list):
                for item in scores_input:
                    if isinstance(item, dict):
                        scores_array.append({
                            "subject_id": default_subject_id,
                            "subject_name": item.get("subject_name") or item.get("name") or "Subject",
                            "score": float(item.get("score") or 0),
                            "max": float(item.get("max") or item.get("max_score") or 100)
                        })
            elif isinstance(scores_input, dict):
                for k, val in scores_input.items():
                    matched_subj = next((s for s in db_subjs if s["subject_code"].lower() == k.lower() or s["subject_name"].lower() == k.lower()), None)
                    scores_array.append({
                        "subject_id": default_subject_id,
                        "subject_name": matched_subj["subject_name"] if matched_subj else k,
                        "score": float(val or 0),
                        "max": matched_subj["max_score"] if matched_subj else 100
                    })

            scores_json_str = json.dumps(scores_array, ensure_ascii=False)

            cursor.execute("SELECT score_id FROM scores WHERE student_id = %s AND exam_id = %s", (s_id, exam_id))
            existing = cursor.fetchone()
            if existing:
                cursor.execute("UPDATE scores SET score = %s, subject_id = %s WHERE score_id = %s", (scores_json_str, default_subject_id, existing["score_id"]))
            else:
                cursor.execute("INSERT INTO scores (student_id, subject_id, exam_id, score) VALUES (%s, %s, %s, %s)", (s_id, default_subject_id, exam_id, scores_json_str))
            
            saved_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានបញ្ចូលពិន្ទុសម្រាប់សិស្ស {saved_count} នាក់ក្នុងថ្នាក់ដោយជោគជ័យ!",
            "saved_count": saved_count,
            "exam_id": exam_id,
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
# 3. GET ALL SCORES (Filtered by Exam & Class)
# ----------------------------------------------------
@score_bp.route("/api/scores", methods=["GET"])
def get_scores():
    exam_id = request.args.get("exam_id")
    student_id = request.args.get("student_id")
    class_id = request.args.get("class_id")

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        query = """
            SELECT 
                sc.score_id,
                sc.student_id,
                st.student_code,
                st.full_name as student_name,
                st.gender,
                sc.subject_id,
                sc.exam_id,
                ex.exam_name,
                ex.week,
                sc.score,
                scl.class_id,
                c.class_name,
                c.grade
            FROM scores sc
            LEFT JOIN students st ON sc.student_id = st.student_id
            LEFT JOIN examinations ex ON sc.exam_id = ex.exam_id
            LEFT JOIN student_classes scl ON st.student_id = scl.student_id
            LEFT JOIN classes c ON scl.class_id = c.class_id
            WHERE 1=1
        """
        params = []
        academic_year_id = request.args.get("academic_year_id")
        include_all = request.args.get("include_all") == "1" or request.args.get("all") == "1"

        if academic_year_id:
            query += " AND ex.academic_year_id = %s"
            params.append(academic_year_id)
        elif not include_all and not exam_id:
            # Default for active gradebook: only load scores from active academic year examinations
            query += " AND (ex.academic_year_id = (SELECT academic_year_id FROM academic_years WHERE status = 'Active' LIMIT 1) OR ex.academic_year_id IS NULL OR ex.exam_id IS NULL)"
        if exam_id:
            query += " AND sc.exam_id = %s"
            params.append(exam_id)
        if student_id:
            query += " AND sc.student_id = %s"
            params.append(student_id)
        if class_id:
            query += " AND scl.class_id = %s"
            params.append(class_id)

        query += " ORDER BY sc.score_id DESC"

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        cursor.close()
        conn.close()

        _, default_total_max = get_db_subjects_and_total_max()

        result = []
        for r in rows:
            raw_score = r.get("score")
            scores_array = []
            tot_score = 0
            tot_max = 0

            # Try parsing JSON array
            if raw_score:
                try:
                    parsed = json.loads(raw_score)
                    if isinstance(parsed, list):
                        scores_array = parsed
                        for item in parsed:
                            tot_score += float(item.get("score") or 0)
                            tot_max += float(item.get("max") or 100)
                    elif isinstance(parsed, dict):
                        for k, v in parsed.items():
                            val = float(v or 0)
                            scores_array.append({"subject_name": k, "score": val, "max": 100})
                            tot_score += val
                            tot_max += 100
                    else:
                        val = float(parsed or 0)
                        scores_array = [{"subject_name": "Total", "score": val, "max": default_total_max}]
                        tot_score = val
                        tot_max = default_total_max
                except Exception:
                    try:
                        val = float(raw_score)
                        scores_array = [{"subject_name": "Total", "score": val, "max": default_total_max}]
                        tot_score = val
                        tot_max = default_total_max
                    except Exception:
                        scores_array = []

            if tot_max == 0:
                tot_max = default_total_max or 100

            avg_pct = round((tot_score / tot_max) * 100, 1) if tot_max > 0 else 0
            gpa = "Grade A+" if avg_pct >= 90 else "Grade A" if avg_pct >= 80 else "Grade B" if avg_pct >= 70 else "Grade C" if avg_pct >= 60 else "Grade D" if avg_pct >= 50 else "Grade F"
            res_str = "pass" if avg_pct >= 50 else "fail"

            result.append({
                "score_id": r.get("score_id"),
                "student_id": r.get("student_id"),
                "student_code": r.get("student_code"),
                "student_name": r.get("student_name"),
                "gender": r.get("gender"),
                "class_id": r.get("class_id"),
                "class_name": r.get("class_name"),
                "grade": r.get("grade"),
                "exam_id": r.get("exam_id"),
                "exam_name": r.get("exam_name"),
                "week": r.get("week"),
                "scores": scores_array,
                "total_score": tot_score,
                "total_max_points": tot_max,
                "average_pct": f"{avg_pct}%",
                "gpa": gpa,
                "result": res_str
            })

        return jsonify({
            "status": "success",
            "scores": result,
            "total_max_points": default_total_max,
            "total": len(result)
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 4. DELETE SCORE BY ID
# ----------------------------------------------------
@score_bp.route("/api/scores/<int:score_id>", methods=["DELETE", "POST"])
@score_bp.route("/api/deletescore/<int:score_id>", methods=["DELETE", "POST"])
def delete_score(score_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("DELETE FROM scores WHERE score_id = %s", (score_id,))
        conn.commit()
        affected = cursor.rowcount
        cursor.close()
        conn.close()

        if affected == 0:
            return jsonify({"status": "error", "message": "រកមិនឃើញពិន្ទុនេះទេ"}), 404

        return jsonify({
            "status": "success",
            "message": "បានលុបពិន្ទុជោគជ័យ!",
            "score_id": score_id
        })
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500
