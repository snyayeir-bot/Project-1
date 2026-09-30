import json
import os
from datetime import datetime, date
from flask import Blueprint, request, jsonify
from db import get_db_connection

logs_bp = Blueprint("logs", __name__)

def ensure_audit_logs_table(cursor):
    """Ensure the audit_logs table exists and has proper schema."""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INT AUTO_INCREMENT PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                category VARCHAR(50) DEFAULT 'Student',
                performed_by VARCHAR(100) DEFAULT 'លោក នាយកសាលា',
                role_badge VARCHAR(80) DEFAULT '🏛️ នាយកសាលា',
                target_id VARCHAR(100) NULL,
                target_name VARCHAR(255) DEFAULT '',
                action_type VARCHAR(255) NOT NULL,
                old_val TEXT NULL,
                new_val TEXT NULL,
                details TEXT NULL,
                ip_address VARCHAR(100) DEFAULT '127.0.0.1',
                status VARCHAR(50) DEFAULT 'success',
                is_edited TINYINT DEFAULT 0,
                edited_by VARCHAR(100) NULL,
                edited_at DATETIME NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
        """)

        # Check existing columns to add if missing
        cursor.execute("SHOW COLUMNS FROM audit_logs")
        existing_cols = [row['Field'] if isinstance(row, dict) else row[0] for row in cursor.fetchall()]
        
        if "is_edited" not in existing_cols:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN is_edited TINYINT DEFAULT 0")
        if "edited_by" not in existing_cols:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN edited_by VARCHAR(100) NULL")
        if "edited_at" not in existing_cols:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN edited_at DATETIME NULL")
        if "details" not in existing_cols:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN details TEXT NULL")
        if "role_badge" not in existing_cols:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN role_badge VARCHAR(80) DEFAULT '🏛️ នាយកសាលា'")
        if "target_id" not in existing_cols:
            cursor.execute("ALTER TABLE audit_logs ADD COLUMN target_id VARCHAR(100) NULL")

        # Seed initial sample audit logs if table is empty
        cursor.execute("SELECT COUNT(*) AS total FROM audit_logs")
        res = cursor.fetchone()
        count = res['total'] if isinstance(res, dict) else res[0]
        if count == 0:
            sample_logs = [
                ("Student", "លោក នាយកសាលា", "🏛️ នាយកសាលា", "STD-001", "សិស្ស: សុខ ចាន់ដារ៉ា (ថ្នាក់ទី ១២-A)", "✏️ កែប្រែឈ្មោះសិស្ស", "ឈ្មោះចាស់: សុខ ចាន់ដា", "ឈ្មោះថ្មី: សុខ ចាន់ដារ៉ា", "កែតម្រូវឈ្មោះតាមសំបុត្រកំណើតផ្លូវការ", "192.168.1.45 (Windows PC)"),
                ("AcademicYear", "លោក នាយកសាលា", "🏛️ នាយកសាលា", "AY-2022-2023", "ឆ្នាំសិក្សា ២០២២-២០២៣", "🚀 បើកឆ្នាំសិក្សាថ្មី", "ស្ថានភាព: បិទ (Closed)", "ស្ថានភាព: កំពុងដំណើរការ (Active)", "បើកដំណើរការឆ្នាំសិក្សាថ្មីជាផ្លូវការ និងរៀបចំថ្នាក់រៀន", "192.168.1.10 (Admin Console)"),
                ("AcademicYear", "លោក នាយកសាលា", "🏛️ នាយកសាលា", "AY-2021-2022", "ឆ្នាំសិក្សា ២០២១-២០២២", "🔒 បិទបញ្ចប់ឆ្នាំសិក្សា", "ស្ថានភាព: កំពុងដំណើរការ (Active)", "ស្ថានភាព: បិទ (Closed)", "បិទបញ្ចប់ឆ្នាំសិក្សា និងរក្សាទុកទិន្នន័យ (Archive)", "192.168.1.10 (Admin Console)"),
                ("Student", "គ្រូ ស៊ឹម សុភា", "👨‍🏫 គ្រូបន្ទុកថ្នាក់", "STD-015", "សិស្ស: មាស រតនា (ថ្នាក់ទី ១១-B)", "✏️ កែប្រែព័ត៌មានទូរស័ព្ទអាណាព្យាបាល", "ទូរស័ព្ទចាស់: 012 334 455", "ទូរស័ព្ទថ្មី: 098 776 655", "ឪពុកម្តាយសិស្សបានស្នើសុំប្តូរលេខទំនាក់ទំនងថ្មី", "192.168.1.88 (Mobile Web)"),
                ("Teacher", "លោក នាយកសាលា", "🏛️ នាយកសាលា", "TCH-005", "គ្រូបង្រៀន: សួស សុភាព", "👨‍🏫 ចាត់តាំងគ្រូបន្ទុកថ្នាក់", "បន្ទុកចាស់: ថ្នាក់ទី ១០-A", "បន្ទុកថ្មី: ថ្នាក់ទី ១១-A", "ចាត់តាំងគ្រូបន្ទុកថ្នាក់សម្រាប់ឆ្នាំសិក្សាថ្មី", "192.168.1.10 (Admin Console)"),
                ("Exam", "គ្រូ សុខ វិបុល", "👨‍🏫 គ្រូបង្រៀន", "STD-001", "សិស្ស: សុខ ចាន់ដារ៉ា (ថ្នាក់ទី ១២-A)", "✏️ កែប្រែពិន្ទុប្រឡងប្រចាំខែ", "គណិតវិទ្យា: ៨៥ ពិន្ទុ", "គណិតវិទ្យា: ៩៥ ពិន្ទុ", "កែតម្រូវពិន្ទុឡើងវិញបន្ទាប់ពីបានផ្ទៀងផ្ទាត់ក្រដាសប្រឡង", "192.168.1.52 (Chrome)")
            ]
            for log in sample_logs:
                cursor.execute("""
                    INSERT INTO audit_logs 
                    (category, performed_by, role_badge, target_id, target_name, action_type, old_val, new_val, details, ip_address)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, log)
    except Exception as e:
        print(f"[-] Error in ensure_audit_logs_table: {e}")

