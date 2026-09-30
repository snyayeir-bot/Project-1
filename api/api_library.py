from flask import Blueprint, request, jsonify
from db import get_db_connection
from api.api_login import extract_token_from_request, verify_token
import json
from datetime import datetime, date, timedelta

library_bp = Blueprint('library_bp', __name__)

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

# Helper to ensure book_loans and books table exist with all required columns
def ensure_library_tables(cursor):
    try:
        # 1. Books catalog table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                book_id INT AUTO_INCREMENT PRIMARY KEY,
                book_code VARCHAR(100) UNIQUE NULL,
                title VARCHAR(255) NOT NULL,
                author VARCHAR(150) NULL,
                category VARCHAR(100) DEFAULT 'ចំណេះដឹងទូទៅ',
                total_copies INT DEFAULT 10,
                available_copies INT DEFAULT 10,
                shelf_location VARCHAR(100) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # 2. Book loans table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS book_loans (
                loan_id INT AUTO_INCREMENT PRIMARY KEY,
                student_id INT NOT NULL,
                class_id INT NULL,
                book_title VARCHAR(255) NOT NULL,
                book_code VARCHAR(100) NULL,
                author VARCHAR(150) NULL,
                category VARCHAR(100) DEFAULT 'ចំណេះដឹងទូទៅ',
                quantity INT DEFAULT 1,
                borrow_date DATE NOT NULL,
                due_date DATE NOT NULL,
                return_date DATE NULL,
                status VARCHAR(50) DEFAULT 'borrowed',
                condition_on_borrow VARCHAR(100) DEFAULT 'ល្អ',
                condition_on_return VARCHAR(100) NULL,
                fine_amount DECIMAL(10,2) DEFAULT 0.00,
                notes TEXT NULL,
                recorded_by VARCHAR(100) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                KEY idx_loan_student (student_id),
                KEY idx_loan_class (class_id),
                KEY idx_loan_status (status),
                KEY idx_loan_dates (borrow_date, due_date)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """)

        # Check existing columns in book_loans to alter if needed
        cursor.execute("SHOW COLUMNS FROM book_loans")
        cols = [r['Field'] if isinstance(r, dict) else r[0] for r in cursor.fetchall()]

        if "academic_year_id" not in cols:
            cursor.execute("ALTER TABLE book_loans ADD COLUMN academic_year_id INT NULL")
        if "quantity" not in cols:
            cursor.execute("ALTER TABLE book_loans ADD COLUMN quantity INT DEFAULT 1")
        if "category" not in cols:
            cursor.execute("ALTER TABLE book_loans ADD COLUMN category VARCHAR(100) DEFAULT 'ចំណេះដឹងទូទៅ'")
        if "author" not in cols:
            cursor.execute("ALTER TABLE book_loans ADD COLUMN author VARCHAR(150) NULL")
        if "condition_on_borrow" not in cols:
            cursor.execute("ALTER TABLE book_loans ADD COLUMN condition_on_borrow VARCHAR(100) DEFAULT 'ល្អ'")
        if "condition_on_return" not in cols:
            cursor.execute("ALTER TABLE book_loans ADD COLUMN condition_on_return VARCHAR(100) NULL")
        if "fine_amount" not in cols:
            cursor.execute("ALTER TABLE book_loans ADD COLUMN fine_amount DECIMAL(10,2) DEFAULT 0.00")
        if "recorded_by" not in cols:
            cursor.execute("ALTER TABLE book_loans ADD COLUMN recorded_by VARCHAR(100) NULL")

        # Backfill academic_year_id from classes if not stamped
        cursor.execute("""
            UPDATE book_loans bl 
            JOIN classes c ON bl.class_id = c.class_id 
            SET bl.academic_year_id = c.academic_year_id 
            WHERE bl.academic_year_id IS NULL AND c.academic_year_id IS NOT NULL
        """)

    except Exception as err:
        print(f"[-] Database error in ensure_library_tables: {err}")

# Update overdue loans status automatically
def update_overdue_loans(cursor):
    try:
        today_str = date.today().strftime('%Y-%m-%d')
        cursor.execute("""
            UPDATE book_loans 
            SET status = 'overdue' 
            WHERE status = 'borrowed' AND due_date < %s AND return_date IS NULL
        """, (today_str,))
    except Exception as e:
        print(f"[-] Error auto-updating overdue loans: {e}")


# =========================================================================
# 1. GET LIBRARY OVERVIEW / SUMMARY STATS
# =========================================================================
@library_bp.route("/api/library/overview", methods=["GET"])
@library_bp.route("/api/library/summary", methods=["GET"])
def get_library_summary():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_library_tables(cursor)
        conn.commit()
        update_overdue_loans(cursor)
        conn.commit()

        # 1. Global KPIs directly from Database
        cursor.execute("""
            SELECT 
                COUNT(*) AS total_loans,
                COUNT(DISTINCT student_id) AS total_borrowers,
                SUM(CASE WHEN status = 'borrowed' THEN 1 ELSE 0 END) AS active_borrowed,
                SUM(CASE WHEN status = 'overdue' THEN 1 ELSE 0 END) AS overdue_count,
                SUM(CASE WHEN status = 'returned' THEN 1 ELSE 0 END) AS returned_count,
                COALESCE(SUM(quantity), 0) AS total_books_issued
            FROM book_loans
        """)
        loan_stats = cursor.fetchone() or {}

        # 2. Total inventory directly from books table
        cursor.execute("""
            SELECT 
                COALESCE(SUM(total_copies), 0) AS total_inventory,
                COALESCE(SUM(available_copies), 0) AS total_stock_remaining
            FROM books
        """)
        inv_stats = cursor.fetchone() or {}

        total_inventory = int(inv_stats.get('total_inventory') or 0)
        active_borrowed = int(loan_stats.get('active_borrowed') or 0)
        overdue_count = int(loan_stats.get('overdue_count') or 0)
        returned_count = int(loan_stats.get('returned_count') or 0)
        total_borrowed_now = active_borrowed + overdue_count
        stock_remaining = max(0, total_inventory - total_borrowed_now)

        # 3. Subject / Category inventory breakdown
        cursor.execute("""
            SELECT 
                b.category,
                b.title,
                b.book_code,
                b.total_copies,
                b.available_copies,
                COALESCE(l.borrowed_cnt, 0) AS current_borrowed
            FROM books b
            LEFT JOIN (
                SELECT book_title, COUNT(*) AS borrowed_cnt 
                FROM book_loans 
                WHERE status IN ('borrowed', 'overdue')
                GROUP BY book_title
            ) l ON b.title = l.book_title
            ORDER BY b.book_id ASC
        """)
        subject_breakdown = cursor.fetchall()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "kpi": {
                "total_inventory": total_inventory,
                "total_borrowed": total_borrowed_now,
                "active_borrowed": active_borrowed,
                "returned_count": returned_count,
                "overdue_count": overdue_count,
                "stock_remaining": stock_remaining,
                "total_borrowers": int(loan_stats.get('total_borrowers') or 0),
                "total_loans_history": int(loan_stats.get('total_loans') or 0)
            },
            "subject_breakdown": subject_breakdown
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error in get_library_summary: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 2. GET CLASSES WITH BOOK BORROWING COUNTS (LEVEL 1 GRID)
# =========================================================================
@library_bp.route("/api/library/classes", methods=["GET"])
def get_library_classes():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_library_tables(cursor)
        conn.commit()
        update_overdue_loans(cursor)
        conn.commit()

        year_param = request.args.get('academic_year_id') or request.args.get('year_id')
        all_years = request.args.get('all') in ('true', '1', 'yes')
        where_clause = ""
        params = []

        if year_param and str(year_param).isdigit():
            where_clause = "WHERE c.academic_year_id = %s"
            params.append(int(year_param))
        elif not all_years:
            where_clause = """
                WHERE c.academic_year_id = (SELECT academic_year_id FROM academic_years WHERE status = 'Active' ORDER BY academic_year_id DESC LIMIT 1)
                   OR (c.academic_year_id IS NULL AND (SELECT COUNT(*) FROM academic_years WHERE status = 'Active') = 0)
            """

        # Query classes with homeroom teacher info & loan counts scoped to academic year
        query = f"""
            SELECT 
                c.class_id,
                c.class_name,
                c.grade,
                c.room,
                c.academic_year_id,
                ay.academic_year,
                t.teacher_id,
                t.full_name AS teacher_name,
                t.phone AS teacher_phone,
                t.specialty AS teacher_specialty,
                COUNT(DISTINCT bl.student_id) AS total_borrowers,
                COUNT(CASE WHEN bl.status IN ('borrowed', 'overdue') THEN bl.loan_id ELSE NULL END) AS total_borrowed_books,
                COUNT(CASE WHEN bl.status = 'returned' THEN bl.loan_id ELSE NULL END) AS returned_books,
                COUNT(CASE WHEN bl.status = 'overdue' THEN bl.loan_id ELSE NULL END) AS overdue_books
            FROM classes c
            LEFT JOIN academic_years ay ON c.academic_year_id = ay.academic_year_id
            LEFT JOIN teacher_classes tc ON c.class_id = tc.class_id
            LEFT JOIN teachers t ON tc.teacher_id = t.teacher_id
            LEFT JOIN book_loans bl ON c.class_id = bl.class_id AND (bl.academic_year_id = c.academic_year_id OR bl.academic_year_id IS NULL)
            {where_clause}
            GROUP BY c.class_id, t.teacher_id, ay.academic_year
            ORDER BY c.class_name ASC
        """
        cursor.execute(query, tuple(params))
        classes = cursor.fetchall()
        cursor.close()
        conn.close()

        # Format icons and defaults
        for idx, cls in enumerate(classes):
            cls['id'] = f"CLS-{cls['class_id']}"
            cls['teacher'] = cls.get('teacher_name') or 'មិនទាន់ចាត់តាំង'
            cls['teacher_avatar'] = f"https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=80&auto=format&fit=crop&q=80"
            cls['room'] = f"បន្ទប់ {cls.get('room') or (300 + idx + 1)}"
            cls['icon'] = "bi-calculator" if "12" in str(cls.get('class_name')) else ("bi-book" if "11" in str(cls.get('class_name')) else "bi-journal-bookmark")

        return jsonify({
            "status": "success",
            "classes": classes,
            "count": len(classes)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error in get_library_classes: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 3. GET ALL BOOK LOANS (FILTERABLE BY CLASS, STUDENT, STATUS, SEARCH)
# =========================================================================
@library_bp.route("/api/library/loans", methods=["GET"])
def get_book_loans():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    class_id = request.args.get("class_id")
    student_id = request.args.get("student_id")
    status = request.args.get("status")
    category = request.args.get("category")
    q = (request.args.get("q") or request.args.get("search") or "").strip()

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_library_tables(cursor)
        conn.commit()
        update_overdue_loans(cursor)
        conn.commit()

        year_param = request.args.get("academic_year_id") or request.args.get("year_id")

        base_query = """
            SELECT 
                bl.loan_id,
                bl.student_id,
                bl.class_id,
                bl.academic_year_id,
                ay.academic_year,
                bl.book_title,
                bl.book_code,
                bl.author,
                bl.category,
                bl.quantity,
                bl.borrow_date,
                bl.due_date,
                bl.return_date,
                bl.status,
                bl.condition_on_borrow,
                bl.condition_on_return,
                bl.fine_amount,
                bl.notes,
                bl.recorded_by,
                bl.created_at,
                s.student_code,
                s.full_name AS student_name,
                s.gender AS student_gender,
                s.phone AS student_phone,
                c.class_name,
                DATEDIFF(CURDATE(), bl.due_date) AS days_overdue
            FROM book_loans bl
            LEFT JOIN students s ON bl.student_id = s.student_id
            LEFT JOIN classes c ON bl.class_id = c.class_id
            LEFT JOIN academic_years ay ON bl.academic_year_id = ay.academic_year_id
            WHERE 1=1
        """
        params = []

        if year_param and str(year_param).isdigit():
            base_query += " AND bl.academic_year_id = %s "
            params.append(int(year_param))

        if class_id:
            # Handle CLS-101 format or raw integer
            clean_cid = str(class_id).replace("CLS-", "")
            base_query += " AND bl.class_id = %s "
            params.append(clean_cid)

        if student_id:
            base_query += " AND bl.student_id = %s "
            params.append(student_id)

        if status and status.lower() != 'all':
            base_query += " AND bl.status = %s "
            params.append(status.lower())

        if category and category.lower() != 'all':
            base_query += " AND bl.category = %s "
            params.append(category)

        if q:
            base_query += """
                AND (s.full_name LIKE %s 
                     OR s.student_code LIKE %s 
                     OR bl.book_title LIKE %s 
                     OR bl.book_code LIKE %s 
                     OR bl.author LIKE %s
                     OR c.class_name LIKE %s)
            """
            search_param = f"%{q}%"
            params.extend([search_param, search_param, search_param, search_param, search_param, search_param])

        base_query += " ORDER BY bl.loan_id DESC"

        cursor.execute(base_query, tuple(params))
        loans = cursor.fetchall()
        cursor.close()
        conn.close()

        # Format dates & badges
        for l in loans:
            if l.get('borrow_date'):
                l['borrow_date_raw'] = str(l['borrow_date'])
                l['borrow_date_str'] = str(l['borrow_date'])
            if l.get('due_date'):
                l['due_date_raw'] = str(l['due_date'])
                l['due_date_str'] = str(l['due_date'])
            if l.get('return_date'):
                l['return_date_raw'] = str(l['return_date'])
                l['return_date_str'] = str(l['return_date'])
            else:
                l['return_date_str'] = "—"

            if l.get('created_at'):
                l['created_at'] = str(l['created_at'])

            # Khmer status label & badge
            st = (l.get('status') or 'borrowed').lower()
            if st == 'returned':
                l['status_khmer'] = '🔵 បានសងរួច'
                l['badge_class'] = 'bg-success-subtle text-success border border-success'
            elif st == 'overdue':
                days = max(0, int(l.get('days_overdue') or 0))
                l['status_khmer'] = f'🔴 ហួសកំណត់ ({days} ថ្ងៃ)'
                l['badge_class'] = 'bg-danger-subtle text-danger border border-danger'
            else:
                l['status_khmer'] = '🟢 កំពុងខ្ចី'
                l['badge_class'] = 'bg-warning-subtle text-warning border border-warning'

            l['fine_amount'] = float(l.get('fine_amount') or 0.0)

        return jsonify({
            "status": "success",
            "loans": loans,
            "count": len(loans)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error in get_book_loans: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 3.5 GET AVAILABLE BOOKS & CATEGORIES STRICTLY FROM `books` TABLE
# =========================================================================
@library_bp.route("/api/library/categories", methods=["GET"])
@library_bp.route("/api/library/book_options", methods=["GET"])
def get_library_categories():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_library_tables(cursor)

        # Strictly fetch ONLY from `books` table in MySQL database
        cursor.execute("""
            SELECT 
                book_id, 
                book_code, 
                title, 
                category, 
                author, 
                available_copies, 
                total_copies, 
                shelf_location
            FROM books 
            ORDER BY book_id ASC
        """)
        books_rows = cursor.fetchall()
        cursor.close()
        conn.close()

        # Build list of books & categories strictly from `books` table
        book_items = []
        categories = []
        for b in books_rows:
            display_name = (b.get('category') or b.get('title') or '').strip()
            cat_name = (b.get('category') or b.get('title') or '').strip()
            if display_name and display_name not in categories:
                categories.append(display_name)

            book_items.append({
                "book_id": b.get("book_id"),
                "book_code": b.get("book_code") or f"BK-{b.get('book_id')}",
                "title": b.get("title") or display_name,
                "category": cat_name,
                "author": b.get("author") or "",
                "available_copies": int(b.get("available_copies") or 0),
                "total_copies": int(b.get("total_copies") or 0),
                "shelf_location": b.get("shelf_location") or ""
            })

        return jsonify({
            "status": "success",
            "categories": categories,
            "books": book_items,
            "count": len(book_items)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error in get_library_categories from books table: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 4. CREATE NEW BOOK LOAN RECORD (សាមញ្ញ & រហ័ស - អាចជ្រើសរើសបានច្រើនមុខវិជ្ជា)
# =========================================================================
@library_bp.route("/api/library/loans", methods=["POST"])
def create_book_loan():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    data = get_request_data()
    student_id = data.get("student_id")
    student_code = data.get("student_code")
    class_id = data.get("class_id")
    
    # Handle multiple categories or single category
    raw_categories = data.get("categories") or data.get("category") or data.get("subject") or "ចំណេះដឹងទូទៅ"
    categories_list = []
    if isinstance(raw_categories, list):
        categories_list = [str(c).strip() for c in raw_categories if str(c).strip()]
    elif isinstance(raw_categories, str):
        if "," in raw_categories:
            categories_list = [c.strip() for c in raw_categories.split(",") if c.strip()]
        else:
            categories_list = [raw_categories.strip()]
            
    if not categories_list:
        categories_list = ["ចំណេះដឹងទូទៅ"]

    author = (data.get("author") or "ក្រសួងអប់រំ").strip()
    quantity_per_book = 1
    borrow_date = data.get("borrow_date") or date.today().strftime('%Y-%m-%d')
    due_date = data.get("due_date") or None
    condition_on_borrow = data.get("condition_on_borrow") or "ល្អ"
    notes = data.get("notes") or ""
    recorded_by = data.get("recorded_by") or "Teacher/Admin"

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_library_tables(cursor)

        # Allow due_date column to be NULL if previously NOT NULL
        try:
            cursor.execute("ALTER TABLE book_loans MODIFY COLUMN due_date DATE NULL")
        except Exception:
            pass

        # If student_id is missing but student_code or name is provided, resolve student_id & class_id
        if not student_id and student_code:
            cursor.execute("SELECT student_id FROM students WHERE student_code = %s LIMIT 1", (student_code,))
            s_row = cursor.fetchone()
            if s_row:
                student_id = s_row['student_id']

        if not student_id:
            student_name = data.get("student_name")
            if student_name:
                cursor.execute("SELECT student_id FROM students WHERE full_name LIKE %s LIMIT 1", (f"%{student_name}%",))
                s_row = cursor.fetchone()
                if s_row:
                    student_id = s_row['student_id']

        if not student_id:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Student not found (សូមជ្រើសរើសឈ្មោះសិស្ស)"}), 400

        # Auto-detect class_id if missing
        if not class_id or str(class_id) == "" or str(class_id) == "0":
            cursor.execute("SELECT class_id FROM student_classes WHERE student_id = %s LIMIT 1", (student_id,))
            sc_row = cursor.fetchone()
            if sc_row and sc_row.get('class_id'):
                class_id = sc_row['class_id']
            else:
                class_id = 1
        elif str(class_id).startswith("CLS-"):
            class_id = int(str(class_id).replace("CLS-", ""))

        # Resolve target academic year for this loan
        target_year_id = data.get("academic_year_id")
        target_year_name = ""

        if not target_year_id or str(target_year_id) == "" or str(target_year_id) == "0":
            if class_id:
                cursor.execute("SELECT academic_year_id FROM classes WHERE class_id = %s", (class_id,))
                c_row = cursor.fetchone()
                if c_row and c_row.get('academic_year_id'):
                    target_year_id = c_row['academic_year_id']

        if not target_year_id:
            cursor.execute("SELECT academic_year_id, academic_year FROM academic_years WHERE status = 'Active' ORDER BY academic_year_id DESC LIMIT 1")
            act_yr = cursor.fetchone()
            if act_yr:
                target_year_id = act_yr['academic_year_id']
                target_year_name = act_yr['academic_year']
            else:
                target_year_name = "បច្ចុប្បន្ន"
        else:
            cursor.execute("SELECT academic_year FROM academic_years WHERE academic_year_id = %s", (target_year_id,))
            yr_row = cursor.fetchone()
            target_year_name = yr_row['academic_year'] if yr_row else str(target_year_id)

        # Check if student already has active borrowed books in THIS academic year session
        # (ក្នុងការបើកឆ្នាំសិក្សាថ្មីម្តង សិស្សអាចកត់ត្រាការខ្ចីសៀវភៅសម្រាប់ឆ្នាំសិក្សានោះបាន)
        cursor.execute("""
            SELECT COUNT(*) AS count_loans 
            FROM book_loans 
            WHERE student_id = %s 
              AND status IN ('borrowed', 'overdue')
              AND (academic_year_id = %s OR (%s IS NULL AND academic_year_id IS NULL))
        """, (student_id, target_year_id, target_year_id))
        loan_check = cursor.fetchone()
        if loan_check and (loan_check.get('count_loans') or 0) > 0:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": f"សិស្សនេះបានខ្ចីសៀវភៅរួចរាល់ហើយក្នុងឆ្នាំសិក្សា {target_year_name}! (ក្នុងការបើកឆ្នាំសិក្សាថ្មីម្តង សិស្សអាចកត់ត្រាការខ្ចីសៀវភៅបានម្តង)"
            }), 400

        created_loan_ids = []
        insert_query = """
            INSERT INTO book_loans 
            (student_id, class_id, academic_year_id, book_title, book_code, author, category, quantity, borrow_date, due_date, status, condition_on_borrow, notes, recorded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'borrowed', %s, %s, %s)
        """

        for cat in categories_list:
            b_title = f"សៀវភៅ {cat}"
            b_code = f"BK-{cat[:3].upper()}"
            cursor.execute(insert_query, (
                student_id, class_id, target_year_id, b_title, b_code, author, cat, quantity_per_book, borrow_date, due_date, condition_on_borrow, notes, recorded_by
            ))
            created_loan_ids.append(cursor.lastrowid)

            # Deduct available copy in books catalog if exists
            cursor.execute("""
                UPDATE books 
                SET available_copies = GREATEST(0, available_copies - %s)
                WHERE category = %s OR title = %s
            """, (quantity_per_book, cat, b_title))

        conn.commit()
        cursor.close()
        conn.close()

        cats_str = ", ".join(categories_list)
        return jsonify({
            "status": "success",
            "message": f"បានកត់ត្រាការខ្ចីសៀវភៅមុខវិជ្ជា [{cats_str}] ចំនួន {len(created_loan_ids)} ក្បាល ដោយជោគជ័យ!",
            "loan_ids": created_loan_ids
        }), 201

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error creating book loan: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 5. RETURN A BORROWED BOOK (MARK AS RETURNED)
# =========================================================================
@library_bp.route("/api/library/loans/<int:loan_id>/return", methods=["PUT", "POST"])
def return_book_loan(loan_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    data = get_request_data()
    return_date = data.get("return_date") or date.today().strftime('%Y-%m-%d')
    condition_on_return = data.get("condition_on_return") or "ល្អ"
    fine_amount = float(data.get("fine_amount") or 0.0)
    notes = data.get("notes") or ""

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_library_tables(cursor)

        # Fetch existing loan
        cursor.execute("SELECT * FROM book_loans WHERE loan_id = %s", (loan_id,))
        loan = cursor.fetchone()
        if not loan:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Loan record not found"}), 404

        # Update loan record
        update_query = """
            UPDATE book_loans
            SET status = 'returned',
                return_date = %s,
                condition_on_return = %s,
                fine_amount = %s,
                notes = CONCAT(COALESCE(notes, ''), CASE WHEN %s != '' THEN CONCAT(' | ', %s) ELSE '' END)
            WHERE loan_id = %s
        """
        cursor.execute(update_query, (return_date, condition_on_return, fine_amount, notes, notes, loan_id))
        conn.commit()

        # Restore available copies in books catalog if matched
        book_title = loan.get('book_title')
        quantity = loan.get('quantity') or 1
        if book_title:
            cursor.execute("""
                UPDATE books 
                SET available_copies = LEAST(total_copies, available_copies + %s)
                WHERE title = %s
            """, (quantity, book_title))
            conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានទទួលសងសៀវភៅ '{book_title}' រួចរាល់ដោយជោគជ័យ!",
            "loan_id": loan_id
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error returning book loan: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 6. DELETE / CANCEL BOOK LOAN
# =========================================================================
@library_bp.route("/api/library/loans/<int:loan_id>", methods=["DELETE"])
def delete_book_loan(loan_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM book_loans WHERE loan_id = %s", (loan_id,))
        loan = cursor.fetchone()
        if not loan:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Loan record not found"}), 404

        # If it was borrowed/overdue, restore catalog copy count
        if loan.get('status') in ['borrowed', 'overdue'] and loan.get('book_title'):
            qty = loan.get('quantity') or 1
            cursor.execute("""
                UPDATE books 
                SET available_copies = LEAST(total_copies, available_copies + %s)
                WHERE title = %s
            """, (qty, loan.get('book_title')))

        cursor.execute("DELETE FROM book_loans WHERE loan_id = %s", (loan_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានលុបកំណត់ត្រាខ្ចីសៀវភៅលេខ #{loan_id} ដោយជោគជ័យ!"
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error deleting book loan: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 7. GET / MANAGE BOOKS CATALOG & INVENTORY STOCK
# =========================================================================
@library_bp.route("/api/library/books", methods=["GET"])
def get_library_books():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_library_tables(cursor)
        
        # Fetch books with current active borrowed count
        cursor.execute("""
            SELECT 
                b.book_id,
                b.book_code,
                b.title,
                b.author,
                b.category,
                b.total_copies,
                b.available_copies,
                b.shelf_location,
                b.created_at,
                COALESCE(l.borrowed_cnt, 0) AS current_borrowed
            FROM books b
            LEFT JOIN (
                SELECT book_title, COUNT(*) AS borrowed_cnt 
                FROM book_loans 
                WHERE status IN ('borrowed', 'overdue')
                GROUP BY book_title
            ) l ON b.title = l.book_title
            ORDER BY b.book_id DESC
        """)
        books = cursor.fetchall()
        cursor.close()
        conn.close()

        for b in books:
            if b.get('created_at'):
                b['created_at'] = str(b['created_at'])

        return jsonify({
            "status": "success",
            "books": books,
            "count": len(books)
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error fetching books: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 8. ADD NEW BOOK TO INVENTORY STOCK (➕ បន្ថែមសៀវភៅថ្មីចូលស្តុក)
# =========================================================================
@library_bp.route("/api/library/books", methods=["POST"])
def add_new_book_to_stock():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    data = get_request_data()
    title = (data.get("title") or "").strip()
    book_code = (data.get("book_code") or "").strip()
    author = (data.get("author") or "ក្រសួងអប់រំ").strip()
    category = (data.get("category") or "ចំណេះដឹងទូទៅ").strip()
    total_copies = int(data.get("total_copies") or 10)
    shelf_location = (data.get("shelf_location") or "ជួរ A-01").strip()

    if not title:
        return jsonify({"status": "error", "message": "Book title is required (សូមបញ្ចូលចំណងជើងសៀវភៅ)"}), 400

    if not book_code:
        # Generate clean book code if not provided
        book_code = f"BK-{category[:3].upper()}-{int(datetime.now().timestamp()) % 10000}"

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_library_tables(cursor)

        # Check if book title already exists
        cursor.execute("SELECT book_id, total_copies, available_copies FROM books WHERE title = %s OR book_code = %s LIMIT 1", (title, book_code))
        existing = cursor.fetchone()

        if existing:
            # If exists, increment copies (restock)
            cursor.execute("""
                UPDATE books 
                SET total_copies = total_copies + %s,
                    available_copies = available_copies + %s,
                    shelf_location = COALESCE(%s, shelf_location)
                WHERE book_id = %s
            """, (total_copies, total_copies, shelf_location, existing['book_id']))
            conn.commit()
            book_id = existing['book_id']
            msg = f"សៀវភៅ '{title}' មានក្នុងស្តុកស្រាប់ - បានបន្ថែមចំនួន {total_copies} ក្បាលបន្ថែមដោយជោគជ័យ!"
        else:
            cursor.execute("""
                INSERT INTO books (book_code, title, author, category, total_copies, available_copies, shelf_location)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (book_code, title, author, category, total_copies, total_copies, shelf_location))
            conn.commit()
            book_id = cursor.lastrowid
            msg = f"បានបញ្ចូលសៀវភៅ '{title}' ចំនួន {total_copies} ក្បាលទៅក្នុងស្តុកដោយជោគជ័យ!"

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": msg,
            "book_id": book_id
        }), 201

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error adding book to stock: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 9. RESTOCK / ADD COPIES TO EXISTING BOOK (➕ បន្ថែមចំនួនស្តុក)
# =========================================================================
@library_bp.route("/api/library/books/<int:book_id>/add_stock", methods=["POST", "PUT"])
def restock_existing_book(book_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    data = get_request_data()
    additional_copies = int(data.get("additional_copies") or data.get("copies") or 0)
    shelf_location = data.get("shelf_location")

    if additional_copies <= 0:
        return jsonify({"status": "error", "message": "Additional copies must be greater than 0 (ចំនួនត្រូវធំជាង ០)"}), 400

    try:
        cursor = conn.cursor(dictionary=True)
        ensure_library_tables(cursor)

        cursor.execute("SELECT * FROM books WHERE book_id = %s", (book_id,))
        book = cursor.fetchone()
        if not book:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Book not found"}), 404

        if shelf_location:
            cursor.execute("""
                UPDATE books 
                SET total_copies = total_copies + %s,
                    available_copies = available_copies + %s,
                    shelf_location = %s
                WHERE book_id = %s
            """, (additional_copies, additional_copies, shelf_location, book_id))
        else:
            cursor.execute("""
                UPDATE books 
                SET total_copies = total_copies + %s,
                    available_copies = available_copies + %s
                WHERE book_id = %s
            """, (additional_copies, additional_copies, book_id))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានបន្ថែមចំនួន {additional_copies} ក្បាល លើសៀវភៅ '{book['title']}' ដោយជោគជ័យ!",
            "book_id": book_id
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error restocking book: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 10. EDIT BOOK DETAILS
# =========================================================================
@library_bp.route("/api/library/books/<int:book_id>", methods=["PUT"])
def update_book_details(book_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    data = get_request_data()
    title = (data.get("title") or "").strip()
    book_code = (data.get("book_code") or "").strip()
    author = (data.get("author") or "").strip()
    category = (data.get("category") or "").strip()
    shelf_location = (data.get("shelf_location") or "").strip()

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            UPDATE books
            SET title = COALESCE(NULLIF(%s, ''), title),
                book_code = COALESCE(NULLIF(%s, ''), book_code),
                author = COALESCE(NULLIF(%s, ''), author),
                category = COALESCE(NULLIF(%s, ''), category),
                shelf_location = COALESCE(NULLIF(%s, ''), shelf_location)
            WHERE book_id = %s
        """, (title, book_code, author, category, shelf_location, book_id))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": "បានកែប្រែព័ត៌មានសៀវភៅដោយជោគជ័យ!"
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error updating book: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# =========================================================================
# 11. DELETE BOOK FROM INVENTORY
# =========================================================================
@library_bp.route("/api/library/books/<int:book_id>", methods=["DELETE"])
def delete_book_from_stock(book_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM books WHERE book_id = %s", (book_id,))
        book = cursor.fetchone()
        if not book:
            cursor.close()
            conn.close()
            return jsonify({"status": "error", "message": "Book not found"}), 404

        # Check if there are active loans with this book title
        cursor.execute("SELECT COUNT(*) AS active_cnt FROM book_loans WHERE book_title = %s AND status IN ('borrowed', 'overdue')", (book['title'],))
        act_row = cursor.fetchone()
        if act_row and (act_row['active_cnt'] if isinstance(act_row, dict) else act_row[0]) > 0:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error", 
                "message": f"មិនអាចលុបសៀវភៅនេះបានទេ ពីព្រោះកំពុងមានសិស្សខ្ចី {act_row['active_cnt']} ក្បាល!"
            }), 400

        cursor.execute("DELETE FROM books WHERE book_id = %s", (book_id,))
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"បានលុបសៀវភៅ '{book['title']}' ចេញពីស្តុកដោយជោគជ័យ!"
        }), 200

    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        print(f"[-] Error deleting book: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500
