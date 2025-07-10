from repos.GoogleDriveRepo import GoogleDriveRepo
import time
import os
import io

class BackupService:
    def __init__(self, log, interval=0):
        self.log = log
        self.interval = interval
        self.drive_repo = GoogleDriveRepo()

        self.db_folder = os.getenv('DB_FOLDER')
        self.config_folder = os.getenv('CONFIG_FOLDER')
        self.log_folder = os.getenv('LOG_FOLDER')


    def push_folder(self, local_folder_path: str, folder_id: str, current_time: float):
        files_to_push = os.listdir(local_folder_path)
        files_to_delete = self.drive_repo.get_files_in_folder(folder_id)

        for file in files_to_push:
            file_path = f"{local_folder_path}/{file}"
            last_change_timestamp = os.path.getmtime(file_path)
            if current_time - last_change_timestamp > self.interval:
                continue

            with open(file_path, 'rb') as f:
                data = f.read()

            self.log.info(f"Starting to push: {file} [{len(data)/1e6:.2f} MB]")
            self.drive_repo.upload_file_from_bytes(file_bytes=io.BytesIO(data), filename=file, folder_id=folder_id)
            if file in files_to_delete:
                self.drive_repo.delete_file(files_to_delete[file])


    def push_all(self):
        folders_to_setup = [
            (self.db_folder, "Data/database/"),
            (self.log_folder, "Data/logs/")
        ]


        self.log.info("Backup in progress...")
        start_timestamp = time.time()
        for folder in folders_to_setup:
            self.push_folder(local_folder_path=folder[1], folder_id=folder[0], current_time=start_timestamp)

        self.log.info(f"Backup is finished in {time.time()-start_timestamp:.4f} secconds!")

    def run(self):
        if self.interval > 0:
            while True:
                time.sleep(self.interval)
                self.push_all()

        