import os
import time
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