def log_audit_event(category, performed_by, action_type, target_name="", target_id=None, old_val="", new_val="", details="", role_badge="🏛️ នាយកសាលា", ip_address=None):
    """
    Central helper function to record any audit log in MySQL.
    Can be safely called from any API handler.
    """
    conn = None
    try:
        if not ip_address:
            try:
                ip_address = request.headers.get('X-Forwarded-For', request.remote_addr) or '127.0.0.1'
            except Exception:
                ip_address = '127.0.0.1'

        if not performed_by:
            performed_by = "លោក នាយកសាលា (Admin)"

        conn = get_db_connection()
        if not conn:
            return False

        cursor = conn.cursor(dictionary=True)
        ensure_audit_logs_table(cursor)

        cursor.execute("""
            INSERT INTO audit_logs 
            (category, performed_by, role_badge, target_id, target_name, action_type, old_val, new_val, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            str(category or "System"),
            str(performed_by or "Admin"),
            str(role_badge or "🏛️ នាយកសាលា"),
            str(target_id) if target_id else None,
            str(target_name or ""),
            str(action_type or "កែប្រែទិន្នន័យ"),
            str(old_val or "—"),
            str(new_val or "—"),
            str(details or ""),
            str(ip_address)
        ))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[-] Error logging audit event: {e}")
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return False


# ==========================================================
# 1. GET ALL AUDIT LOGS (With Filters, Search, KPI Aggregations)
# ==========================================================
@logs_bp.route("/api/logs", methods=["GET"])
def get_audit_logs():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_audit_logs_table(cursor)

        category = request.args.get("category", "All").strip()
        search_query = request.args.get("q", "").strip().lower()
        limit = int(request.args.get("limit", 200))
        offset = int(request.args.get("offset", 0))

        # Build dynamic WHERE clause
        where_clauses = []
        params = []

        if category and category.lower() != "all":
            where_clauses.append("LOWER(category) = %s")
            params.append(category.lower())

        if search_query:
            where_clauses.append("""(
                LOWER(performed_by) LIKE %s OR 
                LOWER(target_name) LIKE %s OR 
                LOWER(action_type) LIKE %s OR 
                LOWER(COALESCE(old_val, '')) LIKE %s OR 
                LOWER(COALESCE(new_val, '')) LIKE %s OR
                LOWER(COALESCE(details, '')) LIKE %s OR
                LOWER(COALESCE(target_id, '')) LIKE %s
            )""")
            search_param = f"%{search_query}%"
            params.extend([search_param] * 7)

        where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

        # Fetch records
        query = f"""
            SELECT 
                log_id,
                log_id AS id,
                timestamp,
                DATE_FORMAT(timestamp, '%d-%m-%Y %H:%i') AS timestamp_str,
                category,
                performed_by,
                role_badge,
                target_id,
                target_name,
                action_type,
                old_val,
                new_val,
                details,
                ip_address,
                ip_address AS ip,
                status,
                is_edited,
                edited_by,
                edited_at
            FROM audit_logs
            {where_sql}
            ORDER BY timestamp DESC, log_id DESC
            LIMIT %s OFFSET %s
        """
        cursor.execute(query, params + [limit, offset])
        logs = cursor.fetchall()

        # Format dates & logs nicely
        formatted_logs = []
        for l in logs:
            dt = l.get('timestamp')
            time_str = dt.strftime('%d-%m-%Y (%H:%M)') if isinstance(dt, (datetime, date)) else str(l.get('timestamp_str') or dt)
            formatted_logs.append({
                "id": f"LOG-{l['log_id']}",
                "log_id": l['log_id'],
                "timestamp": time_str,
                "raw_timestamp": dt.isoformat() if isinstance(dt, (datetime, date)) else str(dt),
                "category": l['category'],
                "performed_by": l['performed_by'],
                "role_badge": l['role_badge'] or "🏛️ នាយកសាលា",
                "target_id": l['target_id'] or "",
                "target_name": l['target_name'] or "",
                "action_type": l['action_type'] or "កែប្រែ",
                "old_val": l['old_val'] or "—",
                "new_val": l['new_val'] or "—",
                "details": l['details'] or "",
                "ip": l['ip_address'] or "127.0.0.1",
                "status": l['status'] or "success",
                "is_edited": bool(l.get('is_edited', 0)),
                "edited_by": l.get('edited_by') or "",
                "edited_at": str(l.get('edited_at') or "")
            })

        # Calculate KPI Counts
        cursor.execute("""
            SELECT 
                COUNT(*) AS total_count,
                SUM(CASE WHEN LOWER(category) = 'student' THEN 1 ELSE 0 END) AS student_count,
                SUM(CASE WHEN LOWER(category) = 'academicyear' THEN 1 ELSE 0 END) AS academic_year_count,
                SUM(CASE WHEN LOWER(category) = 'teacher' THEN 1 ELSE 0 END) AS teacher_count,
                SUM(CASE WHEN LOWER(category) IN ('principal', 'system', 'admin') THEN 1 ELSE 0 END) AS principal_count
            FROM audit_logs
        """)
        kpi_row = cursor.fetchone() or {}

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "logs": formatted_logs,
            "total": len(formatted_logs),
            "kpi": {
                "total": int(kpi_row.get("total_count") or 0),
                "student": int(kpi_row.get("student_count") or 0),
                "academic_year": int(kpi_row.get("academic_year_count") or 0),
                "teacher": int(kpi_row.get("teacher_count") or 0),
                "principal": int(kpi_row.get("principal_count") or 0)
            }
        })
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": f"កំហុសក្នុងការទាញយកកំណត់ត្រា: {str(e)}"}), 500


# ==========================================================
# 2. CREATE NEW AUDIT LOG MANUALLY (POST)
# ==========================================================
@logs_bp.route("/api/logs", methods=["POST"])
def create_audit_log():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    performed_by = (data.get("performed_by") or "លោក នាយកសាលា (Admin)").strip()
    category = (data.get("category") or "Student").strip()
    role_badge = (data.get("role_badge") or "🏛️ នាយកសាលា").strip()
    target_name = (data.get("target_name") or "ប្រព័ន្ធទូទៅ").strip()
    target_id = (data.get("target_id") or "").strip()
    action_type = (data.get("action_type") or "").strip()
    old_val = (data.get("old_val") or "—").strip()
    new_val = (data.get("new_val") or "—").strip()
    details = (data.get("details") or "").strip()
    ip_address = data.get("ip_address") or request.headers.get('X-Forwarded-For', request.remote_addr) or "127.0.0.1"

    if not action_type:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលប្រភេទសកម្មភាព (Action Type is required)"}), 400

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_audit_logs_table(cursor)

        cursor.execute("""
            INSERT INTO audit_logs 
            (category, performed_by, role_badge, target_id, target_name, action_type, old_val, new_val, details, ip_address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (category, performed_by, role_badge, target_id, target_name, action_type, old_val, new_val, details, ip_address))
        conn.commit()
        new_id = cursor.lastrowid

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានបញ្ចូលកំណត់ត្រាសកម្មភាពដោយជោគជ័យ!",
            "log_id": new_id,
            "id": f"LOG-{new_id}"
        }), 201
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": f"បរាជ័យក្នុងការបញ្ចូលកំណត់ត្រា: {str(e)}"}), 500


