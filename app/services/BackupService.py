from repos.BackblazeRepo import BackblazeRepo
import time
import os
import io

class BackupService:
    def __init__(self, log, interval=0):
        self.log = log
        self.interval = interval
        self.drive_repo = BackblazeRepo()

        # Environment variables must match Backblaze folder prefixes
        self.db_folder = os.getenv('DB_FOLDER')
        self.log_folder = os.getenv('LOG_FOLDER')

    def push_folder(self, local_folder_path: str, b2_folder_path: str):
        files_to_push = os.listdir(local_folder_path)

        for file in files_to_push:
            if file in ['.gitkeep', '.bzEmpty']:
                continue

            file_path = os.path.join(local_folder_path, file)

            with open(file_path, 'rb') as f:
                data = f.read()

            self.log.info(f"Starting to push: {file} [{len(data)/1e6:.2f} MB]")
            self.drive_repo.upload_file_from_bytes(
                file_bytes=io.BytesIO(data),
                filename=file,
                folder_path=b2_folder_path
            )

    def push_all(self):
        folders_to_setup = [
            (self.db_folder, "Data/database/"),
            (self.log_folder, "Data/logs/")
        ]

        self.log.info("Backup in progress...")
        start_timestamp = time.time()

        for b2_path, local_path in folders_to_setup:
            self.push_folder(local_folder_path=local_path, b2_folder_path=b2_path)

        self.log.info(f"Backup is finished in {time.time()-start_timestamp:.4f} seconds!")

    def run(self):
        if self.interval > 0:
            while True:
                self.push_all()
                time.sleep(self.interval)
