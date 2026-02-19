# safe_logger.py
import csv
import os
from datetime import datetime
from typing import Optional

LOG_FILE = "test_results.csv"
FIELDNAMES = ["timestamp", "captcha_type", "status", "time_taken", "attempts", "notes"]

def init_result_logger(log_file: str = LOG_FILE):
    """Create the CSV with header if it doesn't exist."""
    if not os.path.exists(log_file):
        with open(log_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
            writer.writeheader()

def log_result(captcha_type: str,
               status: str,
               time_taken: float,
               attempts: int = 1,
               notes: Optional[str] = "",
               log_file: str = LOG_FILE):
    """
    Append a single test result row to the CSV.
    - captcha_type: e.g. "text", "recaptcha", "botdetect"
    - status: "success" or "fail" (or custom labels)
    - time_taken: seconds (float)
    - attempts: number of attempts used
    - notes: optional free-text
    """
    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "captcha_type": captcha_type,
        "status": status,
        "time_taken": round(float(time_taken), 3),
        "attempts": int(attempts),
        "notes": notes or ""
    }
    init_result_logger(log_file)
    with open(log_file, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writerow(row)