# ==========================================================
# 3. UPDATE / EDIT AUDIT LOG ENTRY (PUT)
# ==========================================================
@logs_bp.route("/api/logs/<int:log_id>", methods=["PUT"])
def update_audit_log(log_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    data = request.get_json(silent=True) or request.form.to_dict() or {}
    performed_by = data.get("performed_by")
    category = data.get("category")
    role_badge = data.get("role_badge")
    target_name = data.get("target_name")
    target_id = data.get("target_id")
    action_type = data.get("action_type")
    old_val = data.get("old_val")
    new_val = data.get("new_val")
    details = data.get("details")
    edited_by = data.get("edited_by") or "លោក នាយកសាលា (Admin)"

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_audit_logs_table(cursor)

        # Check existing
        cursor.execute("SELECT * FROM audit_logs WHERE log_id = %s", (log_id,))
        existing = cursor.fetchone()
        if not existing:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": f"រកមិនឃើញកំណត់ត្រាលេខ #{log_id} ឡើយ"}), 404

        # Update fields
        cursor.execute("""
            UPDATE audit_logs 
            SET category = COALESCE(%s, category),
                performed_by = COALESCE(%s, performed_by),
                role_badge = COALESCE(%s, role_badge),
                target_name = COALESCE(%s, target_name),
                target_id = COALESCE(%s, target_id),
                action_type = COALESCE(%s, action_type),
                old_val = COALESCE(%s, old_val),
                new_val = COALESCE(%s, new_val),
                details = COALESCE(%s, details),
                is_edited = 1,
                edited_by = %s,
                edited_at = NOW()
            WHERE log_id = %s
        """, (
            category if category is not None else existing['category'],
            performed_by if performed_by is not None else existing['performed_by'],
            role_badge if role_badge is not None else existing['role_badge'],
            target_name if target_name is not None else existing['target_name'],
            target_id if target_id is not None else existing['target_id'],
            action_type if action_type is not None else existing['action_type'],
            old_val if old_val is not None else existing['old_val'],
            new_val if new_val is not None else existing['new_val'],
            details if details is not None else existing['details'],
            edited_by,
            log_id
        ))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានកែប្រែកំណត់ត្រាសកម្មភាព #{log_id} ដោយជោគជ័យ!",
            "log_id": log_id
        })
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": f"បរាជ័យក្នុងការកែប្រែកំណត់ត្រា: {str(e)}"}), 500


# ==========================================================
# 4. DELETE AUDIT LOG ENTRY (DELETE)
# ==========================================================
@logs_bp.route("/api/logs/<int:log_id>", methods=["DELETE"])
def delete_audit_log(log_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_audit_logs_table(cursor)

        cursor.execute("SELECT * FROM audit_logs WHERE log_id = %s", (log_id,))
        existing = cursor.fetchone()
        if not existing:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": f"រកមិនឃើញកំណត់ត្រាលេខ #{log_id} ឡើយ"}), 404

        cursor.execute("DELETE FROM audit_logs WHERE log_id = %s", (log_id,))
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានលុបកំណត់ត្រាសកម្មភាព #{log_id} ដោយជោគជ័យ!"
        })
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": f"បរាជ័យក្នុងការលុបកំណត់ត្រា: {str(e)}"}), 500
