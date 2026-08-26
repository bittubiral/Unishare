"""
database.py - SQLite database initialization and all DB operations
Handles Users, Resources, Courses, Departments, Comments, Downloads, Favorites, Ratings
"""

import sqlite3
import os
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    DHAKA_TZ = ZoneInfo("Asia/Dhaka")
except Exception:
    # Fallback for environments without the IANA tz database installed —
    # Dhaka has no daylight saving, so a fixed UTC+6 offset is equivalent.
    DHAKA_TZ = timezone(timedelta(hours=6))

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "platform.db")


def bd_now() -> datetime:
    """Current date/time in Bangladesh's actual local timezone (Asia/Dhaka)."""
    return datetime.now(DHAKA_TZ).replace(tzinfo=None)


def get_connection():
    """Return a new SQLite connection with row factory."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Create all tables if they don't exist."""
    conn = get_connection()
    c = conn.cursor()

    # Departments table
    c.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            code TEXT NOT NULL UNIQUE,
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Users table
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('student','teacher','admin')),
            department_id INTEGER REFERENCES departments(id),
            semester INTEGER,
            student_id TEXT,
            is_active INTEGER DEFAULT 1,
            reputation_score INTEGER DEFAULT 100,
            warning_points INTEGER DEFAULT 0,
            suspended_until TEXT,
            suspension_reason TEXT,
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Courses table
    c.execute("""
        CREATE TABLE IF NOT EXISTS courses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            semester INTEGER NOT NULL,
            department_id INTEGER REFERENCES departments(id),
            teacher_id INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Resources table
    c.execute("""
        CREATE TABLE IF NOT EXISTS resources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            category TEXT NOT NULL CHECK(category IN
                ('lecture_note','assignment','lab_report','presentation','past_paper','book','other')),
            course_id INTEGER REFERENCES courses(id),
            semester INTEGER NOT NULL,
            uploader_id INTEGER REFERENCES users(id),
            is_approved INTEGER DEFAULT 0,
            download_count INTEGER DEFAULT 0,
            tags TEXT,
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Downloads table
    c.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            downloaded_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Comments table
    c.execute("""
        CREATE TABLE IF NOT EXISTS comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            content TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Ratings table
    c.execute("""
        CREATE TABLE IF NOT EXISTS ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5),
            created_at TEXT DEFAULT (datetime('now', '+6 hours')),
            UNIQUE(resource_id, user_id)
        )
    """)

    # Favorites table
    c.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
            user_id INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now', '+6 hours')),
            UNIQUE(resource_id, user_id)
        )
    """)

    # Teacher Ratings table (students rate teachers per course)
    c.execute("""
        CREATE TABLE IF NOT EXISTS teacher_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL REFERENCES users(id),
            student_id INTEGER NOT NULL REFERENCES users(id),
            course_id INTEGER NOT NULL REFERENCES courses(id),
            teaching_quality INTEGER NOT NULL CHECK(teaching_quality BETWEEN 1 AND 5),
            communication INTEGER NOT NULL CHECK(communication BETWEEN 1 AND 5),
            course_material INTEGER NOT NULL CHECK(course_material BETWEEN 1 AND 5),
            review TEXT,
            created_at TEXT DEFAULT (datetime('now', '+6 hours')),
            UNIQUE(teacher_id, student_id, course_id)
        )
    """)

    # Violations table — warnings and penalty points issued to users
    c.execute("""
        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            issued_by INTEGER NOT NULL REFERENCES users(id),
            violation_type TEXT NOT NULL,
            severity TEXT NOT NULL CHECK(severity IN ('minor','moderate','severe')),
            points INTEGER NOT NULL,
            description TEXT NOT NULL,
            resource_id INTEGER REFERENCES resources(id),
            comment_id INTEGER REFERENCES comments(id),
            status TEXT DEFAULT 'active' CHECK(status IN ('active','resolved','appealed')),
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Appeals table — suspended users can appeal
    c.execute("""
        CREATE TABLE IF NOT EXISTS appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            violation_id INTEGER REFERENCES violations(id),
            reason TEXT NOT NULL,
            evidence_files TEXT,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
            admin_response TEXT,
            reviewed_by INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now', '+6 hours')),
            reviewed_at TEXT
        )
    """)

    # Peer reports — students reporting each other
    c.execute("""
        CREATE TABLE IF NOT EXISTS peer_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_id INTEGER NOT NULL REFERENCES users(id),
            reported_user_id INTEGER NOT NULL REFERENCES users(id),
            report_type TEXT NOT NULL,
            description TEXT NOT NULL,
            evidence_files TEXT,
            resource_id INTEGER REFERENCES resources(id),
            comment_id INTEGER REFERENCES comments(id),
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','reviewed','dismissed','actioned')),
            reviewed_by INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Comment reports — report inappropriate comments
    c.execute("""
        CREATE TABLE IF NOT EXISTS comment_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comment_id INTEGER NOT NULL REFERENCES comments(id) ON DELETE CASCADE,
            reported_by INTEGER NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','reviewed','dismissed','actioned')),
            reviewed_by INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Rating reports — teacher reports an inappropriate anonymous student review
    c.execute("""
        CREATE TABLE IF NOT EXISTS rating_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rating_id INTEGER NOT NULL REFERENCES teacher_ratings(id) ON DELETE CASCADE,
            reported_by INTEGER NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            status TEXT DEFAULT 'pending' CHECK(status IN ('pending','reviewed','dismissed','actioned')),
            reviewed_by INTEGER REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Reputation log — track score changes over time
    c.execute("""
        CREATE TABLE IF NOT EXISTS reputation_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            change INTEGER NOT NULL,
            reason TEXT NOT NULL,
            old_score INTEGER NOT NULL,
            new_score INTEGER NOT NULL,
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Appointments table (group appointments)
    c.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            teacher_id INTEGER NOT NULL REFERENCES users(id),
            course_id INTEGER REFERENCES courses(id),
            proposed_date TEXT NOT NULL,
            proposed_time TEXT NOT NULL,
            purpose TEXT NOT NULL,
            urgency TEXT NOT NULL DEFAULT 'normal' CHECK(urgency IN ('low','normal','high')),
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK(status IN ('pending','approved','rejected','cancelled','completed')),
            teacher_note TEXT,
            created_by INTEGER NOT NULL REFERENCES users(id),
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Appointment participants (students in a group appointment)
    c.execute("""
        CREATE TABLE IF NOT EXISTS appointment_participants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL REFERENCES users(id),
            joined_at TEXT DEFAULT (datetime('now', '+6 hours')),
            UNIQUE(appointment_id, student_id)
        )
    """)

    # Cancel polls
    c.execute("""
        CREATE TABLE IF NOT EXISTS cancel_polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appointment_id INTEGER NOT NULL REFERENCES appointments(id) ON DELETE CASCADE,
            created_by INTEGER NOT NULL REFERENCES users(id),
            reason TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now', '+6 hours')),
            UNIQUE(appointment_id)
        )
    """)

    # Cancel poll votes
    c.execute("""
        CREATE TABLE IF NOT EXISTS cancel_poll_votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_id INTEGER NOT NULL REFERENCES cancel_polls(id) ON DELETE CASCADE,
            student_id INTEGER NOT NULL REFERENCES users(id),
            vote INTEGER NOT NULL CHECK(vote IN (0,1)),
            voted_at TEXT DEFAULT (datetime('now', '+6 hours')),
            UNIQUE(poll_id, student_id)
        )
    """)

    # Notifications table
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL REFERENCES users(id),
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            link TEXT,
            created_at TEXT DEFAULT (datetime('now', '+6 hours'))
        )
    """)

    # Teacher Rating Replies (teacher replies to anonymous reviews)
    c.execute("""
        CREATE TABLE IF NOT EXISTS teacher_rating_replies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rating_id INTEGER NOT NULL REFERENCES teacher_ratings(id) ON DELETE CASCADE,
            teacher_id INTEGER NOT NULL REFERENCES users(id),
            reply TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now', '+6 hours')),
            UNIQUE(rating_id)
        )
    """)

    # Seed default department and admin
    c.execute("INSERT OR IGNORE INTO departments (name, code) VALUES (?,?)",
              ("Computer Science & Engineering", "CSE"))
    c.execute("INSERT OR IGNORE INTO departments (name, code) VALUES (?,?)",
              ("Electrical & Electronic Engineering", "EEE"))
    c.execute("INSERT OR IGNORE INTO departments (name, code) VALUES (?,?)",
              ("Business Administration", "BBA"))

    # Auto-migrate: add evidence_files to appeals/peer_reports if this DB was
    # created before evidence uploads existed (CREATE TABLE IF NOT EXISTS
    # above won't retroactively add columns to an already-existing table).
    for table in ("appeals", "peer_reports"):
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN evidence_files TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

    conn.commit()
    conn.close()


