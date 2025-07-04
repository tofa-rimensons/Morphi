from multiprocessing import Process
import json
import logging
from services.BackupService import BackupService
from services.FetchService import FetchService

class Main:
    @staticmethod
    def setup_logging():
        logging.basicConfig(
            filename='Data/logs/logs.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

    @staticmethod
    def fetch_data():
        fetch_service = FetchService()
        fetch_service.fetch_all()

    @staticmethod
    def startup_backup():
        Main.setup_logging()

        with open('Data/config/config.json', 'r') as f:
            interval = json.load(f)['backup_interval']

        backup_service = BackupService(logging, interval)
        backup_service.run()






if __name__ == "__main__":
    Main.fetch_data()

    logging.basicConfig(
            filename='Data/logs/logs.log',
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )
    
    backuper = Process(target=Main.startup_backup)

    logging.info("Starting up...")
    logging.info("Activating backuper...")
    backuper.start()
    logging.info("Backuper is activated!")

