import os
import time
import shutil
import tkinter as tk
import queue
import threading
from tkinter import filedialog, messagebox, simpledialog, ttk
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import pystray
from PIL import Image, ImageDraw

from database import log_action
from database import add_rule
from database import get_rule_for_extension
from database import get_all_rules
from database import delete_rule
from database import get_action_history

file_queue = queue.Queue()

class Test(FileSystemEventHandler):
    def __init__(self):
        self.recent_files = {}

    def on_created(self, event):
        if not event.is_directory:
            file_name = os.path.basename(event.src_path)
            file_path = event.src_path
            current_time = time.time()

            if file_name in self.recent_files:
                if current_time - self.recent_files[file_name] < 1.0:
                    return

            if file_name.endswith(('.crdownload', '.tmp', '.part')):
                return

            historical_size = -1
            while True:
                try:
                    current_size = os.path.getsize(file_path)
                    if current_size == historical_size:
                        break
                    historical_size = current_size
                    time.sleep(0.2)
                except FileNotFoundError:
                    return

            self.recent_files[file_name] = time.time()

            _, ext = os.path.splitext(file_name)
            existing_target_folder = get_rule_for_extension(ext.lower())

            if existing_target_folder and os.path.exists(existing_target_folder):
                try:
                    destination = os.path.join(existing_target_folder, file_name)

                    if os.path.exists(destination):
                        base, ext_str = os.path.splitext(file_name)
                        counter = 1
                        while os.path.exists(destination):
                            destination = os.path.join(existing_target_folder, f"{base}_{counter}{ext_str}")
                            counter += 1

                    shutil.move(file_path, destination)
                    log_action("AUTO_SORTED", file_name, file_path, destination)
                    print(f"Auto-sorted {file_name} to {destination}")
                    return 
                except Exception as e:
                    print(f"Error auto-sorting file: {e}")
            
            print(f"New File {file_name} has been downloaded")
            file_queue.put((file_name, file_path))
    
    def trigger_popup(self, file_name, file_path, main_root):
        root = tk.Toplevel(main_root)
        root.title("File Organiser")
        root.attributes("-topmost", True)

        label = tk.Label(root, text=f"New file detected: {file_name}\nWhat would you like to do with it?", padx=20, pady=20)
        label.pack()

        save_rule_var = tk.IntVar(value=0)
        _, file_ext = os.path.splitext(file_name)
        rule_checkbox = tk.Checkbutton(root, text=f"Always move '{file_ext}' files to this location", variable=save_rule_var)
        rule_checkbox.pack(pady=5)
        
        def handle_collision(destination_folder, target_name):
            full_destination = os.path.join(destination_folder, target_name)

            if not os.path.exists(full_destination):
                return full_destination

            answer = messagebox.askyesnocancel(
                "File Name Conflict", 
                f"A file named '{target_name}' already exists in this folder. \n\n"
                "Click YES to REPLACE the existing file.\n"
                "Click NO to RENAME the new file. \n"
                "Click CANCEL to STOP the transfer"
            )
            if answer is True:
                return full_destination
            elif answer is False:
                base, ext = os.path.splitext(target_name)
                while True:
                    custom_name = simpledialog.askstring("Rename File", "Enter new name for the file:", initialvalue=base)
                    if custom_name:
                        if not custom_name.endswith(ext):
                            custom_name += ext
                        
                        new_destination = os.path.join(destination_folder, custom_name)
                        if not os.path.exists(new_destination):
                            return new_destination

                        messagebox.showwarning(
                            "Name Taken", 
                            f"A file named '{custom_name}' already exists in this folder.\n"
                            "Please choose a different name."
                        )
                    else:
                        return None
            else:
                return None

        def option_existing():
            nonlocal file_name, file_path
            root.withdraw()
            chosen_folder = filedialog.askdirectory(title="Select Destination Folder")

            if chosen_folder:
                destination = handle_collision(chosen_folder, file_name)
                if destination:
                    file_name = os.path.basename(destination)
                    try:
                        shutil.move(file_path, destination)
                        log_action("MOVED_FILE", file_name, file_path, destination)

                        if save_rule_var.get() == 1:
                            _, ext = os.path.splitext(file_name)
                            add_rule(ext.lower(), chosen_folder)
                            print(f"Saved new rule: {ext.lower()} -> {chosen_folder}")
                        
                        print(f"Successfully moved {file_name} to {chosen_folder}")
                    except Exception as e:
                        print(f"Error moving file: {e}")
                root.destroy()
            else:
                root.deiconify()
        
        def option_new():
            nonlocal file_name, file_path
            root.withdraw()
            parent_folder = filedialog.askdirectory(title="Where should the new folder be created?")

            if parent_folder:
                new_folder_name = simpledialog.askstring("New Folder", "Enter new folder name:")

                if new_folder_name:
                    new_folder_path = os.path.join(parent_folder, new_folder_name)
                    try:
                        while os.path.exists(new_folder_path):
                            new_folder_name = simpledialog.askstring("Folder Exists", f"'{new_folder_name}' already exists. Enter a different name:")
                            if not new_folder_name:
                                root.deiconify()
                                return
                            new_folder_path = os.path.join(parent_folder, new_folder_name)
                        
                        if not os.path.exists(new_folder_path):
                            os.makedirs(new_folder_path)
                            log_action("CREATED_FOLDER", new_folder_name, None, new_folder_path)
                            
                            destination = os.path.join(new_folder_path, file_name)
                            shutil.move(file_path, destination)
                            log_action("MOVED_FILE", file_name, file_path, destination)

                            if save_rule_var.get() == 1:
                                _, ext = os.path.splitext(file_name)
                                add_rule(ext.lower(), new_folder_path)
                                print(f"Saved new rule: {ext.lower()} -> {new_folder_path}")
                            
                            print(f"Successfully created folder and moved {file_name}")
                            root.destroy()

                    except Exception as e:
                        print(f"Error creating folder or moving file: {e}")
                        root.deiconify()
                else:
                    root.deiconify()
            else:
                root.deiconify()
        
        def option_leave():
            print("Action: Leave in Downloads")
            root.destroy()

        btnexist = tk.Button(root, text="Move to Existing Folder", command=option_existing)
        btnexist.pack(fill='x', padx=20, pady=5)

        btnnew = tk.Button(root, text="Create New Folder", command=option_new)
        btnnew.pack(fill='x', padx=20, pady=5)

        btnleave = tk.Button(root, text="Leave in Downloads Folder", command=option_leave)
        btnleave.pack(fill='x', padx=20, pady=5)

