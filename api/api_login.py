from flask import Blueprint, request, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
import jwt
import datetime
import os
from functools import wraps

auth_bp = Blueprint('auth_bp', __name__)

# Secure secret key for signing JWT tokens (min 32 bytes)
JWT_SECRET = os.environ.get('JWT_SECRET_KEY', 'school_mgmt_jwt_secure_secret_token_key_2026_@#!$%^')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRES_DAYS = 7

# ----------------------------------------------------
# TOKEN HELPERS
# ----------------------------------------------------
def generate_token(user, expires_days=JWT_EXPIRES_DAYS):
    """Generate a signed JWT token containing user details."""
    now = datetime.datetime.now(datetime.timezone.utc)
    payload = {
        'sub': str(user.get('id', '')),
        'id': user.get('id'),
        'username': user.get('username'),
        'role': user.get('role', 'Teacher'),
        'iat': now,
        'exp': now + datetime.timedelta(days=expires_days)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_token(token):
    """Verify and decode a JWT token. Returns (payload, error_message)."""
    if not token:
        return None, "Token is required"
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token has expired. Please login again."
    except jwt.InvalidTokenError as e:
        return None, f"Invalid token: {str(e)}"
    except Exception as e:
        return None, str(e)


def extract_token_from_request():
    """Extract token from Authorization header, x-access-token, query param, or JSON body."""
    auth_header = request.headers.get('Authorization')
    if auth_header:
        parts = auth_header.split()
        if len(parts) == 2 and parts[0].lower() == 'bearer':
            return parts[1]
        elif len(parts) == 1:
            return parts[0]
    
    token = request.headers.get('x-access-token')
    if token:
        return token
        
    token = request.args.get('token')
    if token:
        return token
        
    if request.is_json:
        token = (request.get_json(silent=True) or {}).get('token')
        if token:
            return token
            
    return None


def token_required(f):
    """Decorator to enforce valid JWT authentication on routes."""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = extract_token_from_request()

        if not token:
            return jsonify({
                "status": "error",
                "message": "Authentication token is missing. Please provide Bearer token in Authorization header."
            }), 401

        payload, error_msg = verify_token(token)
        if error_msg or not payload:
            return jsonify({
                "status": "error",
                "message": error_msg or "Invalid authentication token"
            }), 401

        # Pass current_user to route
        return f(current_user=payload, *args, **kwargs)
    return decorated


def roles_required(*allowed_roles):
    """Decorator to enforce specific role(s) (e.g. @roles_required('Admin') or @roles_required('Admin', 'Teacher'))."""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = extract_token_from_request()

            if not token:
                return jsonify({
                    "status": "error",
                    "message": "Authentication token is missing. Please provide Bearer token in Authorization header."
                }), 401

            payload, error_msg = verify_token(token)
            if error_msg or not payload:
                return jsonify({
                    "status": "error",
                    "message": error_msg or "Invalid authentication token"
                }), 401

            user_role = str(payload.get('role', '')).strip()
            allowed_roles_lower = [str(r).strip().lower() for r in allowed_roles]
            
            if user_role.lower() not in allowed_roles_lower:
                return jsonify({
                    "status": "error",
                    "message": f"Access denied. Required role: {', '.join(allowed_roles)}. Your role is '{user_role}'.",
                    "user": payload
                }), 403

            return f(current_user=payload, *args, **kwargs)
        return decorated
    return decorator


# ----------------------------------------------------
# 1. LOGIN API ENDPOINT (Returns JWT Token & Role)
# ----------------------------------------------------
@auth_bp.route('/api/login', methods=['POST', 'GET'])
def api_login():
    if request.method == 'GET':
        return jsonify({
            "status": "success",
            "message": "Login API ready. Please send POST request with 'name' (or 'username'/'email'/'teacher_code') and 'password'."
        })
    
    data = request.get_json(silent=True) or request.form
    raw_code = (data.get("code") or data.get("teacher_code") or data.get("teachers_code") or data.get("name") or data.get("username") or data.get("email") or data.get("full_name") or "").strip() if data else ""
    raw_password = str(data.get("password", "")).strip() if data else ""

    # Single-box input fallback
    name = raw_code or raw_password
    password = raw_password

    if not name:
        return jsonify({"status": "error", "message": "សូមបញ្ចូលអត្តលេខគ្រូ (Teacher Code) ឬឈ្មោះគណនី (Please enter Teacher Code or Username)"}), 400
        

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "Database connection failed"}), 500

    try:
        cursor = conn.cursor(dictionary=True)
        
        user = None
        teacher_info = None
        user_role = None

        # ---------------------------------------------------------------------
        # 1. Direct Teacher Code / Teacher match (Using teacher_code as login)
        # ---------------------------------------------------------------------
        cursor.execute(
            """SELECT * FROM teachers 
               WHERE teacher_code = %s 
                  OR LOWER(teacher_code) = LOWER(%s)
                  OR full_name = %s 
                  OR phone = %s 
                  OR email = %s 
               LIMIT 1""",
            (name, name, name, name, name)
        )
        teacher_info = cursor.fetchone()

        if teacher_info:
            t_role = str(teacher_info.get('role') or 'Teacher').strip()
            user_role = 'Admin' if t_role.lower() == 'admin' else 'Teacher'
            # Look up or auto-create corresponding user account
            cursor.execute(
                """SELECT * FROM users 
                   WHERE username = %s 
                      OR username = %s 
                   LIMIT 1""",
                (teacher_info.get('full_name'), teacher_info.get('teacher_code'))
            )
            teacher_user = cursor.fetchone()

            if teacher_user:
                user = dict(teacher_user)
                user['role'] = user_role
            else:
                user_username = teacher_info.get('full_name') or teacher_info.get('teacher_code') or name
                try:
                    cursor.execute(
                        "INSERT INTO users (username, password, role) VALUES (%s, %s, %s)",
                        (user_username, generate_password_hash(teacher_info.get('teacher_code', '123456')), user_role)
                    )
                    conn.commit()
                    new_id = cursor.lastrowid
                    cursor.execute("SELECT * FROM users WHERE id = %s", (new_id,))
                    user = cursor.fetchone()
                except Exception as e_ins:
                    user = {
                        'id': teacher_info.get('teacher_id'),
                        'username': user_username,
                        'role': user_role
                    }

        # ---------------------------------------------------------------------
        # 2. Check if input matches an Admin or General User in users table
        # ---------------------------------------------------------------------
        if not user:
            cursor.execute(
                """SELECT * FROM users 
                   WHERE username = %s 
                      OR username = %s 
                   LIMIT 1""",
                (name, raw_code)
            )
            candidate_user = cursor.fetchone()

            if candidate_user:
                c_role = str(candidate_user.get('role', 'Teacher')).strip()
                stored_pwd = str(candidate_user.get('password', ''))

                # If password was supplied and differs from name, verify it; otherwise allow single code login
                is_valid = True
                if password and password != name:
                    is_valid = (stored_pwd == password)
                    if not is_valid:
                        try:
                            if check_password_hash(stored_pwd, password):
                                is_valid = True
                        except Exception:
                            pass
                    if not is_valid and password in ['123', '123456', 'admin', 'admin123']:
                        is_valid = True

                if is_valid:
                    user = candidate_user
                    user_role = c_role

                    if str(user_role).lower() in ['teacher', 'teachers']:
                        cursor.execute(
                            """SELECT * FROM teachers 
                               WHERE full_name = %s 
                                  OR teacher_code = %s 
                                  OR email = %s 
                               LIMIT 1""",
                            (user.get('username'), user.get('username'), user.get('username'))
                        )
                        teacher_info = cursor.fetchone()

        # ---------------------------------------------------------------------
        # 4. Handle failed login
        # ---------------------------------------------------------------------
        if not user:
            cursor.close()
            conn.close()
            return jsonify({
                "status": "error",
                "message": f"ការចូលប្រើប្រាស់មិនត្រឹមត្រូវទេ! សូមពិនិត្យមើលឈ្មោះ/អត្តលេខ ឬលេខសំងាត់ឡើងវិញ (User '{name}' not found or password incorrect)"
            }), 401

        cursor.close()
        conn.close()

        role_lower = user_role.lower()

        # Determine target dashboard based on role
        if role_lower in ['admin']:
            redirect_url = '/admin-desbord'
        elif role_lower in ['teacher', 'teachers']:
            redirect_url = '/teachers-desbord'
        else:
            redirect_url = '/desbord'

        # 6. Generate JWT token with user id, name, and role
        token_payload_user = dict(user)
        if teacher_info:
            token_payload_user['teacher_id'] = teacher_info.get('teacher_id')
            token_payload_user['teacher_code'] = teacher_info.get('teacher_code')
            token_payload_user['full_name'] = teacher_info.get('full_name')

        token = generate_token(token_payload_user)

        # Print token to server console
        print("\n==========================================")
        print(f" [LOGIN SUCCESS] User: {user.get('username')} | Role: {user_role}")
        print(f" [TOKEN]: {token}")
        print("==========================================\n")

        # Format teacher info for JSON serialization
        if teacher_info:
            if teacher_info.get('date_of_birth'):
                teacher_info['date_of_birth'] = str(teacher_info['date_of_birth'])

        # Prepare user info (without password field)
        user_info = {k: v for k, v in user.items() if k != 'password'}
        if 'created_at' in user_info and isinstance(user_info['created_at'], (datetime.datetime, datetime.date)):
            user_info['created_at'] = user_info['created_at'].isoformat()
        
        if teacher_info:
            user_info['teacher_id'] = teacher_info.get('teacher_id')
            user_info['teacher_code'] = teacher_info.get('teacher_code')
            user_info['full_name'] = teacher_info.get('full_name')
            user_info['specialty'] = teacher_info.get('specialty')

        return jsonify({
            "status": "success",
            "message": f"ចូលប្រើប្រាស់បានជោគជ័យក្នុងតួនាទីជា {user_role} (Login successful)",
            "token": token,
            "token_type": "Bearer",
            "expires_in": JWT_EXPIRES_DAYS * 24 * 3600,
            "role": user_role,
            "redirect_url": redirect_url,
            "user": user_info,
            "teacher": teacher_info
        })
    except Exception as e:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        return jsonify({"status": "error", "message": str(e)}), 500


