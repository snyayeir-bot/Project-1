from flask import redirect
from flask import Flask, request, jsonify, send_file, send_from_directory
import os

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
HTML_DIR = os.path.join(BASE_DIR, 'Font-end')



@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return send_from_directory(HTML_DIR, 'Login.html')
    else:
        email = request.form.get('email')
        password = request.form.get('password')
        response = {
            "status": "success",
            "email": email,
            "password": password
        }
        # return jsonify(response, ) 
        return redirect("/desbord")



@app.route('/desbord', methods=['GET', 'POST'])
def desbord():
    if request.method == 'GET':
        return redirect("/admin-desbord")
    else:
        return jsonify({"status": "success"})

@app.route('/admin-desbord', methods=['GET'])
def admin_desbord_portal():
    return send_from_directory(os.path.join(HTML_DIR, 'admin-desbord'), 'admin-desbord.html')

@app.route('/teachers-desbord', methods=['GET'])
@app.route('/desbord-tacher', methods=['GET'])
@app.route('/desbord-tacher.html', methods=['GET'])
def teachers_desbord_portal():
    return send_from_directory(os.path.join(HTML_DIR, 'teachers-desbord'), 'teachers-desbord.html')






ADMIN_DIR = os.path.join(HTML_DIR, 'admin-desbord')
TEACHERS_DIR = os.path.join(HTML_DIR, 'teachers-desbord')

def find_and_send_file(filename):
    # Check exact path inside HTML_DIR
    if os.path.exists(os.path.join(HTML_DIR, filename)) and os.path.isfile(os.path.join(HTML_DIR, filename)):
        return send_from_directory(HTML_DIR, filename)
    
    # Check inside admin-desbord folder
    filename_base = os.path.basename(filename)
    if os.path.exists(os.path.join(ADMIN_DIR, filename_base)):
        return send_from_directory(ADMIN_DIR, filename_base)
        
    # Check inside teachers-desbord folder
    if os.path.exists(os.path.join(TEACHERS_DIR, filename_base)):
        return send_from_directory(TEACHERS_DIR, filename_base)

    # Fallback
    return send_from_directory(HTML_DIR, filename)


# API Route to return Teachers Data List
@app.route('/api/teachers', methods=['GET'])
def get_teachers_list():
    teachers = [
        {
            "id": "TCH-2026-001",
            "name": "Prof. Sarah Jenkins",
            "email": "s.jenkins@school.edu",
            "avatar": "https://images.unsplash.com/photo-1573496359142-b8d87734a5a2?w=100&auto=format&fit=crop&q=80",
            "subject": "Pure Mathematics",
            "classes_count": 4,
            "students_count": 142,
            "status": "Active"
        },
        {
            "id": "TCH-2026-002",
            "name": "Dr. Michael Vance",
            "email": "m.vance@school.edu",
            "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=100&auto=format&fit=crop&q=80",
            "subject": "Physics Advanced",
            "classes_count": 3,
            "students_count": 115,
            "status": "Active"
        },
        {
            "id": "TCH-2026-003",
            "name": "Alex Turner",
            "email": "a.turner@school.edu",
            "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=100&auto=format&fit=crop&q=80",
            "subject": "Computer Science & AI",
            "classes_count": 5,
            "students_count": 160,
            "status": "Active"
        },
        {
            "id": "TCH-2026-004",
            "name": "Elena Rostova",
            "email": "e.rostova@school.edu",
            "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=100&auto=format&fit=crop&q=80",
            "subject": "Organic Chemistry",
            "classes_count": 2,
            "students_count": 88,
            "status": "On Leave"
        },
        {
            "id": "TCH-2026-005",
            "name": "Robert Sterling",
            "email": "r.sterling@school.edu",
            "avatar": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=100&auto=format&fit=crop&q=80",
            "subject": "World History & Civics",
            "classes_count": 4,
            "students_count": 130,
            "status": "Active"
        }
    ]
    return jsonify({
        "status": "success",
        "total": len(teachers),
        "data": teachers
    })

# API Route to return Classes Box Data List
@app.route('/api/classes', methods=['GET'])
def get_classes_list():
    classes_data = [
        {
            "id": "CLS-101",
            "name": "Mathematics 101 - Advanced",
            "track": "STEM Track",
            "instructor": "Prof. Sarah Jenkins",
            "room": "Room 302",
            "schedule": "Mon / Wed / Fri (09:00 AM)",
            "students_count": 38,
            "pass_rate": "92%",
            "icon": "bi-calculator",
            "status": "Active"
        },
        {
            "id": "CLS-202",
            "name": "Physics Lab & Relativity",
            "track": "Science Track",
            "instructor": "Dr. Michael Vance",
            "room": "Lab 2",
            "schedule": "Tue / Thu (10:30 AM)",
            "students_count": 32,
            "pass_rate": "88%",
            "icon": "bi-lightning-charge",
            "status": "Active"
        },
        {
            "id": "CLS-303",
            "name": "Computer Science & AI Systems",
            "track": "Tech Track",
            "instructor": "Alex Turner",
            "room": "Comp Lab A",
            "schedule": "Mon - Fri (01:00 PM)",
            "students_count": 45,
            "pass_rate": "95%",
            "icon": "bi-code-slash",
            "status": "Active"
        },
        {
            "id": "CLS-404",
            "name": "Organic Chemistry Fundamentals",
            "track": "Science Track",
            "instructor": "Elena Rostova",
            "room": "Lab 1",
            "schedule": "Wed / Fri (02:30 PM)",
            "students_count": 28,
            "pass_rate": "85%",
            "icon": "bi-flask",
            "status": "Active"
        },
        {
            "id": "CLS-505",
            "name": "World History & Political Civics",
            "track": "Humanities Track",
            "instructor": "Robert Sterling",
            "room": "Room 105",
            "schedule": "Tue / Thu (08:30 AM)",
            "students_count": 40,
            "pass_rate": "90%",
            "icon": "bi-globe",
            "status": "Active"
        },
        {
            "id": "CLS-606",
            "name": "Macroeconomics & Finance",
            "track": "Business Track",
            "instructor": "Marcus Brody",
            "room": "Hall 201",
            "schedule": "Mon / Wed (11:00 AM)",
            "students_count": 35,
            "pass_rate": "87%",
            "icon": "bi-graph-up-arrow",
            "status": "Active"
        }
    ]
    return jsonify({
        "status": "success",
        "total": len(classes_data),
        "data": classes_data
    })

