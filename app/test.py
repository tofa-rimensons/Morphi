import os
import logging
from dotenv import load_dotenv

from repos.GoogleDriveRepo import GoogleDriveRepo  # your updated class file

# Setup logging to a file
logging.basicConfig(
    filename='test.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    load_dotenv()

    # Load folder IDs from env
    DB_FOLDER = os.getenv('DB_FOLDER')
    CONFIG_FOLDER = os.getenv('CONFIG_FOLDER')
    IMAGE_FOLDER = os.getenv('IMAGE_FOLDER')
    VOCALS_FOLDER = os.getenv('VOCALS_FOLDER')
    LOG_FOLDER = os.getenv('LOG_FOLDER')

    if not all([DB_FOLDER, CONFIG_FOLDER, IMAGE_FOLDER, LOG_FOLDER]):
        logging.error("One or more folder IDs missing in .env")
        return

    creds_path = 'service_account.json'

    # Initialize GoogleDriveRepo with the logger
    drive_repo = GoogleDriveRepo(creds_path, logging)

    # Example files and contents
    db_file_name = 'db_dump.sql'
    db_file_content = b'-- Example DB dump content\nCREATE TABLE test(id INT);'

    config_file_name = 'config.json'
    config_file_content = b'{ "setting1": true, "setting2": "value" }'

    image_file_name = 'image.jpg'
    try:
        with open(image_file_name, 'rb') as f:
            image_file_content = f.read()
    except FileNotFoundError:
        logging.error(f"Test image file '{image_file_name}' not found")
        return

    # Upload files
    try:
        db_file_id = drive_repo.upload_file_from_bytes(db_file_content, db_file_name, DB_FOLDER, 'application/sql')
        logging.info(f"DB dump uploaded: {db_file_name} with ID {db_file_id}")

        config_file_id = drive_repo.upload_file_from_bytes(config_file_content, config_file_name, CONFIG_FOLDER, 'application/json')
        logging.info(f"Config file uploaded: {config_file_name} with ID {config_file_id}")

        image_file_id = drive_repo.upload_file_from_bytes(image_file_content, image_file_name, IMAGE_FOLDER, 'image/jpeg')
        logging.info(f"Image file uploaded: {image_file_name} with ID {image_file_id}")

        # Close and flush logging handlers so log file content is complete
        for handler in logging.root.handlers[:]:
            handler.close()
            logging.root.removeHandler(handler)

        with open('test.log', 'rb') as logf:
            log_content = logf.read()
        log_file_id = drive_repo.upload_file_from_bytes(log_content, 'test.log', LOG_FOLDER, 'text/plain')
        print("Uploaded log file with ID:", log_file_id)

    except Exception as e:
        logging.error(f"Error uploading files: {e}")
        return

    # Download files to verify
    try:
        drive_repo.download_file(db_file_id, 'downloaded_db_dump.sql')
        drive_repo.download_file(config_file_id, 'downloaded_config.json')
        drive_repo.download_file(image_file_id, 'downloaded_image.jpg')

        logging.info("Downloaded all files successfully for verification.")
    except Exception as e:
        logging.error(f"Error downloading files: {e}")

if __name__ == '__main__':
    main()
