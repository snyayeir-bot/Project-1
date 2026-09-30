from flask import Blueprint, request, send_from_directory, redirect, jsonify
import os

router_bp = Blueprint('router_bp', __name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
HTML_DIR = os.path.join(BASE_DIR, 'Font-end')
ADMIN_DIR = os.path.join(HTML_DIR, 'admin-desbord')
TEACHERS_DIR = os.path.join(HTML_DIR, 'teachers-desbord')

def find_and_send_file(filename):
    # 1. Check inside BASE_DIR directly (handles /Font-end/js/auth-guard.js, /Font-end/css/..., etc.)
    full_base_path = os.path.join(BASE_DIR, filename)
    if os.path.exists(full_base_path) and os.path.isfile(full_base_path):
        return send_from_directory(BASE_DIR, filename)

    # 2. Check exact path inside HTML_DIR (handles /js/auth-guard.js, /css/..., etc.)
    full_html_path = os.path.join(HTML_DIR, filename)
    if os.path.exists(full_html_path) and os.path.isfile(full_html_path):
        return send_from_directory(HTML_DIR, filename)
    
    # 3. If filename starts with "Font-end/", strip it and check in HTML_DIR
    if filename.startswith('Font-end/'):
        clean_name = filename[len('Font-end/'):]
        full_clean_path = os.path.join(HTML_DIR, clean_name)
        if os.path.exists(full_clean_path) and os.path.isfile(full_clean_path):
            return send_from_directory(HTML_DIR, clean_name)

    # 4. Check inside admin-desbord folder
    filename_base = os.path.basename(filename)
    if os.path.exists(os.path.join(ADMIN_DIR, filename_base)) and os.path.isfile(os.path.join(ADMIN_DIR, filename_base)):
        return send_from_directory(ADMIN_DIR, filename_base)
        
    # 5. Check inside teachers-desbord folder
    if os.path.exists(os.path.join(TEACHERS_DIR, filename_base)) and os.path.isfile(os.path.join(TEACHERS_DIR, filename_base)):
        return send_from_directory(TEACHERS_DIR, filename_base)

    # Fallback
    return send_from_directory(HTML_DIR, filename)

# 1. Login Page Route (Supports '/', '/login', '/Login', '/Login.html', '/login.html')
@router_bp.route('/', methods=['GET', 'POST'])
@router_bp.route('/login', methods=['GET', 'POST'])
@router_bp.route('/Login', methods=['GET', 'POST'])
@router_bp.route('/Login.html', methods=['GET'])
@router_bp.route('/login.html', methods=['GET'])
def login():
    if request.method == 'GET':
        return send_from_directory(HTML_DIR, 'Login.html')
    else:
        return redirect("/desbord")

# 2. Register Page Route (Supports '/register', '/Register', '/Register.html', '/register.html')
@router_bp.route('/register', methods=['GET'])
@router_bp.route('/Register', methods=['GET'])
@router_bp.route('/Register.html', methods=['GET'])
@router_bp.route('/register.html', methods=['GET'])
def register():
    return send_from_directory(HTML_DIR, 'Register.html')

# 2. General Dashboard Route
@router_bp.route('/desbord', methods=['GET', 'POST'])
def desbord():
    if request.method == 'GET':
        return redirect("/admin-desbord")
    else:
        return jsonify({"status": "success"})

# 3. Admin Main Dashboard Route
@router_bp.route('/admin-desbord', methods=['GET'])
def admin_desbord_portal():
    return send_from_directory(ADMIN_DIR, 'admin-desbord.html')

# 4. Admin Teachers Management Route
@router_bp.route('/admin-desbord-tacher', methods=['GET'])
@router_bp.route('/admin-desbord-tacher.html', methods=['GET'])
def admin_desbord_teacher_portal():
    return send_from_directory(ADMIN_DIR, 'admin-desbord-tacher.html')

# 5. Admin Students Management Route
@router_bp.route('/admin-desbord-students', methods=['GET'])
@router_bp.route('/admin-desbord-students.html', methods=['GET'])
def admin_desbord_students_portal():
    return send_from_directory(ADMIN_DIR, 'admin-desbord-students.html')

# 5.1 Admin Library & Book Loans Management Route
@router_bp.route('/admin-desbord-library', methods=['GET'])
@router_bp.route('/admin-desbord-library.html', methods=['GET'])
def admin_desbord_library_portal():
    return send_from_directory(ADMIN_DIR, 'admin-desbord-library.html')

# 5.2 Admin Audit Logs Route
@router_bp.route('/admin-desbord-logs', methods=['GET'])
@router_bp.route('/admin-desbord-logs.html', methods=['GET'])
def admin_desbord_logs_portal():
    return send_from_directory(ADMIN_DIR, 'admin-desbord-logs.html')

# 5.3 Admin Exams Route
@router_bp.route('/admin-desbord-exams', methods=['GET'])
@router_bp.route('/admin-desbord-exams.html', methods=['GET'])
def admin_desbord_exams_portal():
    return send_from_directory(ADMIN_DIR, 'admin-desbord-exams.html')

# 5.4 Admin Attendance Route
@router_bp.route('/admin-desbord-attendance', methods=['GET'])
@router_bp.route('/admin-desbord-attendance.html', methods=['GET'])
def admin_desbord_attendance_portal():
    return send_from_directory(ADMIN_DIR, 'admin-desbord-attendance.html')

# 5.5 Admin Projects / Academic Year Route
@router_bp.route('/admin-desbord-projects', methods=['GET'])
@router_bp.route('/admin-desbord-projects.html', methods=['GET'])
def admin_desbord_projects_portal():
    return send_from_directory(ADMIN_DIR, 'admin-desbord-projects.html')

# 5. Teacher Portal Route
@router_bp.route('/teachers-desbord', methods=['GET'])
@router_bp.route('/desbord-tacher', methods=['GET'])
@router_bp.route('/desbord-tacher.html', methods=['GET'])
def teachers_desbord_portal():
    return send_from_directory(TEACHERS_DIR, 'teachers-desbord.html')

# 6. Static Files & Assets Route Handler
@router_bp.route('/<path:filename>', methods=['GET'])
def serve_static(filename):
    return find_and_send_file(filename)