# API Route to return Student Scores in Class
@app.route('/api/scores', methods=['GET'])
def get_student_scores():
    scores_data = [
        {
            "id": "STD-2026-001",
            "name": "Alexander Wright",
            "avatar": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=80&auto=format&fit=crop&q=80",
            "class_name": "Mathematics 101",
            "midterm": 94,
            "final": 96,
            "assignment": 98,
            "total_score": 96.0,
            "grade": "A+",
            "status": "Passed"
        },
        {
            "id": "STD-2026-002",
            "name": "Sophia Martinez",
            "avatar": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=80&auto=format&fit=crop&q=80",
            "class_name": "Physics Advanced",
            "midterm": 88,
            "final": 92,
            "assignment": 95,
            "total_score": 91.5,
            "grade": "A",
            "status": "Passed"
        },
        {
            "id": "STD-2026-003",
            "name": "David Kim",
            "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=80&auto=format&fit=crop&q=80",
            "class_name": "Computer Science & AI",
            "midterm": 82,
            "final": 86,
            "assignment": 90,
            "total_score": 86.0,
            "grade": "B+",
            "status": "Passed"
        },
        {
            "id": "STD-2026-004",
            "name": "Emma Watson",
            "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=80&auto=format&fit=crop&q=80",
            "class_name": "Organic Chemistry",
            "midterm": 58,
            "final": 62,
            "assignment": 65,
            "total_score": 61.6,
            "grade": "D",
            "status": "Needs Review"
        },
        {
            "id": "STD-2026-005",
            "name": "Lucas Vance",
            "avatar": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=80&auto=format&fit=crop&q=80",
            "class_name": "Mathematics 101",
            "midterm": 90,
            "final": 91,
            "assignment": 93,
            "total_score": 91.3,
            "grade": "A",
            "status": "Passed"
        }
    ]
    return jsonify({
        "status": "success",
        "total": len(scores_data),
        "data": scores_data
    })

# API Route to return Students Directory List
@app.route('/api/students', methods=['GET'])
def get_students_list():
    students_data = [
        {
            "id": "STD-2026-001",
            "name": "Alexander Wright",
            "email": "alex.w@student.edu",
            "avatar": "https://images.unsplash.com/photo-1539571696357-5a69c17a67c6?w=80&auto=format&fit=crop&q=80",
            "grade": "Grade 11 - STEM",
            "gpa": "3.92",
            "attendance": "98%",
            "status": "Active"
        },
        {
            "id": "STD-2026-002",
            "name": "Sophia Martinez",
            "email": "sophia.m@student.edu",
            "avatar": "https://images.unsplash.com/photo-1517841905240-472988babdf9?w=80&auto=format&fit=crop&q=80",
            "grade": "Grade 12 - Science",
            "gpa": "3.75",
            "attendance": "94%",
            "status": "Active"
        },
        {
            "id": "STD-2026-003",
            "name": "David Kim",
            "email": "david.k@student.edu",
            "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=80&auto=format&fit=crop&q=80",
            "grade": "Grade 10 - Tech",
            "gpa": "3.40",
            "attendance": "91%",
            "status": "Active"
        },
        {
            "id": "STD-2026-004",
            "name": "Emma Watson",
            "email": "emma.w@student.edu",
            "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=80&auto=format&fit=crop&q=80",
            "grade": "Grade 11 - Arts",
            "gpa": "2.10",
            "attendance": "82%",
            "status": "Warning"
        },
        {
            "id": "STD-2026-005",
            "name": "Lucas Vance",
            "email": "lucas.v@student.edu",
            "avatar": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=80&auto=format&fit=crop&q=80",
            "grade": "Grade 12 - STEM",
            "gpa": "3.88",
            "attendance": "96%",
            "status": "Active"
        }
    ]
    return jsonify({
        "status": "success",
        "total": len(students_data),
        "data": students_data
    })

@app.route('/<path:filename>', methods=['GET'])
def serve_static(filename):
    return find_and_send_file(filename)




if __name__ == '__main__':
    app.run(host='localhost', port=3000, debug=True)