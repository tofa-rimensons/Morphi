import io
import os
from dotenv import load_dotenv
from repos.CryptographyRepo import CryptographyRepo
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2 import service_account

class GoogleDriveRepo:
    def __init__(self, credentials_json_path: str="Data/config/service_account.json"):
        """
        Initialize Google Drive API client with Service Account credentials.
        
        :param credentials_json_path: Path to service account JSON key file
        :param folder_id: ID of the folder in Google Drive where files will be saved
        """
        load_dotenv()
        self.cryptography_repo = CryptographyRepo(password=os.getenv('MASTER_KEY'))

        scopes = ['https://www.googleapis.com/auth/drive']
        credentials = service_account.Credentials.from_service_account_file(
            credentials_json_path, scopes=scopes)
        self.service = build('drive', 'v3', credentials=credentials)

    def upload_file_from_bytes(self, file_bytes: bytes, filename: str, folder_id: str, mime_type: str):
        """
        Upload a file directly from bytes with a given filename and MIME type.

        :param file_bytes: File content in bytes
        :param filename: Name of the file to save in Drive (including extension or none)
        :param mime_type: MIME type of the file (e.g., 'application/octet-stream' for unknown)
        :return: file ID string
        """
        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        file_stream = self.cryptography_repo.resize_and_optimize_if_image(file_bytes)
        file_stream_encrypted = self.cryptography_repo.encrypt_file(file_stream)
        media = MediaIoBaseUpload(file_stream_encrypted, mimetype=mime_type)

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        return file.get('id')

    def download_file_to_bytes(self, file_id) -> bytes:
        """
        Downloads a file from Google Drive by its ID and returns bytes.

        :param file_id: ID of the file in Drive
        :return: File content as bytes
        """
        request = self.service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        fh.seek(0)

        data_encrypted = fh.read()
        data = self.cryptography_repo.decrypt_file(data_encrypted)
        
        return data