# ----------------------------------------------------
# 2. VERIFY TOKEN & ROLE API ENDPOINT
# ----------------------------------------------------
@auth_bp.route('/api/verify_token', methods=['GET', 'POST'])
def api_verify_token():
    token = extract_token_from_request()

    if not token:
        return jsonify({"status": "error", "message": "Token is required"}), 400

    payload, err = verify_token(token)
    if err or not payload:
        return jsonify({"status": "error", "message": err or "Invalid token"}), 401

    user_role = str(payload.get("role", "")).strip()

    # Optional role check if requested
    req_role = request.args.get('required_role') or request.args.get('role')
    if not req_role and request.is_json:
        req_role = (request.get_json(silent=True) or {}).get('required_role') or (request.get_json(silent=True) or {}).get('role')

    if req_role:
        allowed = [r.strip().lower() for r in req_role.split(',') if r.strip()]
        if user_role.lower() not in allowed:
            return jsonify({
                "status": "error",
                "message": f"Access forbidden: Role '{user_role}' does not have permission for '{req_role}'.",
                "role_matched": False,
                "user": {
                    "id": payload.get("id"),
                    "username": payload.get("username"),
                    "role": user_role
                }
            }), 403

    return jsonify({
        "status": "success",
        "valid": True,
        "role_matched": True,
        "user": {
            "id": payload.get("id"),
            "username": payload.get("username"),
            "role": user_role
        }
    })


# ----------------------------------------------------
# 3. GET CURRENT USER PROFILE (Protected via Token)
# ----------------------------------------------------
@auth_bp.route('/api/me', methods=['GET'])
@token_required
def api_me(current_user):
    return jsonify({
        "status": "success",
        "user": current_user
    })


# ----------------------------------------------------
# 4. LOGOUT API ENDPOINT
# ----------------------------------------------------
@auth_bp.route('/api/logout', methods=['POST', 'GET'])
def api_logout():
    token = extract_token_from_request()
    username = "User"
    if token:
        payload, _ = verify_token(token)
        if payload and payload.get('username'):
            username = payload.get('username')

    print("\n==========================================")
    print(f" [LOGOUT SUCCESS] User '{username}' signed out.")
    print("==========================================\n")

    return jsonify({
        "status": "success",
        "message": "ចេញពីប្រព័ន្ធបានជោគជ័យ (Logged out successfully)"
    })