def create_tray_image():
    image = Image.new('RGB', (64, 64), color=(30, 144, 255))
    dc = ImageDraw.Draw(image)
    dc.rectangle((16, 16, 48, 48), fill=(255, 255, 255))
    return image

downloads_folder = os.path.expanduser("~\Downloads")
event_handler = Test()
observer = Observer()
observer.schedule(event_handler, path=downloads_folder, recursive=False)
observer.start()

main_root = tk.Tk()
main_root.title("File Organiser Dashboard")
main_root.geometry("400x350")

tk.Label(main_root, text="File Organiser Dashboard", font=("Arial", 12, "bold")).pack(pady=(15, 5))
tk.Label(main_root, text=f"monitoring: {downloads_folder}", font=("Arial", 9), fg="gray").pack(pady=(0, 15))

tray_icon = None

def show_dashboard():
    main_root.after(0, main_root.deiconify)

def hide_dashboard():
    main_root.withdraw()

def quit_app():
    if tray_icon:
        tray_icon.stop()
    observer.stop()
    main_root.after(0, main_root.destroy)

def setup_tray_icon():
    global tray_icon
    menu = pystray.Menu(
        pystray.MenuItem("Open Dashboard", lambda: show_dashboard()),
        pystray.MenuItem("Exit & Stop Monitoring", lambda: quit_app())
    )
    tray_icon = pystray.Icon("FileOrganiser", create_tray_image(), "File Organiser (Running)", menu)
    tray_icon.run()

threading.Thread(target=setup_tray_icon, daemon=True).start()

def dashboard_add_rule():
    ext = simpledialog.askstring("Add Rule", "Enter file extension (e.g. .pdf):")
    if ext:
        if not ext.startswith('.'):
            ext = '.' + ext
        target_dir = filedialog.askdirectory(title="Select Target Directory")
        if target_dir:
            add_rule(ext.lower(), target_dir)
            messagebox.showinfo("Rule Saved", f"Added Rule: {ext.lower()} to {target_dir}")

