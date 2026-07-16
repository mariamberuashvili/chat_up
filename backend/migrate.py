import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST"),
    port=int(os.getenv("DB_PORT", 3306)),
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASSWORD"),
    database=os.getenv("DB_NAME"),
    ssl_disabled=False,
)
cur = conn.cursor()

steps = [
    ("ai_enabled column", "ALTER TABLE rooms ADD COLUMN ai_enabled TINYINT(1) NOT NULL DEFAULT 0"),
    ("ai-bot user", "INSERT IGNORE INTO users (uid, email, display_name, online) VALUES ('ai-bot', 'ai@kaia.app', 'Inteligente IA', 0)"),
    ("tabla pdf_docs", """
        CREATE TABLE IF NOT EXISTS pdf_docs (
          id VARCHAR(32) PRIMARY KEY,
          room_id VARCHAR(255) NOT NULL,
          filename VARCHAR(255) NOT NULL,
          chunks LONGTEXT NOT NULL,
          created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
          INDEX idx_pdf_docs_room (room_id)
        )
    """),
    (
        "columna embeddings en pdf_docs",
        "ALTER TABLE pdf_docs ADD COLUMN embeddings LONGTEXT NULL",
    ),
]

for label, sql in steps:
    try:
        cur.execute(sql)
        conn.commit()
        print(f"OK: {label}")
    except mysql.connector.Error as e:
        if e.errno == 1060:
            print(f"YA EXISTE: {label}")
        else:
            print(f"ERROR: {label} -> {e}")

cur.close()
conn.close()
print("Listo.")
