import sqlite3
import sys

DB_Name = "chat.db"

def init_db():
    
    conn = sqlite3.connect(DB_Name)

    cursor = conn.cursor()

    cursor.execute(""" 
        CREATE TABLE IF NOT EXISTS messages(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)

    conn.commit()
    conn.close()

def save_message(session_id: str, role: str, content: str):
    conn = sqlite3.connect(DB_Name)
    cursor = conn.cursor()

    cursor.execute(""" 
        INSERT INTO messages (session_id, role, content)
        VALUES(?,?,?);
    """, (session_id, role, content))
    conn.commit()
    conn.close()

def get_chat_history(session_id: str) -> list:
    conn = sqlite3.connect(DB_Name)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role, content FROM messages 
        WHERE session_id = ?
        ORDER BY created_at ASC;
    """, (session_id,))

    rows = cursor.fetchall()
    conn.close()

    history = []
    for row in rows:
        history.append({
            "role": row[0],
            "content": row[1]
        })
    return history


if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        if command == "init":
            init_db()
            print("Database initialized successfully!")
        else:
            print(f" Unknown command: '{command}'")
    else:
        init_db()
        print("ℹ Defaulting to safe initialization...")