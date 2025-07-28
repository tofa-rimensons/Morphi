import os
import io
from repos.CryptographyRepo import CryptographyRepo
from b2sdk.v2 import InMemoryAccountInfo, B2Api, UploadSourceBytes

        

class BackblazeRepo:
    def __init__(self):
        # Load B2 credentials from env
        app_key_id = os.getenv('B2_KEY_ID')
        app_key = os.getenv('B2_APP_KEY')
        self.bucket_name = os.getenv('B2_BUCKET_NAME')

        if not all([app_key_id, app_key, self.bucket_name]):
            raise ValueError("Missing B2 credentials or bucket name in environment variables.")

        # Auth and initialize B2
        info = InMemoryAccountInfo()
        self.b2_api = B2Api(info)
        self.b2_api.authorize_account("production", app_key_id, app_key)

        # Get bucket
        self.bucket = self.b2_api.get_bucket_by_name(self.bucket_name)

        # Initialize your encryption/image handling repo
        self.cryptography_repo = CryptographyRepo(password=os.getenv('MASTER_KEY'))

    def upload_file_from_bytes(self, file_bytes, filename: str, folder_path: str, encode: bool = False, mime_type: str = 'application/octet-stream'):
        """
        Upload file to B2 with optional encryption and image optimization.
        folder_path: relative folder path inside the bucket (e.g., 'Data/logs/')
        """
        # Ensure file_stream is a BytesIO
        if isinstance(file_bytes, bytes):
            file_stream = io.BytesIO(file_bytes)
        elif isinstance(file_bytes, io.BytesIO):
            file_stream = file_bytes
            file_stream.seek(0)
        else:
            raise TypeError(f"file_bytes must be bytes or io.BytesIO, got {type(file_bytes)}")

        # Optional image optimization
        file_stream = self.cryptography_repo.resize_and_optimize_if_image(file_stream)

        # Optional encryption
        if encode:
            file_stream = self.cryptography_repo.encrypt_file(file_stream)

        # Final upload
        file_stream.seek(0)
        full_path = f"{folder_path.rstrip('/')}/{filename}"

        self.bucket.upload(
            UploadSourceBytes(file_stream.read()),
            file_name=full_path,
            content_type=mime_type
        )

    def download_file_to_bytes(self, full_path: str, decode: bool = False) -> bytes:
        buffer = io.BytesIO()  # Create an in-memory bytes buffer
        downloaded_file = self.bucket.download_file_by_name(full_path)
        downloaded_file.save(buffer)  # Save data into buffer
        buffer.seek(0)  # Reset pointer to the start of buffer

        if decode:
            buffer = self.cryptography_repo.decrypt_file(buffer)

        return buffer.getvalue()



    def get_files_in_folder(self, folder_path: str) -> dict:
        """
        List all files in a folder (prefix).
        Returns a dict {filename: full_path}
        """
        files = {}
        for file_version_info, _ in self.bucket.ls(folder_path, recursive=False):
            file_name = os.path.basename(file_version_info.file_name)
            files[file_name] = file_version_info.file_name
        return files

    def delete_file(self, full_path: str):
        """
        Permanently deletes a file from B2.
        """
        file_versions = list(self.bucket.ls(full_path))
        for file_info, _ in file_versions:
            self.bucket.delete_file_version(file_info.id_, file_info.file_name)
