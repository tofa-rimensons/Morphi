import io
import os
from dotenv import load_dotenv
from repos.CryptographyRepo import CryptographyRepo
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

class GoogleDriveRepo:
    SCOPES = ['https://www.googleapis.com/auth/drive']

    def __init__(self, credentials_json_path: str = "Data/config/credentials.json", token_path: str = "Data/config/token.json"):
        """
        Initialize Google Drive API client with OAuth2 user credentials.

        :param credentials_json_path: Path to OAuth client secrets file (credentials.json)
        :param token_path: Path to store user's access and refresh tokens (token.json)
        """
        load_dotenv()
        self.cryptography_repo = CryptographyRepo(password=os.getenv('MASTER_KEY'))

        self.credentials_json_path = credentials_json_path
        self.token_path = token_path
        self.creds = None

        self._authenticate()
        self.service = build('drive', 'v3', credentials=self.creds, cache_discovery=False)

    def _authenticate(self):
        """Authenticate the user via OAuth2, refreshing or generating tokens as needed."""
        if os.path.exists(self.token_path):
            self.creds = Credentials.from_authorized_user_file(self.token_path, self.SCOPES)
        # If no valid creds or expired, refresh or login again
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_json_path, self.SCOPES)
                self.creds = flow.run_local_server(port=0)
            # Save creds for next time
            with open(self.token_path, 'w') as token_file:
                token_file.write(self.creds.to_json())

    def upload_file_from_bytes(self, file_bytes, filename: str, folder_id: str, encode: bool = False, mime_type: str = 'application/octet-stream'):
        """
        Upload a file from bytes or BytesIO with a given filename and MIME type.

        :param file_bytes: File content, either bytes or io.BytesIO
        :param filename: Name of the file to save in Drive (including extension or none)
        :param encode: Whether to encrypt the file before upload
        :param mime_type: MIME type of the file (e.g., 'application/octet-stream' for unknown)
        :return: file ID string
        """

        # If file_bytes is raw bytes, convert to BytesIO for MediaIoBaseUpload
        if isinstance(file_bytes, bytes):
            file_stream = io.BytesIO(file_bytes)
        elif isinstance(file_bytes, io.BytesIO):
            file_stream = file_bytes
            # Ensure the pointer is at the start
            file_stream.seek(0)
        else:
            raise TypeError(f"file_bytes must be bytes or io.BytesIO, got {type(file_bytes)}")

        # Optional: resize/optimize if image
        file_stream = self.cryptography_repo.resize_and_optimize_if_image(file_stream)

        if encode:
            file_stream = self.cryptography_repo.encrypt_file(file_stream)

        media = MediaIoBaseUpload(file_stream, mimetype=mime_type)

        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }

        file = self.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        return file.get('id')


    def download_file_to_bytes(self, file_id, decode: bool = False) -> bytes:
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

        data = io.BytesIO(fh.read())
        if decode:
            data = self.cryptography_repo.decrypt_file(data)

        return data.getvalue()
    
    def get_filename(self, file_id):
        metadata = self.service.files().get(fileId=file_id, fields="name").execute()
        file_name = metadata.get('name', f'{file_id}')
        return file_name

    def get_files_in_folder(self, folder_id: str) -> dict:
        """
        Get all files id's and names inside a specific Google Drive folder.

        :param folder_id: ID of the Google Drive folder
        """
        query = f"'{folder_id}' in parents and trashed = false"
        results = self.service.files().list(
            q=query,
            spaces='drive',
            fields='files(id, name)',
        ).execute()

        files = results.get('files', [])

        file_ids = {}
        for file in files:
            file_ids[file['name']] = file['id']

        return file_ids

    def delete_file(self, file_id: str):
        self.service.files().delete(fileId=file_id).execute()
