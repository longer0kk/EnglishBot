import os
from dotenv import load_dotenv
from aiogram.fsm.state import StatesGroup, State

load_dotenv()

class QuizStates(StatesGroup):
    waiting_for_word_translation = State()
    waiting_for_tense_answer = State()

# FSM States used in settings menu
class SettingsStates(StatesGroup):
    waiting_for_words_per_day = State()
    waiting_for_tenses_per_day = State()
    waiting_for_split = State()
    waiting_for_specific_weight = State()
    waiting_for_all_weights_step = State()
    waiting_for_word_delete = State()
    waiting_for_min_gap = State()

ENGLISH_BOT_TOKEN = os.getenv("ENGLISH_BOT_TOKEN", "ENGLISH_BOT_TOKEN")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")

admin_env = os.getenv("ADMIN_ID", "0").strip()
ADMIN_ID = int(admin_env) if admin_env.isdigit() else 0

ACTIVE_HOURS = (9, 20)

WORDS_PER_DAY = 10

TENSES_PER_DAY = 5

MIN_GAP_MINUTES = 20

QUEUE_BUFFER_SECONDS = 7

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "english_bot.db")
DATABASE_URL = f"sqlite+aiosqlite:///{DB_PATH}"

SRS_INTERVALS = {
    0: 1,    # Stage 0: review next day
    1: 3,    # Stage 1: review in 3 days
    2: 7,    # Stage 2: review in 7 days
    3: 14,   # Stage 3: review in 14 days
    4: 30,   # Stage 4: review in 30 days
    5: 60,   # Stage 5: review in 60 days
    6: 120,  # Stage 6: review in 120 days
}

# The 12 tenses and their selection weights (must sum to 1.0 or we normalize them)
TENSE_WEIGHTS = {
    "Present Simple": 0.20,
    "Present Continuous": 0.15,
    "Present Perfect": 0.10,
    "Present Perfect Continuous": 0.05,
    "Past Simple": 0.15,
    "Past Continuous": 0.10,
    "Past Perfect": 0.05,
    "Past Perfect Continuous": 0.03,
    "Future Simple": 0.10,
    "Future Continuous": 0.04,
    "Future Perfect": 0.02,
    "Future Perfect Continuous": 0.01,
}
