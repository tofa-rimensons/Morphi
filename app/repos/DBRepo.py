import sqlite3
import os
import pandas as pd
from datetime import datetime, timedelta
from repos.CryptographyRepo import CryptographyRepo

class DBRepo:
    def __init__(self, db_path='Data/database/database.db'):
        self.cryptography_repo = CryptographyRepo(os.getenv('MASTER_KEY'))
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._initialize_db()

    def _initialize_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(64) PRIMARY KEY,
                    timestamp_joined INTEGER,
                    is_research_allowed BOOLEAN,
                    hrt_type VARCHAR,
                    hrt_dose REAL,
                    master_interval INTEGER,
                    weight_interval INTEGER,
                    height_interval INTEGER,
                    bonemassFatMuscle_interval INTEGER,
                    chestBustWaistHipThigh_interval INTEGER,
                    bloodPressure_interval INTEGER,
                    physicalSelfEsteem_interval INTEGER,
                    menthalSelfEsteem_interval INTEGER,
                    libidoSelfEsteem_interval INTEGER,
                    voiceFragment_interval INTEGER,
                    photoBody_interval INTEGER,
                    photoFace_interval INTEGER
                );
            """)
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS measurements (
                    measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp INTEGER DEFAULT CURRENT_TIMESTAMP,
                    user_id VARCHAR(64),
                    hrt_type VARCHAR,
                    hrt_dose_mg REAL,
                    weight_kg REAL,
                    height_cm REAL,
                    bonemass_prc REAL,
                    fat_prc REAL,
                    muscle_prc REAL,
                    chest_cm REAL,
                    bust_cm REAL,
                    waist_cm REAL,
                    hip_cm REAL,
                    thigh_cm REAL,
                    systolic_mmhg INTEGER,
                    diastolic_mmhg INTEGER,
                    heartRate_bpm INTEGER,
                    physicalSelfEsteem INTEGER,
                    menthalSelfEsteem INTEGER,
                    libidoSelfEsteem INTEGER,
                    voiceFragment_url TEXT,
                    photoBody_url TEXT,
                    photoFace_url TEXT,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                );
            """)

    def set_user_data(self, user_id: int, **kwargs):
        """
        Insert or update user data. 
        Pass user_id and any other fields as keyword arguments.
        """
        fields = ['timestamp_joined', 'is_research_allowed', 'hrt_type', 'hrt_dose',
                'master_interval', 'dose_interval', 'weight_interval', 'height_interval',
                'bonemassFatMuscle_interval', 'chestBustWaistHipThigh_interval',
                'bloodPressure_interval', 'physicalSelfEsteem_interval',
                'menthalSelfEsteem_interval', 'libidoSelfEsteem_interval',
                'voiceFragment_interval', 'photoBody_interval', 'photoFace_interval']

        # Validate keys
        for key in kwargs:
            if key not in fields:
                raise ValueError(f"Invalid field: {key}")

        user_id = self.cryptography_repo.encrypt_int(user_id)
        # Check if user exists
        cursor = self.conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        exists = cursor.fetchone() is not None

        if exists:
            # Update only provided fields
            if kwargs:
                set_clause = ", ".join(f"{key} = ?" for key in kwargs)
                values = list(kwargs.values())
                values.append(user_id)
                query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
                with self.conn:
                    self.conn.execute(query, values)
        else:
            # Insert new user with provided fields
            columns = ["user_id"] + list(kwargs.keys())
            placeholders = ", ".join("?" for _ in columns)
            values = [user_id] + list(kwargs.values())
            query = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})"
            with self.conn:
                self.conn.execute(query, values)


    def save_measurement(self, user_id: int, **kwargs):
        """
        Save a measurement for a user.
        - If the last measurement is less than 12 hours old, update it.
        - Otherwise, insert a new measurement.
        """

        # Make sure user_id is provided
        if not user_id:
            raise ValueError("user_id must be provided.")
        
        user_id = self.cryptography_repo.encrypt_int(user_id)

        # Check if there is a measurement for this user in the last 12 hours
        cursor = self.conn.execute("""
            SELECT measurement_id, timestamp FROM measurements
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (user_id,))
        row = cursor.fetchone()

        update_existing = False
        if row:
            measurement_id, timestamp = row
            last_time = datetime.fromtimestamp(timestamp)
            if datetime.now() - last_time < timedelta(hours=12):
                update_existing = True

        if update_existing:
            # Update existing measurement
            if kwargs:
                set_clause = ', '.join(f"{key} = ?" for key in kwargs)
                values = list(kwargs.values())
                values.append(measurement_id)
                with self.conn:
                    self.conn.execute(f"""
                        UPDATE measurements SET {set_clause}
                        WHERE measurement_id = ?
                    """, values)
        else:
            # Insert new measurement
            keys = ', '.join(['user_id'] + list(kwargs.keys()))
            placeholders = ', '.join(['?'] * (len(kwargs) + 1))
            values = [user_id] + list(kwargs.values())

            with self.conn:
                self.conn.execute(f"""
                    INSERT INTO measurements ({keys})
                    VALUES ({placeholders})
                """, values)


    def get_measurements_df(self, user_id):
        user_id = self.cryptography_repo.encrypt_int(user_id)
        query = """
            SELECT * FROM measurements
            WHERE user_id = ?
            ORDER BY timestamp DESC
        """
        return pd.read_sql_query(query, self.conn, params=(user_id,))
    
    def get_measurements_row_count(self, user_id):
        user_id = self.cryptography_repo.encrypt_int(user_id)
        query = """
            SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
            FROM measurements
            WHERE user_id = ?
        """
        cursor = self.conn.execute(query, (user_id,))
        row_count, first_measurement, last_measurement = cursor.fetchone()
        return row_count, first_measurement, last_measurement

    def get_user_dict(self, user_id):
        encrypted_user_id = self.cryptography_repo.encrypt_int(user_id)
        query = "SELECT * FROM users WHERE user_id = ?"
        cursor = self.conn.execute(query, (encrypted_user_id,))
        result = cursor.fetchone()

        if result is None:
            # No user found, create a new user with default values
            default_values = {
                "user_id": encrypted_user_id,
                "timestamp_joined": int(datetime.now().timestamp()),
                "is_research_allowed": False,
                "hrt_type": None,
                "hrt_dose": None,
                "master_interval": 1,
                "weight_interval": None,
                "height_interval": None,
                "bonemassFatMuscle_interval": None,
                "chestBustWaistHipThigh_interval": None,
                "bloodPressure_interval": None,
                "physicalSelfEsteem_interval": None,
                "menthalSelfEsteem_interval": None,
                "libidoSelfEsteem_interval": None,
                "voiceFragment_interval": None,
                "photoBody_interval": None,
                "photoFace_interval": None
            }
            columns = ", ".join(default_values.keys())
            placeholders = ", ".join("?" for _ in default_values)
            values = list(default_values.values())

            with self.conn:
                self.conn.execute(f"INSERT INTO users ({columns}) VALUES ({placeholders})", values)

            # Fetch the newly created user
            cursor = self.conn.execute(query, (encrypted_user_id,))
            result = cursor.fetchone()

        # Fetch columns names from cursor description
        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, result)) if result else None

    def delete_user_data(self, user_id: int):
        encrypted_user_id = self.cryptography_repo.encrypt_int(user_id)
        with self.conn:
            self.conn.execute("DELETE FROM measurements WHERE user_id = ?", (encrypted_user_id,))
            self.conn.execute("DELETE FROM users WHERE user_id = ?", (encrypted_user_id,))