import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from flask import Flask, request, jsonify

from api.api_login import auth_bp
from api.api_register import register_bp
from api.api_teachers import teachers_bp
from api.api_aeccunt_teachers import aeccunt_bp
from api.api_student import student_bp
from api.api_class import class_bp
from api.api_subject import subject_bp
from api.api_examination import exam_bp
from api.api_score import score_bp
from api.api_attendance import attendance_bp
from api.api_library import library_bp
from api.api_logs import logs_bp
from Router import router_bp

app = Flask(__name__)

# Global Preflight & CORS Handler to eliminate 405 (Method Not Allowed)
@app.before_request
def handle_preflight():
    if request.method == "OPTIONS":
        response = app.make_default_options_response()
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
        return response

# Enable CORS headers on all responses
@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response

# Register Blueprints
app.register_blueprint(auth_bp)
app.register_blueprint(register_bp)
app.register_blueprint(teachers_bp)
app.register_blueprint(aeccunt_bp)
app.register_blueprint(student_bp)
app.register_blueprint(class_bp)
app.register_blueprint(subject_bp)
app.register_blueprint(exam_bp)
app.register_blueprint(score_bp)
app.register_blueprint(attendance_bp)
app.register_blueprint(library_bp)
app.register_blueprint(logs_bp)
app.register_blueprint(router_bp)

if __name__ == '__main__':
    app.run(host='localhost', port=3000, debug=True)