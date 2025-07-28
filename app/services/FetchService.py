from repos.BackblazeRepo import BackblazeRepo
import os

class FetchService:
    def __init__(self):
        self.repo = BackblazeRepo()

        self.db_folder = os.getenv('DB_FOLDER')
        self.config_folder = os.getenv('CONFIG_FOLDER')
        self.log_folder = os.getenv('LOG_FOLDER')

    def fetch_files(self, local_folder_path: str, b2_folder_path: str):
        files_to_download = self.repo.get_files_in_folder(folder_path=b2_folder_path)

        os.makedirs(local_folder_path, exist_ok=True)

        for filename, key in files_to_download.items():
            data = self.repo.download_file_to_bytes(key)

            local_path = os.path.join(local_folder_path, filename)
            with open(local_path, "wb") as f:
                f.write(data)

    def fetch_all(self):
        folders_to_setup = [
            (self.db_folder, "Data/database/"),
            (self.config_folder, "Data/config/"),
            (self.log_folder, "Data/logs/")
        ]

        for b2_folder, local_path in folders_to_setup:
            self.fetch_files(local_folder_path=local_path, b2_folder_path=b2_folder)
