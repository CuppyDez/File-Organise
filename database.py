import os 
import sqlite3
import sys

if getattr(sys, 'frozen', False):
    folder_path = os.path.dirname(sys.executable)
else:
    folder_path = os.path.dirname(os.path.abspath(__file__))

full_file_path = os.path.join(folder_path, "database.db")

def initialise_database():
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    
    worker.execute("""CREATE TABLE IF NOT EXISTS autosort_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        extension TEXT NOT NULL UNIQUE, 
        destination TEXT NOT NULL
    )""")
    
    worker.execute("""CREATE TABLE IF NOT EXISTS history_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action_type TEXT NOT NULL,
        file_name TEXT NOT NULL,
        source_path TEXT,
        destination_path TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )""")
    
    connection.commit()
    connection.close()

def add_rule(extension, destination):
    try:
        connection = sqlite3.connect(full_file_path)
        worker = connection.cursor()
        worker.execute("INSERT INTO autosort_rules (extension, destination) VALUES (?, ?)", (extension.lower(), destination))
        connection.commit()
        connection.close()
        return True
    except sqlite3.IntegrityError:
        connection.close()
        return False

def get_all_rules(): 
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    worker.execute("SELECT id, extension, destination FROM autosort_rules")
    rows = worker.fetchall()
    connection.close()
    
    rules = []
    for row in rows:
        rules.append({
            "id": row[0],
            "extension": row[1],
            "destination": row[2]
        })
    return rules

def delete_rule(rule_id):
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    worker.execute("DELETE FROM autosort_rules WHERE id = ?", (rule_id,))
    connection.commit()
    connection.close()

def log_action(action_type, file_name, source_path, destination_path):
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    worker.execute("""INSERT INTO history_log (action_type, file_name, source_path, destination_path) 
                      VALUES (?, ?, ?, ?)""", 
                   (action_type, file_name, source_path, destination_path))
    connection.commit()
    connection.close()

def get_action_history():
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    worker.execute("SELECT file_name, action_type, destination_path FROM history_log ORDER BY id DESC LIMIT 100")
    rows = worker.fetchall()
    connection.close()
    
    history = []
    for row in rows:
        history.append({
            "file_name": row[0],
            "action": row[1],
            "destination": row[2]
        })
    return history

def get_rule_for_extension(extension):
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    worker.execute("SELECT destination FROM autosort_rules WHERE extension = ?", (extension.lower(),))
    row = worker.fetchone()
    connection.close()
    
    if row:
        return row[0]
    return None

initialise_database()