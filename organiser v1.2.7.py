import os
import time
import shutil
import tkinter as tk
import queue
from tkinter import filedialog, messagebox, simpledialog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from database import log_action
from database import add_rule
from database import get_rule_for_extension

# queue to pass downloaded file info from the background
file_queue = queue.Queue()

# handles what happens whenever a file change is detected
class Test(FileSystemEventHandler):
    def __init__(self):
        # keeps track of recently processed files
        self.recent_files = {}

    # function automatically runs whenever a new file is created
    def on_created(self, event):
        # ignore folders, only care about actual files
        if not event.is_directory:
            file_name = os.path.basename(event.src_path)
            file_path = event.src_path
            current_time = time.time()

            # if this file was processed less than 1 second ago, ignore the duplicate event
            if file_name in self.recent_files:
                if current_time - self.recent_files[file_name] < 1.0:
                    return

            # ignore temporary files created by browsers during an active download    
            if file_name.endswith(('.crdownload', '.tmp', '.part')):
                return
            # wait until the file finishes transferring
            historical_size = -1
            while True:
                try:
                    current_size = os.path.getsize(file_path)
                    # if the size matches what it was 0.2 seconds ago, the download is complete
                    if current_size == historical_size:
                        break
                    historical_size = current_size
                    time.sleep(0.2)
                except FileNotFoundError:
                    # if file vanishes or is renamed mid-download stop tracking
                    return

            # log the time file finished downloading
            self.recent_files[file_name] = time.time()

            # check if a saved rule already exists for this file type
            _, ext = os.path.splitext(file_name)
            existing_target_folder = get_rule_for_extension(ext.lower())

            if existing_target_folder and os.path.exists(existing_target_folder):
                try:
                    destination = os.path.join(existing_target_folder, file_name)

                    # if file with same name already exists in target folder add number to end
                    if os.path.exists(destination):
                        base, ext_str = os.path.splitext(file_name)
                        counter = 1
                        while os.path.exists(destination):
                            destination = os.path.join(existing_target_folder, f"{base}_{counter}{ext_str}")
                            counter += 1

                    shutil.move(file_path, destination)
                    log_action("AUTO_SORTED", file_name, file_path, destination)
                    print(f"Auto-sorted {file_name} to {destination}")
                    # skip opening the popup window if auto sorted
                    return 
                except Exception as e:
                    print(f"Error auto-sorting file: {e}")
            
            print(f"New File {file_name} has been downloaded")

            file_queue.put((file_name, file_path))
    
    def trigger_popup(self, file_name, file_path, main_root):
        # create a blank desktop window
        root = tk.Toplevel(main_root)
        root.title("File Organiser")
        
        # force the pop-up window to appear on top of everything
        root.attributes("-topmost", True)
        # adds the text prompt inside the window
        label = tk.Label(root, text=f"New file detected: {file_name}\nWhat would you like to do with it?", padx=20, pady=20)
        label.pack()

        # checkbox for user to save destination preference as a rule
        save_rule_var = tk.IntVar(value=0)
        _, file_ext = os.path.splitext(file_name)
        rule_checkbox = tk.Checkbutton(root, text=f"Always move '{file_ext}' files to this location", variable=save_rule_var)
        rule_checkbox.pack(pady=5)
        
        # handles a file with the same name existing there already
        def handle_collision(destination_folder, target_name):
            full_destination = os.path.join(destination_folder, target_name)

            # if no duplicate just return path as is
            if not os.path.exists(full_destination):
                return full_destination

            # ask user whether to replace rename or cancel
            answer = messagebox.askyesnocancel(
                "File Name Conflict", 
                f"A file named '{target_name}' already exists in this folder. \n\n"
                "Click YES to REPLACE the existing file.\n"
                "Click NO to RENAME the new file. \n"
                "Click CANCEL to STOP the transfer"
            )
            if answer is True: # user clicked yes (replace)
                return full_destination
            
            elif answer is False: # user clicked no (rename)
                # split name and extension
                base, ext = os.path.splitext(target_name)

                # safety check whether chosen name also exists (loop back)
                while True:
                    # ask user for custom file name
                    custom_name = simpledialog.askstring("Rename File", "Enter new name for the file:", initialvalue=base)

                    # if they provided a name
                    if custom_name:
                        # make sure the user didnt type out extension themselves
                        if not custom_name.endswith(ext):
                            custom_name += ext
                        
                        new_destination = os.path.join(destination_folder, custom_name)

                        # if the name is completely free break out and return the path
                        if not os.path.exists(new_destination):
                            return new_destination

                        # safety check whether chosen name also exists (loop back)
                        messagebox.showwarning(
                            "Name Taken", 
                            f"A file named '{custom_name}' already exists in this folder.\n"
                            "Please choose a different name."
                        )
                    else:
                        # if they hit cancel on rename text box stop whole transfer
                        return None
            
            else:
                # user clicked cancel or closed window (before rename)
                return None

        # placeholder commands that run when buttons are pressed
        def option_existing():
            nonlocal file_name, file_path

            print("Action: Move to Existing Folder")

            # hide main popup temporarily
            root.withdraw()

            # open a window so the user can select destination folder
            chosen_folder = filedialog.askdirectory(title="Select Destination Folder")

            # if user selected folder and didnt hit cancel
            if chosen_folder:
                # pass details through collision handler first
                destination = handle_collision(chosen_folder, file_name)

                if destination:
                    # update file_name to what they renamed it to if they did
                    file_name = os.path.basename(destination)
                    try:
                        # cut and paste file using shutil
                        shutil.move(file_path, destination)
                        
                        # log the file move to database history
                        log_action("MOVED_FILE", file_name, file_path, destination)

                        # if user ticked checkbox save new rule in database
                        if save_rule_var.get() == 1:
                            _, ext = os.path.splitext(file_name)
                            add_rule(ext.lower(), chosen_folder)
                            print(f"Saved new rule: {ext.lower()} -> {chosen_folder}")
                        
                        print(f"Successfully moved {file_name} to {chosen_folder}")

                    except Exception as e:
                        print(f"Error moving file: {e}")
                    
                root.destroy()
            else:
                # if cancelled folder select bring popup back
                root.deiconify()
        
        def option_new():
            nonlocal file_name, file_path
        
            print("Action: Create New Folder")
            # hide main popup temporarily
            root.withdraw()

            # ask user where to make the new folder
            parent_folder = filedialog.askdirectory(title="Where should the new folder be created?")

            if parent_folder:
                # ask user what to name new folder
                new_folder_name = simpledialog.askstring("New Folder", "Enter new folder name:")

                if new_folder_name:
                    new_folder_path = os.path.join(parent_folder, new_folder_name)

                    try:
                        # if exists keep asking for new name till unique
                        while os.path.exists(new_folder_path):
                            new_folder_name = simpledialog.askstring("Folder Exists", f"'{new_folder_name}' already exists. Enter a different name:")

                            # if they hit cancel stop function
                            if not new_folder_name:
                                # show popup again
                                root.deiconify()
                                return
                            
                            new_folder_path = os.path.join(parent_folder, new_folder_name)
                        
                        if not os.path.exists(new_folder_path):
                            os.makedirs(new_folder_path)
                            
                            # log new folder creation to database history
                            log_action("CREATED_FOLDER", new_folder_name, None, new_folder_path)
                            
                            destination = os.path.join(new_folder_path, file_name)
                            shutil.move(file_path, destination)
                            
                            # log file move to database history
                            log_action("MOVED_FILE", file_name, file_path, destination)

                            # if user ticked checkbox save new rule in database
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
                    # if cancelled at "new folder name"
                    root.deiconify()
            else:
                # if canceled at initial parent folder select
                root.deiconify()
        
        def option_leave():
            print("Action: Leave in Downloads")
            root.destroy()

        # 3 buttons
        btnexist = tk.Button(root, text="Move to Existing Folder", command=option_existing)
        btnexist.pack(fill='x', padx=20, pady=5)

        btnnew = tk.Button(root, text="Create New Folder", command=option_new)
        btnnew.pack(fill='x', padx=20, pady=5)

        btnleave = tk.Button(root, text="Leave in Downloads Folder", command=option_leave)
        btnleave.pack(fill='x', padx=20, pady=5)

# locate current system's download folder
downloads_folder = os.path.expanduser("~\Downloads")

# set up watchdog observer to look at target folder
event_handler = Test()
observer = Observer()
observer.schedule(event_handler, path=downloads_folder, recursive=False)

print(f"Watching: {downloads_folder}")

def check_queue(main_root, event_handler):
    try:
        # check queue without blocking
        file_name, file_path = file_queue.get_nowait()
        # trigger popup safely on main thread
        event_handler.trigger_popup(file_name, file_path, main_root)
    except queue.Empty:
        pass

    # check queue again in 500ms
    main_root.after(500, lambda: check_queue(main_root, event_handler))

# start running folder watcher
observer.start()

# create master window on main thread
main_root = tk.Tk()
main_root.title("File Organiser Dashboard")
main_root.geometry("400x150")

# add simple status text inside dashboard
tk.Label(main_root, text="File Organiser Active\nMonitoring Downloads Folder...", font=("Arial", 11), pady=30).pack()

# start checking queue
check_queue(main_root, event_handler)

try:
    # use tkinter main loop to keep script alive
    main_root.mainloop()
except KeyboardInterrupt:
    pass
finally:
    # cleanly stop watcher
    observer.stop()
    observer.join()