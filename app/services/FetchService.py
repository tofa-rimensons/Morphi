from repos.GoogleDriveRepo import GoogleDriveRepo
import os

class FetchService:
    def __init__(self):
        self.drive_repo = GoogleDriveRepo()

        self.db_folder = os.getenv('DB_FOLDER')
        self.config_folder = os.getenv('CONFIG_FOLDER')
        self.log_folder = os.getenv('LOG_FOLDER')


    def fetch_files(self, local_folder_path: str, folder_id: str):
        files_to_download = self.drive_repo.get_files_in_folder(folder_id=folder_id)

        for name, id in files_to_download.items():
            data = self.drive_repo.download_file_to_bytes(id)

            with open(f"{local_folder_path}/{name}", "wb") as f:
                f.write(data)



    def fetch_all(self):
        folders_to_setup = [
            # (self.db_folder, "Data/database/"),
            (self.config_folder, "Data/config/"),
            (self.log_folder, "Data/logs/")
        ]

        for folder in folders_to_setup:
            self.fetch_files(local_folder_path=folder[1], folder_id=folder[0])



        