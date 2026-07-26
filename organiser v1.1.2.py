import os
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class Test(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            file_name = os.path.basename(event.src_path)
            file_path = event.src_path

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
            
            print(f"New File {file_name} has been downloaded")

           

downloads_folder = os.path.expanduser("~/Downloads")

event_handler = Test()
observer = Observer()
observer.schedule(event_handler, path=downloads_folder, recursive=False)

print(f"Watching: {downloads_folder}")

observer.start()
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
observer.join()