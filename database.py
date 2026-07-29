import os 
import sqlite3

#get direction where script lives
folder_path = os.path.dirname(os.path.abspath(__file__))
#combine directory with file name properly
full_file_path = os.path.join(folder_path, "database.db")

def initialise_database():
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    
    #table for sorting rules
    worker.execute("""CREATE TABLE IF NOT EXISTS autosort_rules (
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        extension TEXT NOT NULL UNIQUE, 
        destination TEXT NOT NULL
    )""")
    
    #table for tracking moved files and created folders
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

        #insert statement with ? placeholders
        worker.execute("INSERT INTO autosort_rules (extension, destination) VALUES (?, ?)", (extension.lower(), destination))

        connection.commit()
        connection.close()
        return True #success
    except sqlite3.IntegrityError:
        #fires if extension in database
        connection.close()
        return False #failed cause duplicate

def get_all_rules(): 
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    
    #get all rules from table
    worker.execute("SELECT id, extension, destination FROM autosort_rules")
    rows = worker.fetchall()
    
    connection.close()
    
    #turn rows into clean dictionary list
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
    
    #delete rule matching id
    worker.execute("DELETE FROM autosort_rules WHERE id = ?", (rule_id,))
    
    connection.commit()
    connection.close()

def log_action(action_type, file_name, source_path, destination_path):
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    
    #insert new action into history
    worker.execute("""INSERT INTO history_log (action_type, file_name, source_path, destination_path) 
                      VALUES (?, ?, ?, ?)""", 
                   (action_type, file_name, source_path, destination_path))
    
    connection.commit()
    connection.close()

def get_history():
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    
    #get 50 most recent actions
    worker.execute("SELECT id, action_type, file_name, source_path, destination_path, timestamp FROM history_log ORDER BY id DESC LIMIT 50")
    rows = worker.fetchall()
    
    connection.close()


    
    #turn rows into clean list of dicts
    history = []
    for row in rows:
        history.append({
            "id": row[0],
            "action": row[1],
            "file": row[2],
            "from": row[3],
            "to": row[4],
            "time": row[5]
        })
    return history

def get_rule_for_extension(extension):
    connection = sqlite3.connect(full_file_path)
    worker = connection.cursor()
    
    # lookup target folder for a specific file extension
    worker.execute("SELECT destination FROM autosort_rules WHERE extension = ?", (extension.lower(),))
    row = worker.fetchone()
    
    connection.close()
    
    # return the folder path if found, or None if no rule exists
    if row:
        return row[0]
    return None

# ensure the database and tables exist when the module is imported
initialise_database()

#run setup when script executes
if __name__ == "__main__":
    initialise_database()