"""專案常數。端點契約集中於 tped.acquire.discover；此處只放不會隨站方改版而變的設定。"""

from datetime import timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TZ = timezone(timedelta(hours=8), "Asia/Taipei")

BASE_URL = "https://wwwq.moex.gov.tw/exam/"
USER_AGENT = (
    "taiwan-pharmacist-exam-data/0.1 "
    "(+https://github.com/liangRxdev/taiwan-pharmacist-exam-data)"
)
REQUEST_INTERVAL_S = 1.5
REQUEST_TIMEOUT_S = 60
RETRIES = 3

FIRST_YEAR_ROC = 113
RELEASE_MIN_AGE_DAYS = 90
MOD_RECHECK_MAX_AGE_DAYS = 180

KINDS = ("Q", "ANS", "MOD")
# 站方 t= 參數 ↔ 本專案 kind
T_PARAM = {"Q": "Q", "ANS": "S", "MOD": "M"}

MANIFEST_PATH = ROOT / "manifest.json"
SUBJECTS_PATH = ROOT / "subjects.json"
INPUTS_EXAMS_PATH = ROOT / "inputs" / "exams.json"
RAW_DIR = ROOT / "raw"
PAGES_DIR = RAW_DIR / "pages"
