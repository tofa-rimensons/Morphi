import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from repos.GoogleDriveRepo import GoogleDriveRepo
import os
import pandas as pd
import io

import traceback


class DownloaderService:
    def __init__(self):
        """
        Takes a GoogleDriveRepo instance.
        """
        self.drive_repo = GoogleDriveRepo()
        self.temp_folder = 'Data/temp'

    def download_file(self, file_id: str, decode: bool = False) -> tuple[bytes, str]:
        """
        Downloads one file and returns (bytes, filename).
        """
        file_bytes = self.drive_repo.download_file_to_bytes(file_id, decode=decode)
        file_name = self.drive_repo.get_filename(file_id)
        return file_bytes, file_name

    def download_files_as_zip(
        self,
        zip_name: str,
        file_ids: list[str],
        decode: bool = False,
        file_extension: str = "",
        max_zip_size: int = 50 * 1024 * 1024  # 50 MB by default
    ) -> bytes:
        """
        Downloads multiple files in parallel (max 10), zips them on disk, returns zip bytes.
        Adds an extension to all files. Stops adding if max size is exceeded.
        """
        def worker(file_id):
            return self.download_file(file_id, decode=decode)

        tmp_zip_path = f"{self.temp_folder}/{zip_name}"
        total_size = 0

        zip_bytes = None

        try:

            with zipfile.ZipFile(tmp_zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zipf:
                with ThreadPoolExecutor(max_workers=10) as executor:
                    futures = [executor.submit(worker, fid) for fid in file_ids]

                    for future in as_completed(futures):
                        file_bytes, file_name = future.result()

                        # Add extension if needed
                        if file_extension and not file_name.endswith(file_extension):
                            file_name += file_extension

                        file_size = len(file_bytes)

                        # Check if adding this file exceeds limit
                        if total_size + file_size > max_zip_size:
                            break

                        zipf.writestr(file_name, file_bytes)
                        total_size += file_size

            # Read zip back
            with open(tmp_zip_path, 'rb') as f:
                zip_bytes = f.read()

        except Exception as e:
            tb_str = traceback.format_exc()  # <-- full traceback as string
            print(tb_str)
            return tb_str  # <-- return if you want the caller to see it

        finally:
            # Clean up
            os.remove(tmp_zip_path)

            return zip_bytes

    def dataframe_to_zip_bytes(self, df: pd.DataFrame, csv_filename="data.csv", zip_filename="data.zip") -> bytes:
        # Create a bytes buffer for the zip file
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            # Save dataframe to csv bytes
            csv_bytes = df.to_csv(index=False).encode('utf-8')
            # Write csv bytes into the zip with the given filename
            zip_file.writestr(csv_filename, csv_bytes)

        zip_buffer.seek(0)
        return zip_buffer.getvalue()