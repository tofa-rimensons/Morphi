import tempfile
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from repos.BackblazeRepo import BackblazeRepo
import os
import pandas as pd
import io
import traceback


class DownloaderService:
    def __init__(self):
        """
        Takes a BackblazeRepo instance.
        """
        self.drive_repo = BackblazeRepo()
        self.temp_folder = 'Data/temp'
        os.makedirs(self.temp_folder, exist_ok=True)  # Ensure temp folder exists
        self.files_folder = os.getenv('FILES_FOLDER')
        if not self.files_folder:
            raise ValueError("FILES_FOLDER environment variable not set")

    def download_file(self, file_id: str, decode: bool = False) -> tuple[bytes, str]:
        """
        Downloads one file and returns (bytes, filename).
        """
        file_bytes = self.drive_repo.download_file_to_bytes(f"{self.files_folder}/{file_id}", decode=decode)
        return file_bytes, file_id

    def download_files_as_zip(
        self,
        zip_name: str,
        file_ids: list[str],
        decode: bool = False,
        file_extension: str = "",
        max_zip_size: int = 200 * 1024 * 1024  # 200 MB by default
    ) -> bytes | str:
        """
        Downloads multiple files in parallel (max 10), zips them on disk, returns zip bytes.
        Adds an extension to all files. Stops adding if max size is exceeded.
        Returns zip bytes or traceback string on error.
        """

        def worker(file_id):
            file_bytes = self.drive_repo.download_file_to_bytes(f"{self.files_folder}/{file_id}", decode=decode)
            return file_bytes, file_id

        tmp_zip_path = os.path.join(self.temp_folder, zip_name)
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

        except Exception:
            tb_str = traceback.format_exc()
            print(tb_str)
            return tb_str

        finally:
            # Clean up temp zip file if it exists
            if os.path.exists(tmp_zip_path):
                try:
                    os.remove(tmp_zip_path)
                except Exception as e:
                    print(f"Failed to remove temp zip file: {e}")

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
