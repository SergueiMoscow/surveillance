import os
import asyncio
import time


class ArchiveHandler:
    def __init__(self, path, max_size_gb):
        self.path = path
        self.max_size_gb = max_size_gb

    def calculate_folder_size(self):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(self.path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
        return total_size/(1024*1024*1024)

    def delete_oldest_files(self):
        files = [(f, os.path.getmtime(os.path.join(self.path, f)))
                 for f in os.listdir(self.path) if os.path.isfile(os.path.join(self.path, f))]
        if files:
            oldest_file = min(files, key=lambda x: x[1])[0]
            os.remove(os.path.join(self.path, oldest_file))

    def check_archive(self):
        while True:
            size = self.calculate_folder_size()
            print(f"Current folder size: {size} GB")
            while size > self.max_size_gb:
                print("The folder size is too large. Deleting the oldest files...")
                self.delete_oldest_files()
                size = self.calculate_folder_size()
            time.sleep(60)
