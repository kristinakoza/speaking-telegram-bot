import sqlite3
from pathlib import Path
from datetime import datetime

#constants
SUBMISSION_PENDING = 0
SUBMISSION_APPROVED = 1
SUBMISSION_REJECTED = 2
SUBMISSION_NEEDS_REDO = 3

# Initialize db
def init_db():
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    # tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        approved INTEGER DEFAULT 0,  
        current_task INTEGER DEFAULT 0,
        finished INTEGER DEFAULT 0,
        joined_date TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        day_number INTEGER UNIQUE,
        task_text TEXT
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    task_id INTEGER,
    voice_file_path TEXT,
    feedback_text TEXT DEFAULT '',
    status INTEGER DEFAULT 0,  -- 0=pending, 1=approved, 2=rejected, 3=needs_redo
    FOREIGN KEY(user_id) REFERENCES users(id),
    FOREIGN KEY(task_id) REFERENCES tasks(id)
)
""")

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_submissions_user_id ON submissions(user_id)
""")
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_submissions_task_id ON submissions(task_id)
""")
    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_submissions_status ON submissions(status)
""")
    
    
    conn.commit()
    conn.close()

# User operations
def add_user(telegram_id, username):
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO users (telegram_id, username, joined_date) VALUES (?, ?, ?)",
        (telegram_id, username, datetime.now().isoformat())
    )
    user_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return user_id

def get_user_by_telegram_id(telegram_id):
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'telegram_id': user[1],
            'username': user[2],
            'approved': bool(user[3]),  
            'current_task': user[4],
            'finished': bool(user[5]),
            'joined_date': datetime.fromisoformat(user[6])
        }
    return None

def update_user(user_id, updates):
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values())
    values.append(user_id)
    
    cursor.execute(
        f"UPDATE users SET {set_clause} WHERE id = ?",
        values
    )
    
    conn.commit()
    conn.close()

def get_unapproved_users():
    """Improved to return minimal needed data"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, username, joined_date 
        FROM users 
        WHERE approved = 0
        ORDER BY joined_date DESC
    """)
    
    users = cursor.fetchall()
    conn.close()
    
    return [{
        'id': user[0],
        'telegram_id': user[1],
        'username': user[2],
        'joined_date': datetime.fromisoformat(user[3])
    } for user in users]

# Task operations
def add_task(day_number, task_text):
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "INSERT INTO tasks (day_number, task_text) VALUES (?, ?)",
        (day_number, task_text)
    )
    task_id = cursor.lastrowid
    
    conn.commit()
    conn.close()
    return task_id  

def get_task_by_day(day_number):
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM tasks WHERE day_number = ?", (day_number,))
    task = cursor.fetchone()
    conn.close()
    
    if task:
        return {
            'id': task[0],
            'day_number': task[1],
            'task_text': task[2]
        }
    return None

def get_pending_tasks(user_id):
    """Get all tasks that user hasn't successfully completed yet"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT t.id, t.day_number, t.task_text 
            FROM tasks t
            WHERE NOT EXISTS (
                SELECT 1 FROM submissions s 
                WHERE s.task_id = t.id 
                AND s.user_id = ? 
                AND s.checked = ?
            )
            ORDER BY t.day_number
        """, (user_id, SUBMISSION_APPROVED))
        
        tasks = [{
            'id': row[0],
            'day': row[1],
            'text': row[2]
        } for row in cursor.fetchall()]
        
        return tasks
    except sqlite3.Error as e:
        print(f"Database error in get_pending_tasks: {e}")
        return []
    finally:
        conn.close()

def get_user_completed_tasks_count(user_id):
    """Get count of tasks user has completed"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT COUNT(DISTINCT task_id)
            FROM submissions
            WHERE user_id = ? AND status = ?
        """, (user_id, SUBMISSION_APPROVED))
        
        return cursor.fetchone()[0]
    except sqlite3.Error as e:
        print(f"Database error in get_user_completed_tasks_count: {e}")
        return 0
    finally:
        conn.close()

def get_user_progress(user_id):
    """Get user's completion progress"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT COUNT(*) FROM tasks")
        total_tasks = cursor.fetchone()[0]
        
        completed = get_user_completed_tasks_count(user_id)
        
        return {
            'completed': completed,
            'total': total_tasks,
            'percentage': (completed / total_tasks * 100) if total_tasks > 0 else 0
        }
    except sqlite3.Error as e:
        print(f"Database error in get_user_progress: {e}")
        return {'completed': 0, 'total': 0, 'percentage': 0}
    finally:
        conn.close()

def get_all_tasks():
    """Get all tasks in the system"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT * FROM tasks ORDER BY day_number")
        return [{
            'id': row[0],
            'day_number': row[1],
            'task_text': row[2]
        } for row in cursor.fetchall()]
    except sqlite3.Error as e:
        print(f"Database error in get_all_tasks: {e}")
        return []
    finally:
        conn.close()