def dashboard_remove_rule():
    rules = get_all_rules()
    if not rules:
        messagebox.showinfo("No Rules", "You do not have any custom auto-sort rules yet.")
        return

    remove_window = tk.Toplevel(main_root)
    remove_window.title("Remove Auto-Sort Rule")
    remove_window.geometry("450x260")
    remove_window.transient(main_root)
    remove_window.grab_set()

    tk.Label(remove_window, text="Select a rule to remove:", font=("Arial", 10, "bold")).pack(pady=(10, 5))

    rule_list = tk.Listbox(remove_window, height=min(10, len(rules)), width=60)
    for rule in rules:
        rule_list.insert(tk.END, f"{rule['extension']} -> {rule['destination']}")
    rule_list.pack(fill='both', expand=True, padx=10, pady=5)

    def remove_selected_rule():
        selection = rule_list.curselection()
        if not selection:
            messagebox.showwarning("No Selection", "Please select a rule to remove.")
            return

        selected_index = selection[0]
        selected_rule = rules[selected_index]

        confirm = messagebox.askyesno(
            "Confirm Removal",
            f"Remove the rule for '{selected_rule['extension']}'?"
        )

        if confirm:
            delete_rule(selected_rule['id'])
            messagebox.showinfo("Rule Removed", f"Removed rule for {selected_rule['extension']}")
            remove_window.destroy()

    tk.Button(remove_window, text="Remove Selected Rule", command=remove_selected_rule).pack(pady=(0, 10))

def dashboard_view_history():
    history = get_action_history()
    if not history:
        messagebox.showinfo("File History", "No file movements logged yet.")
        return

    history_win = tk.Toplevel(main_root)
    history_win.title("File Move History")
    history_win.geometry("600x350")
    history_win.attributes("-topmost", True)

    tk.Label(history_win, text="Recent File Actions Log", font=("Arial", 10, "bold")).pack(pady=10)

    frame = tk.Frame(history_win)
    frame.pack(fill='both', expand=True, padx=15, pady=5)

    scrollbar = ttk.Scrollbar(frame)
    scrollbar.pack(side='right', fill='y')

    columns = ("file_name", "action", "destination")
    tree = ttk.Treeview(frame, columns=columns, show='headings', yscrollcommand=scrollbar.set)
    scrollbar.config(command=tree.yview)

    tree.heading("file_name", text="File Name")
    tree.heading("action", text="Action")
    tree.heading("destination", text="Destination")

    tree.column("file_name", width=150)
    tree.column("action", width=110)
    tree.column("destination", width=300)

    for log in history:
        tree.insert('', tk.END, values=(log["file_name"], log["action"], log["destination"]))

    tree.pack(fill='both', expand=True)

def dashboard_open_downloads():
    os.startfile(downloads_folder)

def check_queue(main_root, event_handler):
    try:
        file_name, file_path = file_queue.get_nowait()
        event_handler.trigger_popup(file_name, file_path, main_root)
    except queue.Empty:
        pass

    main_root.after(500, lambda: check_queue(main_root, event_handler))

btn_add_rule = tk.Button(main_root, text="Add Custom Auto-Sort Rule", command=dashboard_add_rule)
btn_add_rule.pack(fill='x', padx=40, pady=4)

btn_remove_rule = tk.Button(main_root, text="Remove Custom Auto-Sort Rule", command=dashboard_remove_rule)
btn_remove_rule.pack(fill='x', padx=40, pady=4)

btn_view_history = tk.Button(main_root, text="View Move History", command=dashboard_view_history)
btn_view_history.pack(fill='x', padx=40, pady=4)

btn_open_downloads = tk.Button(main_root, text="Open Downloads Folder", command=dashboard_open_downloads)
btn_open_downloads.pack(fill='x', padx=40, pady=4)

btn_hide = tk.Button(main_root, text="Hide to Tray (Keep Monitoring)", command=hide_dashboard)
btn_hide.pack(fill='x', padx=40, pady=4)

btn_exit = tk.Button(main_root, text="Exit & Stop Monitoring", command=quit_app)
btn_exit.pack(fill='x', padx=40, pady=4)

main_root.protocol("WM_DELETE_WINDOW", hide_dashboard)

check_queue(main_root, event_handler)

try:
    main_root.mainloop()
except KeyboardInterrupt:
    pass
finally:
    observer.stop()
    observer.join()