import sqlite3
import os
import pandas as pd

class DBRepo:
    def __init__(self, db_path='Data/database/database.db'):
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self._initialize_db()

    def _initialize_db(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id VARCHAR(50) NOT NULL,
                    timestamp_joined INTEGER,
                    is_research_allowed BOOLEAN,
                    hrt_type INTEGER,
                    constant_dose BOOLEAN,
                    interview_timeslot INTEGER,
                    dose_interval INTEGER,
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
                    user_id INTEGER,
                    dose_mg REAL,
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

    def save_user(self, **kwargs):
        keys = ', '.join(kwargs.keys())
        placeholders = ', '.join(['?'] * len(kwargs))
        values = list(kwargs.values())

        with self.conn:
            self.conn.execute(f"""
                INSERT INTO users ({keys}) VALUES ({placeholders})
            """, values)

    def save_measurement(self, user_id, **kwargs):
        keys = ', '.join(['user_id'] + list(kwargs.keys()))
        placeholders = ', '.join(['?'] * (len(kwargs) + 1))
        values = [user_id] + list(kwargs.values())

        with self.conn:
            self.conn.execute(f"""
                INSERT INTO measurements ({keys}) VALUES ({placeholders})
            """, values)

    def get_measurements_df(self, user_id):
        query = """
            SELECT * FROM measurements
            WHERE user_id = ?
            ORDER BY timestamp DESC
        """
        return pd.read_sql_query(query, self.conn, params=(user_id,))

    def get_user_dict(self, user_id):
        query = "SELECT * FROM users WHERE user_id = ?"
        result = self.conn.execute(query, (user_id,)).fetchone()
        if result:
            columns = [desc[0] for desc in self.conn.execute(query, (user_id,)).description]
            return dict(zip(columns, result))
        return None