def get_user_submissions(user_id, status=None):
    """Get all submissions for a user, optionally filtered by status"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    try:
        if status is not None:
            cursor.execute("SELECT * FROM submissions WHERE user_id = ? AND checked = ?", 
                         (user_id, status))
        else:
            cursor.execute("SELECT * FROM submissions WHERE user_id = ?", (user_id,))
            
        return cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Database error in get_user_submissions: {e}")
        return []
    finally:
        conn.close()

def get_submission_by_id(submission_id):
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT * FROM submissions WHERE id = ?
    """, (submission_id,))
    
    submission = cursor.fetchone()
    conn.close()
    
    if submission:
        return {
            'id': submission[0],
            'user_id': submission[1],
            'task_id': submission[2],
            'voice_file_path': submission[3],
            'feedback_text': submission[4],
            'checked': submission[5]
        }
    return None

# Submission operations
def add_submission(user_id, task_id, voice_file_path, checked=SUBMISSION_PENDING):
    """Add a new voice submission to the database"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            INSERT INTO submissions (user_id, task_id, voice_file_path, checked)
            VALUES (?, ?, ?, ?)
        """, (user_id, task_id, voice_file_path, checked))
        
        conn.commit()
        return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"Database error in add_submission: {e}")
        return None
    finally:
        conn.close()

def get_status_text(status_code):
    status_map = {
        SUBMISSION_PENDING: "🟡 Pending",
        SUBMISSION_APPROVED: "✅ Approved",
        SUBMISSION_REJECTED: "❌ Rejected", 
        SUBMISSION_NEEDS_REDO: "🟠 Needs Redo"
    }
    return status_map.get(status_code, "❓ Unknown")


def get_submission_by_user_and_task(user_id, task_id):
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT * FROM submissions WHERE user_id = ? AND task_id = ?",
        (user_id, task_id)
    )
    submission = cursor.fetchone()
    conn.close()
    
    if submission:
        return {
            'id': submission[0],
            'user_id': submission[1],
            'task_id': submission[2],
            'voice_file_path': submission[3],
            'feedback_text': submission[4],
            'checked': bool(submission[5])
        }
    return None

def update_submission(submission_id, updates):
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
    values = list(updates.values())
    values.append(submission_id)
    
    cursor.execute(
        f"UPDATE submissions SET {set_clause} WHERE id = ?",
        values
    )
    
    conn.commit()
    conn.close()


def get_all_users():
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, telegram_id, username, 
               approved, current_task, 
               finished, joined_date
        FROM users 
        ORDER BY id
    """)
    
    users = cursor.fetchall()
    conn.close()
    
    return [{
        'id': user[0],
        'telegram_id': user[1],
        'username': user[2],
        'approved': bool(user[3]),  
        'current_task': user[4],     
        'finished': bool(user[5]),   
        'joined_date': datetime.fromisoformat(user[6])  
    } for user in users]

def get_user_by_id(user_id):
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, telegram_id, username, 
               approved, current_task,
               finished, joined_date
        FROM users 
        WHERE id = ?
    """, (user_id,))
    
    user = cursor.fetchone()
    conn.close()

    if user:
        return {
            'id': user[0],
            'telegram_id': user[1],
            'username': user[2],
            'approved': bool(user[3]),  
            'current_task': user[4],    
            'finished': bool(user[5]),  
            'joined_date': datetime.fromisoformat(user[6])  
        }
    return None
def get_completed_task_count(user_id):
    """Count approved submissions for a user"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM submissions 
        WHERE user_id=? AND checked=?
    """, (user_id, SUBMISSION_APPROVED))
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_total_task_count():
    """Get total number of tasks"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM tasks")
    count = cursor.fetchone()[0]
    conn.close()
    return count

def get_user_by_username(username):
    """Find user by username (case-insensitive)"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE LOWER(username)=?", (username.lower(),))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'telegram_id': user[1],
            'username': user[2],
            'approved': bool(user[3]),
            'current_task': user[4],
            'finished': bool(user[5]),
            'joined_date': datetime.fromisoformat(user[6])
        }
    return None

def get_user_by_username(username):
    """Find user by telegram username (without @)"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username.lower(),))
    user = cursor.fetchone()
    conn.close()
    
    if user:
        return {
            'id': user[0],
            'telegram_id': user[1],
            'username': user[2],
            'approved': bool(user[3]),
            'current_task': user[4],
            'finished': bool(user[5]),
            'joined_date': datetime.fromisoformat(user[6])
        }
    return None

def get_all_submissions():
    """Get all submissions"""
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT id, user_id, task_id, voice_file_path, feedback_text, checked
            FROM submissions
            ORDER BY id DESC
        """)
        rows = cursor.fetchall()
        return [
            {
                'id': r[0],
                'user_id': r[1],
                'task_id': r[2],
                'voice_file_path': r[3],
                'feedback_text': r[4],
                'status': r[5]   # We rename checked -> status for consistency
            } for r in rows
        ]
    finally:
        conn.close()