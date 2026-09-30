import os
import mysql.connector

# Centralized Database Connection Module
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host=os.environ.get('DB_HOST', 'localhost'),
            user=os.environ.get('DB_USER', 'root'),
            password=os.environ.get('DB_PASSWORD', ''),
            database=os.environ.get('DB_NAME', 'school_management'),
            port=int(os.environ.get('DB_PORT', 3306))
        )
        return conn
    except mysql.connector.Error as err:
        print(f"Database Connection Error: {err}")
        return None

def ensure_database_schema(cursor=None):
    """Ensures all required columns and tables exist across the database."""
    conn = None
    close_conn = False
    if cursor is None:
        conn = get_db_connection()
        if not conn:
            return
        cursor = conn.cursor(dictionary=True)
        close_conn = True

    try:
        # Expand column sizes for class_name and grade
        try:
            cursor.execute("ALTER TABLE classes MODIFY COLUMN grade VARCHAR(100) NULL")
            cursor.execute("ALTER TABLE classes MODIFY COLUMN class_name VARCHAR(100) NULL")
            cursor.execute("ALTER TABLE classes MODIFY COLUMN room VARCHAR(100) NULL")
        except Exception:
            pass

        # 1. Students grade column
        cursor.execute("SHOW COLUMNS FROM students LIKE 'grade'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE students ADD COLUMN grade VARCHAR(100) DEFAULT 'Grade 10'")
        else:
            try:
                cursor.execute("ALTER TABLE students MODIFY COLUMN grade VARCHAR(100) DEFAULT 'Grade 10'")
            except Exception:
                pass

        # 2. Student_classes academic_year_id column
        cursor.execute("SHOW COLUMNS FROM student_classes LIKE 'academic_year_id'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE student_classes ADD COLUMN academic_year_id INT NULL")

        # 3. Classes academic_year_id column
        cursor.execute("SHOW COLUMNS FROM classes LIKE 'academic_year_id'")
        if not cursor.fetchone():
            cursor.execute("ALTER TABLE classes ADD COLUMN academic_year_id INT NULL")

        # 4. Student promotions table
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

        if conn:
            conn.commit()

    except Exception as err:
        print("[-] Schema check error:", err)
    finally:
        if close_conn and conn:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass

def check_active_academic_year(cursor=None):
    """Checks if there is an open/active academic year in the database."""
    conn = None
    close_conn = False
    if cursor is None:
        conn = get_db_connection()
        if not conn:
            return False, None
        cursor = conn.cursor(dictionary=True)
        close_conn = True
    try:
        ensure_database_schema(cursor)
        cursor.execute("SELECT academic_year_id, academic_year, status FROM academic_years WHERE status = 'Active' LIMIT 1")
        row = cursor.fetchone()
        if close_conn:
            cursor.close()
            conn.close()
        return bool(row), row
    except Exception as e:
        if close_conn and conn:
            try:
                cursor.close()
                conn.close()
            except Exception:
                pass
        return False, None