# ── USER OPERATIONS ──────────────────────────────────────────────────────────

def create_user(name, email, password_hash, role, department_id, semester=None, student_id=None):
    """
    Create a new user.
    SAFETY NET: if this is the very first user ever created on the platform,
    they are automatically promoted to 'admin' regardless of the role they
    picked during signup. This guarantees there is always at least one admin
    even if the database was wiped or never seeded.
    """
    conn = get_connection()
    try:
        existing_count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        final_role = "admin" if existing_count == 0 else role

        conn.execute(
            "INSERT INTO users (name,email,password_hash,role,department_id,semester,student_id) VALUES (?,?,?,?,?,?,?)",
            (name, email, password_hash, final_role, department_id, semester, student_id)
        )
        conn.commit()

        if final_role == "admin" and role != "admin":
            return True, "🎉 You're the first user — your account has been made an Admin automatically!"
        return True, "Account created successfully!"
    except sqlite3.IntegrityError:
        return False, "Email already registered."
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_users():
    conn = get_connection()
    rows = conn.execute("""
        SELECT u.*, d.name as dept_name
        FROM users u LEFT JOIN departments d ON u.department_id=d.id
        ORDER BY u.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def toggle_user_active(user_id, is_active):
    conn = get_connection()
    conn.execute("UPDATE users SET is_active=? WHERE id=?", (is_active, user_id))
    conn.commit()
    conn.close()


def update_user_role(user_id, role):
    conn = get_connection()
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, user_id))
    conn.commit()
    conn.close()


# ── DEPARTMENT OPERATIONS ────────────────────────────────────────────────────

def get_departments():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM departments ORDER BY name").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_department(name, code):
    conn = get_connection()
    try:
        conn.execute("INSERT INTO departments (name, code) VALUES (?,?)", (name, code))
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# ── COURSE OPERATIONS ────────────────────────────────────────────────────────

def get_courses(department_id=None):
    conn = get_connection()
    if department_id:
        rows = conn.execute("""
            SELECT c.*, d.name as dept_name, u.name as teacher_name
            FROM courses c
            LEFT JOIN departments d ON c.department_id=d.id
            LEFT JOIN users u ON c.teacher_id=u.id
            WHERE c.department_id=?
            ORDER BY c.semester, c.code
        """, (department_id,)).fetchall()
    else:
        rows = conn.execute("""
            SELECT c.*, d.name as dept_name, u.name as teacher_name
            FROM courses c
            LEFT JOIN departments d ON c.department_id=d.id
            LEFT JOIN users u ON c.teacher_id=u.id
            ORDER BY c.semester, c.code
        """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_course(code, name, semester, department_id, teacher_id=None):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO courses (code,name,semester,department_id,teacher_id) VALUES (?,?,?,?,?)",
            (code, name, semester, department_id, teacher_id)
        )
        conn.commit()
        return True, "Course added."
    except sqlite3.IntegrityError:
        return False, "Course code already exists."
    finally:
        conn.close()


def get_course_by_id(course_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM courses WHERE id=?", (course_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── RESOURCE OPERATIONS ──────────────────────────────────────────────────────

def add_resource(title, description, file_name, file_path, file_type, file_size,
                 category, course_id, semester, uploader_id, tags=""):
    """Auto-approve for teachers/admins; pending for students."""
    conn = get_connection()
    uploader = conn.execute("SELECT role FROM users WHERE id=?", (uploader_id,)).fetchone()
    is_approved = 1 if uploader and uploader["role"] in ("teacher", "admin") else 0
    conn.execute("""
        INSERT INTO resources
        (title,description,file_name,file_path,file_type,file_size,category,course_id,semester,uploader_id,is_approved,tags)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (title, description, file_name, file_path, file_type, file_size,
          category, course_id, semester, uploader_id, is_approved, tags))
    conn.commit()
    conn.close()


