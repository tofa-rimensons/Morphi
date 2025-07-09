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
                    timestamp_joined INTEGER DEFAULT (strftime('%s','now')),
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
                    timestamp INTEGER DEFAULT (strftime('%s','now')),
                    user_id VARCHAR(64),
                    hrt_type VARCHAR,
                    hrt_dose_mg REAL,
                    weight_kg REAL,
                    height_cm REAL,
                    bonemass_pct REAL,
                    fat_pct REAL,
                    muscle_pct REAL,
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
        This version is safe from SQL injection.
        """
        allowed_fields = {
            'timestamp_joined', 'is_research_allowed', 'hrt_type', 'hrt_dose',
            'master_interval', 'dose_interval', 'weight_interval', 'height_interval',
            'bonemassFatMuscle_interval', 'chestBustWaistHipThigh_interval',
            'bloodPressure_interval', 'physicalSelfEsteem_interval',
            'menthalSelfEsteem_interval', 'libidoSelfEsteem_interval',
            'voiceFragment_interval', 'photoBody_interval', 'photoFace_interval'
        }

        # Validate column names
        for key in kwargs:
            if key not in allowed_fields:
                raise ValueError(f"Invalid field: {key}")

        encrypted_user_id = self.cryptography_repo.encrypt_int(user_id)

        cursor = self.conn.execute(
            "SELECT 1 FROM users WHERE user_id = ?", (encrypted_user_id,))
        exists = cursor.fetchone() is not None

        if exists:
            if kwargs:
                set_clause = ", ".join(f"{key} = ?" for key in kwargs)
                values = list(kwargs.values()) + [encrypted_user_id]
                query = f"UPDATE users SET {set_clause} WHERE user_id = ?"
                with self.conn:
                    self.conn.execute(query, values)
        else:
            columns = ["user_id"] + list(kwargs.keys())
            placeholders = ", ".join("?" for _ in columns)
            values = [encrypted_user_id] + list(kwargs.values())
            # Columns are from validated keys only
            query = f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})"
            with self.conn:
                self.conn.execute(query, values)


    def save_measurement(self, user_id: int, **kwargs):
        """
        Save a measurement for a user.
        Safe version: When inserting, automatically includes hrt_type and hrt_dose from user table.
        """
        if not user_id:
            raise ValueError("user_id must be provided.")

        encrypted_user_id = self.cryptography_repo.encrypt_int(user_id)

        cursor = self.conn.execute("""
            SELECT measurement_id, timestamp
            FROM measurements
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (encrypted_user_id,))
        row = cursor.fetchone()

        update_existing = False
        if row:
            measurement_id, timestamp = row
            last_time = datetime.fromtimestamp(timestamp)
            if datetime.now() - last_time < timedelta(hours=12):
                update_existing = True

        # Validate keys for measurement table
        allowed_measurement_fields = {
            'hrt_type', 'hrt_dose_mg', 'weight_kg', 'height_cm',
            'bonemass_pct', 'fat_pct', 'muscle_pct',
            'chest_cm', 'bust_cm', 'waist_cm', 'hip_cm', 'thigh_cm',
            'systolic_mmhg', 'diastolic_mmhg', 'heartRate_bpm',
            'physicalSelfEsteem', 'menthalSelfEsteem', 'libidoSelfEsteem',
            'voiceFragment_url', 'photoBody_url', 'photoFace_url'
        }

        for key in kwargs:
            if key not in allowed_measurement_fields:
                raise ValueError(f"Invalid measurement field: {key}")

        if update_existing:
            if kwargs:
                set_clause = ", ".join(f"{key} = ?" for key in kwargs)
                values = list(kwargs.values()) + [measurement_id]
                query = f"""
                    UPDATE measurements
                    SET {set_clause}
                    WHERE measurement_id = ?
                """
                with self.conn:
                    self.conn.execute(query, values)
        else:
            # Get hrt_type and hrt_dose from user table
            cursor = self.conn.execute("""
                SELECT hrt_type, hrt_dose
                FROM users
                WHERE user_id = ?
            """, (encrypted_user_id,))
            user_row = cursor.fetchone()
            hrt_type, hrt_dose = user_row if user_row else (None, None)

            keys = ['user_id', 'hrt_type', 'hrt_dose_mg'] + list(kwargs.keys())
            placeholders = ", ".join("?" for _ in keys)
            values = [encrypted_user_id, hrt_type, hrt_dose] + list(kwargs.values())

            query = f"""
                INSERT INTO measurements ({', '.join(keys)})
                VALUES ({placeholders})
            """
            with self.conn:
                self.conn.execute(query, values)



    def get_measurements_df(self, user_id):
        """
        Returns a DataFrame of all measurement rows for the user,
        excluding 'user_id' and any URL columns (ending with '_url').
        """
        encrypted_user_id = self.cryptography_repo.encrypt_int(user_id)

        # Get all column names from measurements table
        cursor = self.conn.execute("PRAGMA table_info(measurements)")
        all_columns = [row[1] for row in cursor.fetchall()]

        # Exclude user_id and URL columns
        selected_columns = [
            col for col in all_columns
            if col != 'user_id' and not col.endswith('_url')
        ]

        columns_str = ", ".join(selected_columns)

        query = f"""
            SELECT {columns_str}
            FROM measurements
            WHERE user_id = ?
            ORDER BY timestamp DESC
        """

        return pd.read_sql_query(query, self.conn, params=(encrypted_user_id,))

    
    def get_measurement_values(self, user_id: int, col_name_list: list[str]) -> list:
        """
        Returns a flat list of all non-null values for the given columns,
        for the specified user, ordered by timestamp descending.
        """

        allowed_measurement_fields = {
            'hrt_type', 'hrt_dose_mg', 'weight_kg', 'height_cm',
            'bonemass_pct', 'fat_pct', 'muscle_pct',
            'chest_cm', 'bust_cm', 'waist_cm', 'hip_cm', 'thigh_cm',
            'systolic_mmhg', 'diastolic_mmhg', 'heartRate_bpm',
            'physicalSelfEsteem', 'menthalSelfEsteem', 'libidoSelfEsteem',
            'voiceFragment_url', 'photoBody_url', 'photoFace_url'
        }

        for col in col_name_list:
            if col not in allowed_measurement_fields:
                raise ValueError(f"Invalid measurement field: {col}")

        encrypted_user_id = self.cryptography_repo.encrypt_int(user_id)

        # Build query: SELECT timestamp, col1, col2, ...
        columns_str = ", ".join(col_name_list)
        query = f"""
            SELECT timestamp, {columns_str}
            FROM measurements
            WHERE user_id = ?
            ORDER BY timestamp DESC
        """

        cursor = self.conn.execute(query, (encrypted_user_id,))

        # Flatten: keep values by timestamp order, all non-null values
        results = []
        for row in cursor.fetchall():
            # row[0] is timestamp, row[1:] are the values
            values = row[1:]
            results.extend([v for v in values if v is not None])

        return results

    
    def get_last_measurement(self, user_id: int) -> dict | None:
        encrypted_user_id = self.cryptography_repo.encrypt_int(user_id)

        cursor = self.conn.execute("""
            SELECT *
            FROM measurements
            WHERE user_id = ?
            ORDER BY timestamp DESC
            LIMIT 1
        """, (encrypted_user_id,))

        row = cursor.fetchone()
        if not row:
            return None

        columns = [desc[0] for desc in cursor.description]
        return dict(zip(columns, row))

    
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

    def get_due_measurements(self, user_id: int):
        """
        Returns a list of measurement names (e.g. 'weight_kg') where:
        - The user's interval is not 0 or None
        - And the number of measurements since it was last recorded (inclusive) >= interval
        """

        encrypted_user_id = self.cryptography_repo.encrypt_int(user_id)

        # Get the user's interval settings
        cursor = self.conn.execute("""
            SELECT * FROM users WHERE user_id = ?
        """, (encrypted_user_id,))
        user_row = cursor.fetchone()
        if not user_row:
            return []

        # Get column names
        columns = [desc[0] for desc in cursor.description]
        user_data = dict(zip(columns, user_row))

        # Map measurements to their _interval fields
        measurement_intervals = {
            'weight_kg': user_data.get('weight_interval'),
            'height_cm': user_data.get('height_interval'),
            'bonemass_pct': user_data.get('bonemassFatMuscle_interval'),
            'fat_pct': user_data.get('bonemassFatMuscle_interval'),
            'muscle_pct': user_data.get('bonemassFatMuscle_interval'),
            'chest_cm': user_data.get('chestBustWaistHipThigh_interval'),
            'bust_cm': user_data.get('chestBustWaistHipThigh_interval'),
            'waist_cm': user_data.get('chestBustWaistHipThigh_interval'),
            'hip_cm': user_data.get('chestBustWaistHipThigh_interval'),
            'thigh_cm': user_data.get('chestBustWaistHipThigh_interval'),
            'systolic_mmhg': user_data.get('bloodPressure_interval'),
            'diastolic_mmhg': user_data.get('bloodPressure_interval'),
            'heartRate_bpm': user_data.get('bloodPressure_interval'),
            'physicalSelfEsteem': user_data.get('physicalSelfEsteem_interval'),
            'menthalSelfEsteem': user_data.get('menthalSelfEsteem_interval'),
            'libidoSelfEsteem': user_data.get('libidoSelfEsteem_interval'),
            'voiceFragment_url': user_data.get('voiceFragment_interval'),
            'photoBody_url': user_data.get('photoBody_interval'),
            'photoFace_url': user_data.get('photoFace_interval'),
        }

        due_measurements = []

        for measurement, interval in measurement_intervals.items():
            if not interval or interval == 0:
                continue  # skip if interval is None or 0

            # Find last timestamp this measurement had a non-null value
            cursor = self.conn.execute(f"""
                SELECT timestamp
                FROM measurements
                WHERE user_id = ?
                AND {measurement} IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 1
            """, (encrypted_user_id,))
            row = cursor.fetchone()

            if row:
                last_timestamp = row[0]
                # Count how many measurements since (inclusive)
                cursor = self.conn.execute("""
                    SELECT COUNT(*)
                    FROM measurements
                    WHERE user_id = ?
                    AND timestamp >= ?
                """, (encrypted_user_id, last_timestamp))
                count = cursor.fetchone()[0]
            else:
                # If never recorded, treat it as due immediately
                count = interval

            if count >= interval:
                due_measurements.append(measurement.split('_')[0])

        return due_measurements
