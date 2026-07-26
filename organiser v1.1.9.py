import os
import time
import shutil
import tkinter as tk
from tkinter import filedialog
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

#handles what happens whenever a file change is detected
class Test(FileSystemEventHandler):
    def __init__(self):
        self.recent_files = {}
    #function automatically runs whenever a new file is created
    def on_created(self, event):
        #Ignore folders; we only care about actual files
        if not event.is_directory:
            file_name = os.path.basename(event.src_path)
            file_path = event.src_path
            current_time = time.time()

            #if this file was processed less than 1 second ago, ignore the duplicate event
            if file_name in self.recent_files:
                if current_time - self.recent_files[file_name] < 1.0:
                    return

            #ignore temporary files created by browsers during an active download    
            if file_name.endswith(('.crdownload', '.tmp', '.part')):
                return
            #wait until the file finishes transferring
            historical_size = -1
            while True:
                try:
                    current_size = os.path.getsize(file_path)
                    #if the size matches what it was 0.2 seconds ago, the download is complete
                    if current_size == historical_size:
                        break
                    historical_size = current_size
                    time.sleep(0.2)
                except FileNotFoundError:
                    #if file vanishes or is renamed mid-download stop tracking
                    return

            #log the time file finished downloading
            self.recent_files[file_name] = time.time()
            
            print(f"New File {file_name} has been downloaded")

            self.trigger_popup(file_name, file_path)
    
    def trigger_popup(self, file_name, file_path):
        #create a blank desktop window
        root = tk.Tk()
        root.title("File Organiser")
        
        #force the pop-up window to appear on top of everything
        root.attributes("-topmost", True)
        #adds the text prompt inside the window
        label = tk.Label(root, text=f"New file detected: {file_name}\nWhat would you like to do with it?", padx=20, pady=20)
        label.pack()
        
        #placeholder commands that run when buttons are pressed
        def option_existing():
            #grabs variables from trigger_popup
            nonlocal file_name, file_path

            print("Action: Move to Existing Folder")

            #hide main popup temporarily
            root.withdraw()

            #open a window so the user can select destination folder
            chosen_folder = filedialog.askdirectory(title="Select Destination Folder")

            #if user selected folder and didnt hit cancel
            if chosen_folder:
                #create full destination path (e.g., "C:/users/user/videos")
                destination = os.path.join(chosen_folder, file_name)

                try:
                    #cut and paste file using shutil
                    shutil.move(file_path, destination)
                    print(f"Succesfully moved {file_name} to {chosen_folder}")

                except Exception as e:
                    print(f"Error moving file: {e}")
            root.destroy()
        
        def option_new():
            #grabs variables from trigger_popup
            nonlocal file_name, file_path
        
            print("Action: Create New Folder")
            #hide main popup temporarily
            root.withdraw()

            #ask user where to make the new folder
            parent_folder = filedialog.askdirectory(title="Where should the new folder be created?")

            if parent_folder:
                #ask user what to name new folder
                new_folder_name = tk.simpledialog.askstring("New Folder", "Enter new folder name:")

                if new_folder_name:
                    new_folder_path = os.path.join(parent_folder, new_folder_name)

                    try:
                        #if folder doesnt exist yet create it
                        if not os.path.exists(new_folder_path):
                            os.makedirs(new_folder_path)
                        #move file inside new folder
                        destination = os.path.join(new_folder_path, file_name)
                        shutil.move(file_path, destination)
                        print(f"Successfully created folder and moved {file_name}")
                    
                    except Exception as e:
                        print(f"Error creating folder or moving file: {e}")
            root.destroy()



        
        def option_leave():
            print("Action: Leave in Downloads")
            root.destroy()

        #3 buttons
        btnexist = tk.Button(root, text="Move to Existing Folder", command=option_existing)
        btnexist.pack(fill='x', padx=20, pady=5)

        btnnew = tk.Button(root, text="Create New Folder", command=option_new)
        btnnew.pack(fill='x', padx=20, pady=5)

        btnleave = tk.Button(root, text="Leave in Downloads Folder", command=option_leave)
        btnleave.pack(fill='x', padx=20, pady=5)

        #starts loopm that keeps window open
        root.mainloop()
#locate current systems download folder
downloads_folder = os.path.expanduser("~/Downloads")

#set up watchodg observer to look at target folder
event_handler = Test()
observer = Observer()
observer.schedule(event_handler, path=downloads_folder, recursive=False)

print(f"Watching: {downloads_folder}")

#start running folder watcher
observer.start()
try:
    #keep main script constantly running (every second)
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    #cleanly stop watcher
    observer.stop()
#wait for background thread to safely stop before exiting fully    
observer.join()