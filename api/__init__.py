# API Package
from .api_login import auth_bp, generate_token, verify_token, token_required
from .api_register import register_bp
from .api_teachers import teachers_bp
from .api_student import student_bp
from .api_class import class_bp
from .api_subject import subject_bp
from .api_examination import exam_bp
from .api_score import score_bp
from .api_aeccunt_teachers import aeccunt_bp

__all__ = ['auth_bp', 'register_bp', 'generate_token', 'verify_token', 'token_required', 'teachers_bp', 'student_bp', 'class_bp', 'subject_bp', 'exam_bp', 'score_bp', 'aeccunt_bp']