def get_resources(semester=None, course_id=None, category=None, uploader_id=None,
                  search_query=None, approved_only=True, limit=None):
    conn = get_connection()
    query = """
        SELECT r.*, u.name as uploader_name, u.role as uploader_role,
               c.code as course_code, c.name as course_name,
               COALESCE(AVG(rt.score),0) as avg_rating,
               COUNT(DISTINCT rt.id) as rating_count
        FROM resources r
        LEFT JOIN users u ON r.uploader_id=u.id
        LEFT JOIN courses c ON r.course_id=c.id
        LEFT JOIN ratings rt ON r.id=rt.resource_id
        WHERE 1=1
    """
    params = []
    if approved_only:
        query += " AND r.is_approved=1"
    if semester:
        query += " AND r.semester=?"
        params.append(semester)
    if course_id:
        query += " AND r.course_id=?"
        params.append(course_id)
    if category:
        query += " AND r.category=?"
        params.append(category)
    if uploader_id:
        query += " AND r.uploader_id=?"
        params.append(uploader_id)
    if search_query:
        query += " AND (r.title LIKE ? OR r.description LIKE ? OR r.tags LIKE ? OR c.code LIKE ?)"
        q = f"%{search_query}%"
        params.extend([q, q, q, q])
    query += " GROUP BY r.id ORDER BY r.created_at DESC"
    if limit:
        query += f" LIMIT {limit}"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_resource_by_id(resource_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT r.*, u.name as uploader_name, c.code as course_code, c.name as course_name,
               COALESCE(AVG(rt.score),0) as avg_rating, COUNT(DISTINCT rt.id) as rating_count
        FROM resources r
        LEFT JOIN users u ON r.uploader_id=u.id
        LEFT JOIN courses c ON r.course_id=c.id
        LEFT JOIN ratings rt ON r.id=rt.resource_id
        WHERE r.id=?
        GROUP BY r.id
    """, (resource_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def approve_resource(resource_id):
    conn = get_connection()
    conn.execute("UPDATE resources SET is_approved=1 WHERE id=?", (resource_id,))
    conn.commit()
    conn.close()


def delete_resource(resource_id):
    conn = get_connection()
    row = conn.execute("SELECT file_path FROM resources WHERE id=?", (resource_id,)).fetchone()
    if row:
        try:
            os.remove(row["file_path"])
        except FileNotFoundError:
            pass
    conn.execute("DELETE FROM resources WHERE id=?", (resource_id,))
    conn.commit()
    conn.close()


def increment_download(resource_id, user_id):
    conn = get_connection()
    conn.execute("UPDATE resources SET download_count=download_count+1 WHERE id=?", (resource_id,))
    conn.execute("INSERT INTO downloads (resource_id,user_id) VALUES (?,?)", (resource_id, user_id))
    conn.commit()
    conn.close()


def get_pending_resources():
    conn = get_connection()
    rows = conn.execute("""
        SELECT r.*, u.name as uploader_name, c.code as course_code, c.name as course_name
        FROM resources r
        LEFT JOIN users u ON r.uploader_id=u.id
        LEFT JOIN courses c ON r.course_id=c.id
        WHERE r.is_approved=0
        ORDER BY r.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── COMMENT OPERATIONS ───────────────────────────────────────────────────────

def add_comment(resource_id, user_id, content):
    conn = get_connection()
    conn.execute("INSERT INTO comments (resource_id,user_id,content) VALUES (?,?,?)",
                 (resource_id, user_id, content))
    conn.commit()
    conn.close()


def get_comments(resource_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT cm.*, u.name as user_name, u.role as user_role
        FROM comments cm JOIN users u ON cm.user_id=u.id
        WHERE cm.resource_id=?
        ORDER BY cm.created_at ASC
    """, (resource_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_comment(comment_id):
    conn = get_connection()
    conn.execute("DELETE FROM comments WHERE id=?", (comment_id,))
    conn.commit()
    conn.close()


# ── RATING OPERATIONS ────────────────────────────────────────────────────────

def upsert_rating(resource_id, user_id, score):
    conn = get_connection()
    conn.execute("""
        INSERT INTO ratings (resource_id, user_id, score) VALUES (?,?,?)
        ON CONFLICT(resource_id, user_id) DO UPDATE SET score=excluded.score
    """, (resource_id, user_id, score))
    conn.commit()
    conn.close()


def get_user_rating(resource_id, user_id):
    conn = get_connection()
    row = conn.execute("SELECT score FROM ratings WHERE resource_id=? AND user_id=?",
                       (resource_id, user_id)).fetchone()
    conn.close()
    return row["score"] if row else None


# ── FAVORITES OPERATIONS ─────────────────────────────────────────────────────

def toggle_favorite(resource_id, user_id):
    conn = get_connection()
    existing = conn.execute("SELECT id FROM favorites WHERE resource_id=? AND user_id=?",
                            (resource_id, user_id)).fetchone()
    if existing:
        conn.execute("DELETE FROM favorites WHERE resource_id=? AND user_id=?",
                     (resource_id, user_id))
        result = False
    else:
        conn.execute("INSERT INTO favorites (resource_id, user_id) VALUES (?,?)",
                     (resource_id, user_id))
        result = True
    conn.commit()
    conn.close()
    return result


def is_favorited(resource_id, user_id):
    conn = get_connection()
    row = conn.execute("SELECT id FROM favorites WHERE resource_id=? AND user_id=?",
                       (resource_id, user_id)).fetchone()
    conn.close()
    return row is not None


def get_user_favorites(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT r.*, u.name as uploader_name, c.code as course_code, c.name as course_name,
               COALESCE(AVG(rt.score),0) as avg_rating
        FROM favorites f
        JOIN resources r ON f.resource_id=r.id
        LEFT JOIN users u ON r.uploader_id=u.id
        LEFT JOIN courses c ON r.course_id=c.id
        LEFT JOIN ratings rt ON r.id=rt.resource_id
        WHERE f.user_id=? AND r.is_approved=1
        GROUP BY r.id
        ORDER BY f.created_at DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── ANALYTICS ────────────────────────────────────────────────────────────────

def get_stats():
    conn = get_connection()
    stats = {}
    stats["total_users"] = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    stats["total_resources"] = conn.execute("SELECT COUNT(*) FROM resources WHERE is_approved=1").fetchone()[0]
    stats["pending_resources"] = conn.execute("SELECT COUNT(*) FROM resources WHERE is_approved=0").fetchone()[0]
    stats["total_downloads"] = conn.execute("SELECT COUNT(*) FROM downloads").fetchone()[0]
    stats["total_courses"] = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
    stats["total_comments"] = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]

    # Downloads per day (last 7 days)
    stats["daily_downloads"] = conn.execute("""
        SELECT DATE(downloaded_at) as day, COUNT(*) as cnt
        FROM downloads
        WHERE downloaded_at >= DATE('now','-7 days')
        GROUP BY day ORDER BY day
    """).fetchall()

    # Resources per category
    stats["by_category"] = conn.execute("""
        SELECT category, COUNT(*) as cnt FROM resources
        WHERE is_approved=1 GROUP BY category
    """).fetchall()

    # Top resources
    stats["top_resources"] = conn.execute("""
        SELECT r.title, r.download_count, c.code as course_code
        FROM resources r LEFT JOIN courses c ON r.course_id=c.id
        WHERE r.is_approved=1
        ORDER BY r.download_count DESC LIMIT 5
    """).fetchall()

    # Storage used
    total_size = conn.execute("SELECT COALESCE(SUM(file_size),0) FROM resources WHERE is_approved=1").fetchone()[0]
    stats["storage_mb"] = round(total_size / (1024 * 1024), 2)

    conn.close()
    return stats


# ── TEACHER RATING OPERATIONS ────────────────────────────────────────────────

def get_teachers():
    """Get all teachers for rating selection."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT u.id, u.name, u.department_id, d.name as dept_name
        FROM users u
        LEFT JOIN departments d ON u.department_id = d.id
        WHERE u.role = 'teacher' AND u.is_active = 1
        ORDER BY u.name
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def submit_teacher_rating(teacher_id, student_id, course_id,
                           teaching_quality, communication, course_material, review=""):
    """Submit or update a student's rating for a teacher in a course.
    Notifies the teacher — WITHOUT revealing the student's identity,
    since ratings are anonymous."""
    conn = get_connection()
    try:
        # Detect whether this is a brand-new rating or an update to an existing one
        existing = conn.execute(
            "SELECT id FROM teacher_ratings WHERE teacher_id=? AND student_id=? AND course_id=?",
            (teacher_id, student_id, course_id)
        ).fetchone()
        is_new = existing is None

        conn.execute("""
            INSERT INTO teacher_ratings
            (teacher_id, student_id, course_id, teaching_quality, communication, course_material, review)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(teacher_id, student_id, course_id)
            DO UPDATE SET
                teaching_quality=excluded.teaching_quality,
                communication=excluded.communication,
                course_material=excluded.course_material,
                review=excluded.review,
                created_at=datetime('now', '+6 hours')
        """, (teacher_id, student_id, course_id,
              teaching_quality, communication, course_material, review))
        conn.commit()

        course = conn.execute("SELECT code, name FROM courses WHERE id=?", (course_id,)).fetchone()
        course_label = f"{course['code']} — {course['name']}" if course else "a course"
        conn.close()

        if is_new:
            add_notification(teacher_id,
                             f"🌟 You received a new anonymous rating for {course_label}.",
                             link="my_ratings")
        else:
            add_notification(teacher_id,
                             f"✏️ A student updated their anonymous rating for {course_label}.",
                             link="my_ratings")

        return True, "Rating submitted successfully!"
    except Exception as e:
        conn.close()
        return False, str(e)


def get_student_existing_rating(teacher_id, student_id, course_id):
    """Check if student already rated this teacher for this course."""
    conn = get_connection()
    row = conn.execute("""
        SELECT * FROM teacher_ratings
        WHERE teacher_id=? AND student_id=? AND course_id=?
    """, (teacher_id, student_id, course_id)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_teacher_rating_summary(teacher_id):
    """Get average scores for a teacher across all courses (no student names)."""
    conn = get_connection()
    summary = conn.execute("""
        SELECT
            COUNT(*) as total_ratings,
            ROUND(AVG(teaching_quality), 1) as avg_teaching,
            ROUND(AVG(communication), 1) as avg_communication,
            ROUND(AVG(course_material), 1) as avg_material,
            ROUND((AVG(teaching_quality)+AVG(communication)+AVG(course_material))/3.0, 1) as overall_avg
        FROM teacher_ratings
        WHERE teacher_id=?
    """, (teacher_id,)).fetchone()
    conn.close()
    return dict(summary) if summary else {}


def get_teacher_reviews(teacher_id):
    """
    Get all reviews for a teacher.
    - Student name is HIDDEN (anonymous)
    - Shows course name, scores, review text, and teacher reply
    Uses LEFT JOIN on courses so a rating is never silently dropped
    even if its course was later deleted/changed.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            tr.id,
            tr.teaching_quality,
            tr.communication,
            tr.course_material,
            tr.review,
            tr.created_at,
            COALESCE(c.code, '—') as course_code,
            COALESCE(c.name, 'Unknown course') as course_name,
            trr.reply as teacher_reply,
            trr.created_at as reply_date
        FROM teacher_ratings tr
        LEFT JOIN courses c ON tr.course_id = c.id
        LEFT JOIN teacher_rating_replies trr ON tr.id = trr.rating_id
        WHERE tr.teacher_id = ?
        ORDER BY tr.created_at DESC
    """, (teacher_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_teacher_reviews_admin(teacher_id):
    """
    Admin view — same as above but SHOWS student name.
    Also uses LEFT JOIN on courses for the same reason.
    """
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            tr.id,
            tr.teaching_quality,
            tr.communication,
            tr.course_material,
            tr.review,
            tr.created_at,
            COALESCE(c.code, '—') as course_code,
            COALESCE(c.name, 'Unknown course') as course_name,
            u.name as student_name,
            u.student_id as student_roll,
            trr.reply as teacher_reply,
            trr.created_at as reply_date
        FROM teacher_ratings tr
        LEFT JOIN courses c ON tr.course_id = c.id
        JOIN users u ON tr.student_id = u.id
        LEFT JOIN teacher_rating_replies trr ON tr.id = trr.rating_id
        WHERE tr.teacher_id = ?
        ORDER BY tr.created_at DESC
    """, (teacher_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def add_teacher_reply(rating_id, teacher_id, reply):
    """Teacher replies to an anonymous review."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO teacher_rating_replies (rating_id, teacher_id, reply)
            VALUES (?,?,?)
            ON CONFLICT(rating_id) DO UPDATE SET reply=excluded.reply, created_at=datetime('now', '+6 hours')
        """, (rating_id, teacher_id, reply))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_all_teacher_ratings_admin():
    """Admin: see all teacher ratings with student names."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT
            tr.*,
            t.name as teacher_name,
            u.name as student_name,
            COALESCE(c.code, '—') as course_code,
            COALESCE(c.name, 'Unknown course') as course_name
        FROM teacher_ratings tr
        JOIN users t ON tr.teacher_id = t.id
        JOIN users u ON tr.student_id = u.id
        LEFT JOIN courses c ON tr.course_id = c.id
        ORDER BY tr.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── NOTIFICATION OPERATIONS ───────────────────────────────────────────────────

def add_notification(user_id, message, link=None):
    conn = get_connection()
    conn.execute("INSERT INTO notifications (user_id, message, link) VALUES (?,?,?)",
                 (user_id, message, link))
    conn.commit()
    conn.close()


def get_notifications(user_id, unread_only=False):
    conn = get_connection()
    q = "SELECT * FROM notifications WHERE user_id=?"
    if unread_only:
        q += " AND is_read=0"
    q += " ORDER BY created_at DESC, id DESC LIMIT 20"
    rows = conn.execute(q, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def mark_notifications_read(user_id):
    conn = get_connection()
    conn.execute("UPDATE notifications SET is_read=1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_unread_count(user_id):
    conn = get_connection()
    count = conn.execute(
        "SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (user_id,)
    ).fetchone()[0]
    conn.close()
    return count


# ── APPOINTMENT OPERATIONS ────────────────────────────────────────────────────

def create_appointment(title, description, teacher_id, course_id, proposed_date,
                       proposed_time, purpose, urgency, created_by):
    """Create a group appointment and auto-add creator as first participant."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO appointments
        (title, description, teacher_id, course_id, proposed_date,
         proposed_time, purpose, urgency, created_by)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (title, description, teacher_id, course_id, proposed_date,
          proposed_time, purpose, urgency, created_by))
    appt_id = c.lastrowid
    # Auto-join creator
    c.execute("INSERT OR IGNORE INTO appointment_participants (appointment_id, student_id) VALUES (?,?)",
              (appt_id, created_by))
    conn.commit()
    conn.close()

    # Notify teacher
    teacher = get_user_by_id(teacher_id)
    creator = get_user_by_id(created_by)
    if teacher and creator:
        add_notification(teacher_id,
                         f"📅 New appointment request: '{title}' from {creator['name']}",
                         link="appointments")
    return appt_id


def get_appointments_for_teacher(teacher_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, u.name as creator_name, c.code as course_code,
               COUNT(DISTINCT ap.student_id) as participant_count
        FROM appointments a
        LEFT JOIN users u ON a.created_by = u.id
        LEFT JOIN courses c ON a.course_id = c.id
        LEFT JOIN appointment_participants ap ON a.id = ap.appointment_id
        WHERE a.teacher_id = ?
        GROUP BY a.id
        ORDER BY a.proposed_date DESC, a.proposed_time DESC
    """, (teacher_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_appointments_for_student(student_id):
    """All appointments the student created or joined."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, u.name as teacher_name, c.code as course_code,
               COUNT(DISTINCT ap.student_id) as participant_count
        FROM appointments a
        LEFT JOIN users u ON a.teacher_id = u.id
        LEFT JOIN courses c ON a.course_id = c.id
        LEFT JOIN appointment_participants ap ON a.id = ap.appointment_id
        WHERE a.id IN (
            SELECT appointment_id FROM appointment_participants WHERE student_id=?
        ) OR a.created_by = ?
        GROUP BY a.id
        ORDER BY a.proposed_date DESC, a.proposed_time DESC
    """, (student_id, student_id)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_appointments():
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, t.name as teacher_name, u.name as creator_name,
               c.code as course_code,
               COUNT(DISTINCT ap.student_id) as participant_count
        FROM appointments a
        LEFT JOIN users t ON a.teacher_id = t.id
        LEFT JOIN users u ON a.created_by = u.id
        LEFT JOIN courses c ON a.course_id = c.id
        LEFT JOIN appointment_participants ap ON a.id = ap.appointment_id
        GROUP BY a.id
        ORDER BY a.proposed_date DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_appointment_by_id(appt_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT a.*, t.name as teacher_name, u.name as creator_name,
               c.code as course_code, c.name as course_name
        FROM appointments a
        LEFT JOIN users t ON a.teacher_id = t.id
        LEFT JOIN users u ON a.created_by = u.id
        LEFT JOIN courses c ON a.course_id = c.id
        WHERE a.id = ?
    """, (appt_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_appointment_status(appt_id, status, teacher_note=""):
    conn = get_connection()
    conn.execute("UPDATE appointments SET status=?, teacher_note=? WHERE id=?",
                 (status, teacher_note, appt_id))
    conn.commit()

    # Notify all participants
    appt = conn.execute("SELECT * FROM appointments WHERE id=?", (appt_id,)).fetchone()
    participants = conn.execute(
        "SELECT student_id FROM appointment_participants WHERE appointment_id=?",
        (appt_id,)
    ).fetchall()
    conn.close()

    if appt:
        status_msg = {
            "approved": "✅ Appointment approved",
            "rejected": "❌ Appointment rejected",
            "cancelled": "🚫 Appointment cancelled",
            "completed": "🎓 Appointment marked complete"
        }.get(status, f"Appointment status: {status}")

        for p in participants:
            add_notification(p["student_id"],
                             f"{status_msg}: '{appt['title']}'",
                             link="appointments")


def join_appointment(appt_id, student_id):
    """Student joins an existing group appointment."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO appointment_participants (appointment_id, student_id) VALUES (?,?)",
            (appt_id, student_id)
        )
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        conn.close()


def get_participants(appt_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT u.id, u.name, u.student_id as roll, u.semester
        FROM appointment_participants ap
        JOIN users u ON ap.student_id = u.id
        WHERE ap.appointment_id = ?
    """, (appt_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def is_participant(appt_id, student_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT id FROM appointment_participants WHERE appointment_id=? AND student_id=?",
        (appt_id, student_id)
    ).fetchone()
    conn.close()
    return row is not None


# ── CANCEL POLL OPERATIONS ────────────────────────────────────────────────────

def create_cancel_poll(appt_id, created_by, reason):
    """Start a cancel poll for an appointment."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO cancel_polls (appointment_id, created_by, reason) VALUES (?,?,?)",
            (appt_id, created_by, reason)
        )
        conn.commit()

        # Notify all other participants to vote
        participants = conn.execute(
            "SELECT student_id FROM appointment_participants WHERE appointment_id=? AND student_id!=?",
            (appt_id, created_by)
        ).fetchall()
        appt = conn.execute("SELECT title, teacher_id FROM appointments WHERE id=?",
                            (appt_id,)).fetchone()
        creator = get_user_by_id(created_by)

        if appt and creator:
            msg = f"🗳️ Cancel poll started for '{appt['title']}' by {creator['name']}. Vote now!"
            for p in participants:
                add_notification(p["student_id"], msg, link="appointments")
            # Notify teacher too
            add_notification(appt["teacher_id"],
                             f"🗳️ Students started a cancel poll for '{appt['title']}'",
                             link="appointments")
        return True, "Poll started!"
    except Exception:
        return False, "A poll already exists for this appointment."
    finally:
        conn.close()


def get_cancel_poll(appt_id):
    conn = get_connection()
    row = conn.execute("""
        SELECT cp.*, u.name as creator_name,
               COUNT(DISTINCT cpv.id) as total_votes,
               SUM(CASE WHEN cpv.vote=1 THEN 1 ELSE 0 END) as yes_votes,
               SUM(CASE WHEN cpv.vote=0 THEN 1 ELSE 0 END) as no_votes
        FROM cancel_polls cp
        LEFT JOIN users u ON cp.created_by = u.id
        LEFT JOIN cancel_poll_votes cpv ON cp.id = cpv.poll_id
        WHERE cp.appointment_id = ?
        GROUP BY cp.id
    """, (appt_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def submit_poll_vote(poll_id, student_id, vote):
    """Vote on a cancel poll (1=Yes cancel, 0=No keep)."""
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO cancel_poll_votes (poll_id, student_id, vote) VALUES (?,?,?)
            ON CONFLICT(poll_id, student_id) DO UPDATE SET vote=excluded.vote
        """, (poll_id, student_id, vote))
        conn.commit()

        # Check if majority reached → auto cancel
        poll = conn.execute("""
            SELECT cp.appointment_id,
                   COUNT(DISTINCT ap.student_id) as total_participants,
                   SUM(CASE WHEN cpv.vote=1 THEN 1 ELSE 0 END) as yes_votes
            FROM cancel_polls cp
            JOIN appointment_participants ap ON cp.appointment_id = ap.appointment_id
            LEFT JOIN cancel_poll_votes cpv ON cp.id = cpv.poll_id
            WHERE cp.id = ?
            GROUP BY cp.id
        """, (poll_id,)).fetchone()

        if poll:
            total = poll["total_participants"] or 1
            yes = poll["yes_votes"] or 0
            if yes / total > 0.5:
                # Majority reached — cancel appointment
                appt_id = poll["appointment_id"]
                conn.execute(
                    "UPDATE appointments SET status='cancelled' WHERE id=?", (appt_id,)
                )
                conn.execute(
                    "UPDATE cancel_polls SET is_active=0 WHERE id=?", (poll_id,)
                )
                conn.commit()

                # Notify all
                appt = conn.execute(
                    "SELECT title, teacher_id FROM appointments WHERE id=?", (appt_id,)
                ).fetchone()
                participants = conn.execute(
                    "SELECT student_id FROM appointment_participants WHERE appointment_id=?",
                    (appt_id,)
                ).fetchall()
                if appt:
                    msg = f"🚫 Appointment '{appt['title']}' cancelled by majority vote ({yes}/{total})"
                    for p in participants:
                        add_notification(p["student_id"], msg, link="appointments")
                    add_notification(appt["teacher_id"], msg, link="appointments")

                conn.close()
                return True, "voted", True  # voted, majority_reached=True

        conn.close()
        return True, "voted", False
    except Exception as e:
        conn.close()
        return False, str(e), False


def get_student_vote(poll_id, student_id):
    conn = get_connection()
    row = conn.execute(
        "SELECT vote FROM cancel_poll_votes WHERE poll_id=? AND student_id=?",
        (poll_id, student_id)
    ).fetchone()
    conn.close()
    return row["vote"] if row else None


# ── PENALTY & REPUTATION OPERATIONS ─────────────────────────────────────────

VIOLATION_POINTS = {"minor": 1, "moderate": 3, "severe": 5}
REPUTATION_DEDUCTION = {"minor": 5, "moderate": 15, "severe": 25}

VIOLATION_TYPES = {
    "misleading_resource":   ("Misleading/Incorrect Resource", "moderate"),
    "copyrighted_content":   ("Copyrighted/Prohibited Content", "severe"),
    "harassment":            ("Harassment or Bullying", "moderate"),
    "spam":                  ("Spam or Advertising", "minor"),
    "fake_report":           ("Fake Report Against User", "moderate"),
    "personal_info":         ("Sharing Personal Information", "severe"),
    "repeated_offense":      ("Repeated Offense", "severe"),
    "other":                 ("Other Violation", "minor"),
}

# Categories a peer (student/teacher) can report someone for. Labels are
# pulled straight from VIOLATION_TYPES so a report's stated category always
# matches a real violation type 1:1 instead of a separately-worded list that
# can't be mapped back to it later.
REPORTABLE_VIOLATION_KEYS = [
    "misleading_resource", "copyrighted_content", "harassment",
    "spam", "personal_info", "fake_report", "other",
]
REPORT_TYPE_OPTIONS = [VIOLATION_TYPES[k][0] for k in REPORTABLE_VIOLATION_KEYS]


def violation_type_from_label(label):
    """Map a violation/report type label back to its internal VIOLATION_TYPES key."""
    for key, (lbl, _sev) in VIOLATION_TYPES.items():
        if lbl == label:
            return key
    return "other"


def get_reputation_badge(score):
    """Return badge emoji and label based on reputation score."""
    if score >= 100:
        return "🏆", "Trusted Member"
    elif score >= 80:
        return "⭐", "Good Standing"
    elif score >= 60:
        return "🔵", "Regular Member"
    elif score >= 40:
        return "⚠️", "At Risk"
    else:
        return "🔴", "Restricted"


def get_user_penalty_status(user_id):
    """Get full penalty status for a user."""
    conn = get_connection()
    row = conn.execute("""
        SELECT reputation_score, warning_points, suspended_until,
               suspension_reason, is_active
        FROM users WHERE id=?
    """, (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else {}


def issue_violation(user_id, issued_by, violation_type, description,
                    resource_id=None, comment_id=None):
    """
    Issue a violation to a user.
    Auto-applies suspension if points reach threshold.
    """
    from datetime import timedelta

    severity = VIOLATION_TYPES.get(violation_type, ("Other", "minor"))[1]
    points = VIOLATION_POINTS[severity]
    rep_deduction = REPUTATION_DEDUCTION[severity]

    conn = get_connection()

    # Get current user state
    user = conn.execute(
        "SELECT warning_points, reputation_score, name FROM users WHERE id=?",
        (user_id,)
    ).fetchone()
    if not user:
        conn.close()
        return False, "User not found."

    old_points = user["warning_points"]
    new_points = old_points + points
    old_rep = user["reputation_score"]
    new_rep = max(0, old_rep - rep_deduction)

    # Determine auto-suspension
    suspended_until = None
    suspension_reason = None
    is_active = 1

    if new_points >= 15:
        is_active = 0
        suspension_reason = f"Permanent ban: accumulated {new_points} warning points"
        add_notification(user_id,
                         "🚫 Your account has been permanently banned due to repeated violations. "
                         "You may submit an appeal.",
                         link="my_profile")
    elif new_points >= 10:
        suspended_until = (bd_now() + timedelta(days=7)).strftime("%Y-%m-%d")
        suspension_reason = f"7-day suspension: accumulated {new_points} warning points"
        add_notification(user_id,
                         f"⚠️ Your account has been suspended for 7 days due to violations. "
                         f"Suspension lifts on {suspended_until}. You may appeal.",
                         link="my_profile")

    # Insert violation record
    conn.execute("""
        INSERT INTO violations
        (user_id, issued_by, violation_type, severity, points, description,
         resource_id, comment_id)
        VALUES (?,?,?,?,?,?,?,?)
    """, (user_id, issued_by, violation_type, severity, points, description,
          resource_id, comment_id))

    # Update user
    conn.execute("""
        UPDATE users SET
            warning_points=?,
            reputation_score=?,
            suspended_until=?,
            suspension_reason=?,
            is_active=?
        WHERE id=?
    """, (new_points, new_rep, suspended_until, suspension_reason, is_active, user_id))

    # Log reputation change
    conn.execute("""
        INSERT INTO reputation_log (user_id, change, reason, old_score, new_score)
        VALUES (?,?,?,?,?)
    """, (user_id, -rep_deduction,
          f"Violation: {VIOLATION_TYPES.get(violation_type, ('Other','minor'))[0]}",
          old_rep, new_rep))

    conn.commit()
    conn.close()

    # Notify user of violation
    add_notification(user_id,
                     f"⚠️ You received a {severity} violation: "
                     f"{VIOLATION_TYPES.get(violation_type, ('Other','minor'))[0]}. "
                     f"-{rep_deduction} reputation, +{points} warning points.",
                     link="my_profile")

    msg = f"Violation issued. User now has {new_points} warning points."
    if suspended_until:
        msg += f" User suspended until {suspended_until}."
    elif not is_active:
        msg += " User permanently banned."
    return True, msg


def get_user_violations(user_id, active_only=False):
    """Get all violations for a user."""
    conn = get_connection()
    q = """
        SELECT v.*, u.name as issued_by_name
        FROM violations v
        JOIN users u ON v.issued_by = u.id
        WHERE v.user_id=?
    """
    if active_only:
        q += " AND v.status='active'"
    q += " ORDER BY v.created_at DESC, v.id DESC"
    rows = conn.execute(q, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_violations():
    """Admin: get all violations."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT v.*, u.name as user_name, u.role as user_role,
               ib.name as issued_by_name
        FROM violations v
        JOIN users u ON v.user_id = u.id
        JOIN users ib ON v.issued_by = ib.id
        ORDER BY v.created_at DESC, v.id DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def resolve_violation(violation_id):
    conn = get_connection()
    conn.execute("UPDATE violations SET status='resolved' WHERE id=?", (violation_id,))
    conn.commit()
    conn.close()


def reduce_warning_points(user_id, points_to_remove, reason, admin_id, rep_restore=None):
    """
    Admin manually reduces warning points, optionally restoring a specific
    reputation amount (rep_restore). When rep_restore is omitted this is a
    generic manual adjustment and falls back to the old 3x-per-point rule;
    callers that are undoing a *specific* violation (e.g. an approved appeal)
    should always pass the exact reputation amount that violation deducted,
    so the notification and the reputation history log agree with each other.
    """
    conn = get_connection()
    user = conn.execute(
        "SELECT warning_points, reputation_score FROM users WHERE id=?", (user_id,)
    ).fetchone()
    if not user:
        conn.close()
        return

    new_points = max(0, user["warning_points"] - points_to_remove)
    rep_gain = rep_restore if rep_restore is not None else points_to_remove * 3
    new_rep = min(100, user["reputation_score"] + rep_gain)

    conn.execute(
        "UPDATE users SET warning_points=?, reputation_score=?, "
        "suspended_until=NULL, suspension_reason=NULL, is_active=1 WHERE id=?",
        (new_points, new_rep, user_id)
    )
    conn.execute("""
        INSERT INTO reputation_log (user_id, change, reason, old_score, new_score)
        VALUES (?,?,?,?,?)
    """, (user_id, rep_gain, f"Admin adjustment: {reason}",
          user["reputation_score"], new_rep))
    conn.commit()
    conn.close()
    add_notification(user_id,
                     f"✅ Your warning points were reduced by {points_to_remove} and your "
                     f"reputation score was restored by {rep_gain}. Reason: {reason}",
                     link="my_profile")


def get_reputation_log(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM reputation_log WHERE user_id=?
        ORDER BY created_at DESC, id DESC LIMIT 20
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── APPEAL OPERATIONS ─────────────────────────────────────────────────────────

def submit_appeal(user_id, violation_id, reason, evidence_files=""):
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO appeals (user_id, violation_id, reason, evidence_files) VALUES (?,?,?,?)",
            (user_id, violation_id, reason, evidence_files)
        )
        conn.execute(
            "UPDATE violations SET status='appealed' WHERE id=?", (violation_id,)
        )
        conn.commit()

        # Notify all admins
        admins = conn.execute(
            "SELECT id FROM users WHERE role='admin'"
        ).fetchall()
        user = conn.execute("SELECT name FROM users WHERE id=?", (user_id,)).fetchone()
        for admin in admins:
            add_notification(admin["id"],
                             f"📋 Appeal submitted by {user['name'] if user else 'a user'}",
                             link="admin_appeals")
        conn.close()
        return True, "Appeal submitted. Admin will review it."
    except Exception as e:
        conn.close()
        return False, str(e)


def get_appeals(status=None):
    conn = get_connection()
    q = """
        SELECT a.*, u.name as user_name, u.email as user_email,
               u.warning_points, u.reputation_score,
               v.violation_type, v.severity, v.description as violation_desc,
               rv.name as reviewer_name
        FROM appeals a
        JOIN users u ON a.user_id = u.id
        LEFT JOIN violations v ON a.violation_id = v.id
        LEFT JOIN users rv ON a.reviewed_by = rv.id
        WHERE 1=1
    """
    params = []
    if status:
        q += " AND a.status=?"
        params.append(status)
    q += " ORDER BY a.created_at DESC, a.id DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_user_appeals(user_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, v.violation_type, v.severity, v.points
        FROM appeals a
        LEFT JOIN violations v ON a.violation_id = v.id
        WHERE a.user_id=?
        ORDER BY a.created_at DESC, a.id DESC
    """, (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def review_appeal(appeal_id, admin_id, decision, response):
    """Admin approves or rejects an appeal."""
    conn = get_connection()
    conn.execute("""
        UPDATE appeals SET status=?, admin_response=?, reviewed_by=?, reviewed_at=?
        WHERE id=?
    """, (decision, response, admin_id, bd_now().strftime("%Y-%m-%d %H:%M"),
          appeal_id))

    appeal = conn.execute("SELECT * FROM appeals WHERE id=?", (appeal_id,)).fetchone()
    violation = None
    if appeal and appeal["violation_id"]:
        violation = conn.execute(
            "SELECT * FROM violations WHERE id=?", (appeal["violation_id"],)
        ).fetchone()

        # Flip the violation's own status so the student's "awaiting review"
        # message actually clears once an admin has made a decision.
        if decision == "approved":
            conn.execute("UPDATE violations SET status='resolved' WHERE id=?",
                        (violation["id"],))
        else:
            conn.execute("UPDATE violations SET status='active' WHERE id=?",
                        (violation["id"],))

    conn.commit()
    conn.close()

    if appeal:
        if decision == "approved":
            if violation:
                # Undo exactly what THIS violation cost the user, instead of
                # a hardcoded amount that doesn't match its actual severity.
                reduce_warning_points(
                    appeal["user_id"], violation["points"],
                    "Appeal approved by admin", admin_id,
                    rep_restore=REPUTATION_DEDUCTION.get(violation["severity"], 0)
                )
            add_notification(appeal["user_id"],
                             f"✅ Your appeal was approved! {response}",
                             link="my_profile")
        else:
            add_notification(appeal["user_id"],
                             f"❌ Your appeal was rejected. {response}",
                             link="my_profile")


# ── PEER REPORT OPERATIONS ────────────────────────────────────────────────────

def submit_peer_report(reporter_id, reported_user_id, report_type,
                       description, resource_id=None, comment_id=None,
                       evidence_files=""):
    conn = get_connection()
    try:
        conn.execute("""
            INSERT INTO peer_reports
            (reporter_id, reported_user_id, report_type, description,
             evidence_files, resource_id, comment_id)
            VALUES (?,?,?,?,?,?,?)
        """, (reporter_id, reported_user_id, report_type, description,
              evidence_files, resource_id, comment_id))
        conn.commit()

        # Notify admins
        admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
        reported = conn.execute(
            "SELECT name FROM users WHERE id=?", (reported_user_id,)
        ).fetchone()
        for admin in admins:
            add_notification(admin["id"],
                             f"🚩 New peer report against "
                             f"{reported['name'] if reported else 'a user'}: {report_type}",
                             link="admin_reports")
        conn.close()
        return True, "Report submitted. Admin will review it."
    except Exception as e:
        conn.close()
        return False, str(e)


def get_peer_reports(status=None):
    conn = get_connection()
    q = """
        SELECT pr.*, r.name as reporter_name,
               u.name as reported_name, u.role as reported_role,
               u.warning_points, u.reputation_score
        FROM peer_reports pr
        JOIN users r ON pr.reporter_id = r.id
        JOIN users u ON pr.reported_user_id = u.id
        WHERE 1=1
    """
    params = []
    if status:
        q += " AND pr.status=?"
        params.append(status)
    q += " ORDER BY pr.created_at DESC, pr.id DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_peer_report_status(report_id, status, reviewed_by):
    conn = get_connection()
    conn.execute(
        "UPDATE peer_reports SET status=?, reviewed_by=? WHERE id=?",
        (status, reviewed_by, report_id)
    )
    conn.commit()
    conn.close()


# ── COMMENT REPORT OPERATIONS ────────────────────────────────────────────────

def report_comment(comment_id, reported_by, reason):
    """Student reports an inappropriate comment."""
    conn = get_connection()
    try:
        comment = conn.execute("SELECT user_id FROM comments WHERE id=?", (comment_id,)).fetchone()
        if not comment:
            conn.close()
            return False, "Comment not found."

        conn.execute("""
            INSERT INTO comment_reports (comment_id, reported_by, reason)
            VALUES (?,?,?)
        """, (comment_id, reported_by, reason))
        conn.commit()

        # Notify all admins
        admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
        reporter = conn.execute("SELECT name FROM users WHERE id=?", (reported_by,)).fetchone()
        for admin in admins:
            add_notification(admin["id"],
                             f"🚩 New comment report from {reporter['name'] if reporter else 'a user'}",
                             link="admin_comments")
        conn.close()
        return True, "Report submitted. Admin will review it."
    except Exception as e:
        conn.close()
        return False, str(e)


def get_comment_reports(status=None):
    """Get all comment reports, optionally filtered by status."""
    conn = get_connection()
    q = """
        SELECT cr.*, c.content as comment_text, c.user_id as comment_author_id,
               u.name as reporter_name,
               cu.name as comment_author_name, cu.role as comment_author_role
        FROM comment_reports cr
        JOIN comments c ON cr.comment_id = c.id
        JOIN users u ON cr.reported_by = u.id
        JOIN users cu ON c.user_id = cu.id
        WHERE 1=1
    """
    params = []
    if status:
        q += " AND cr.status=?"
        params.append(status)
    q += " ORDER BY cr.created_at DESC, cr.id DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_comment_report_status(report_id, status, reviewed_by=None):
    """Admin marks comment report as reviewed/dismissed/actioned."""
    conn = get_connection()
    conn.execute("""
        UPDATE comment_reports SET status=?, reviewed_by=?
        WHERE id=?
    """, (status, reviewed_by, report_id))
    conn.commit()
    conn.close()


# ── TEACHER RATING REPORT OPERATIONS ─────────────────────────────────────────

def delete_review_text(rating_id):
    """
    Admin removes the written text of an offensive review, but keeps the
    underlying numeric scores intact (deleting the whole row would also
    discard a legitimate 1-5 rating just because its comment was abusive).
    Any teacher reply tied to that review is removed too, since it would
    otherwise be replying to now-deleted content.
    """
    conn = get_connection()
    conn.execute("UPDATE teacher_ratings SET review=NULL WHERE id=?", (rating_id,))
    conn.execute("DELETE FROM teacher_rating_replies WHERE rating_id=?", (rating_id,))
    conn.commit()
    conn.close()


def report_teacher_rating(rating_id, reported_by, reason):
    """Teacher reports an inappropriate anonymous student review."""
    conn = get_connection()
    try:
        rating = conn.execute("SELECT id FROM teacher_ratings WHERE id=?", (rating_id,)).fetchone()
        if not rating:
            conn.close()
            return False, "Review not found."

        conn.execute("""
            INSERT INTO rating_reports (rating_id, reported_by, reason)
            VALUES (?,?,?)
        """, (rating_id, reported_by, reason))
        conn.commit()

        # Notify all admins
        admins = conn.execute("SELECT id FROM users WHERE role='admin'").fetchall()
        reporter = conn.execute("SELECT name FROM users WHERE id=?", (reported_by,)).fetchone()
        for admin in admins:
            add_notification(admin["id"],
                             f"🚩 {reporter['name'] if reporter else 'A teacher'} reported "
                             f"a student review as inappropriate",
                             link="admin_ratings")
        conn.close()
        return True, "Report submitted. Admin will review it."
    except Exception as e:
        conn.close()
        return False, str(e)


def get_rating_reports(status=None):
    """
    Get all reported teacher reviews.
    Only admin sees the student identity (student_id/name) — the report
    itself preserves anonymity toward the teacher who filed it.
    """
    conn = get_connection()
    q = """
        SELECT rr.*, tr.review, tr.teaching_quality, tr.communication,
               tr.course_material, tr.student_id,
               s.name as student_name,
               t.name as teacher_name,
               rp.name as reporter_name,
               c.code as course_code, c.name as course_name
        FROM rating_reports rr
        JOIN teacher_ratings tr ON rr.rating_id = tr.id
        JOIN users s ON tr.student_id = s.id
        JOIN users t ON tr.teacher_id = t.id
        JOIN users rp ON rr.reported_by = rp.id
        JOIN courses c ON tr.course_id = c.id
        WHERE 1=1
    """
    params = []
    if status:
        q += " AND rr.status=?"
        params.append(status)
    q += " ORDER BY rr.created_at DESC, rr.id DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_rating_report_status(report_id, status, reviewed_by=None):
    """Admin marks a reported review as reviewed/dismissed/actioned."""
    conn = get_connection()
    conn.execute("""
        UPDATE rating_reports SET status=?, reviewed_by=?
        WHERE id=?
    """, (status, reviewed_by, report_id))
    conn.commit()
    conn.close()


def get_recommendations(user_id, limit=5):
    """Simple recommendation: resources from courses the user has downloaded from."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT DISTINCT r.*, u.name as uploader_name, c.code as course_code, c.name as course_name,
               COALESCE(AVG(rt.score),0) as avg_rating
        FROM resources r
        LEFT JOIN users u ON r.uploader_id=u.id
        LEFT JOIN courses c ON r.course_id=c.id
        LEFT JOIN ratings rt ON r.id=rt.resource_id
        WHERE r.course_id IN (
            SELECT DISTINCT r2.course_id FROM downloads d
            JOIN resources r2 ON d.resource_id=r2.id
            WHERE d.user_id=?
        )
        AND r.id NOT IN (SELECT resource_id FROM downloads WHERE user_id=?)
        AND r.is_approved=1
        GROUP BY r.id
        ORDER BY r.download_count DESC
        LIMIT ?
    """, (user_id, user_id, limit)).fetchall()
    conn.close()
    return [dict(r) for r in rows]