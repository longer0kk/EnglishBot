import datetime
import json
from sqlalchemy import String, Integer, DateTime, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import config

# Create Async Engine and Session Maker
engine = create_async_engine(config.DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)

# Declarative Base
class Base(DeclarativeBase):
    pass

# Word model representing vocabulary words in the Spaced Repetition System
class Word(Base):
    __tablename__ = "words"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    word: Mapped[str] = mapped_column(String, unique=True, index=True)
    translation: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)  # Very brief context
    interval_stage: Mapped[int] = mapped_column(Integer, default=0)
    next_review_datetime: Mapped[datetime.datetime] = mapped_column(DateTime)

# TenseRule model representing static grammar rules and formulas for English tenses
class TenseRule(Base):
    __tablename__ = "tense_rules"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    tense_name: Mapped[str] = mapped_column(String, unique=True)
    description: Mapped[str] = mapped_column(String)  # Short grammar explanation
    structure_formula: Mapped[str] = mapped_column(String)  # Grammar formula (e.g., S + V/V-es)

# BotSettings model representing configurable settings for the English bot
class BotSettings(Base):
    __tablename__ = "bot_settings"
    
    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    words_per_day: Mapped[int] = mapped_column(Integer, default=10)
    tenses_per_day: Mapped[int] = mapped_column(Integer, default=5)
    fill_in_blank_percentage: Mapped[int] = mapped_column(Integer, default=80)
    tense_weights: Mapped[str] = mapped_column(String)  # JSON string representation
    min_gap_minutes: Mapped[int] = mapped_column(Integer, default=config.MIN_GAP_MINUTES)

# Database Initialization
async def init_db():
    # Create tables if they do not exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    # Populate the 12 static tense rules if the table is currently empty
    async with async_session() as session:
        result = await session.execute(select(TenseRule))
        existing_rules = result.scalars().all()
        if not existing_rules:
            default_rules = [
                TenseRule(
                    tense_name="Present Simple",
                    description="Used for general truths, habits, and permanent states.",
                    structure_formula="S + V/V-es (he/she/it adds -s)"
                ),
                TenseRule(
                    tense_name="Present Continuous",
                    description="Used for actions happening right now or temporary situations.",
                    structure_formula="S + am/is/are + V-ing"
                ),
                TenseRule(
                    tense_name="Present Perfect",
                    description="Used for past actions with a direct result or relevance in the present.",
                    structure_formula="S + have/has + V-ed/V3"
                ),
                TenseRule(
                    tense_name="Present Perfect Continuous",
                    description="Used for actions that started in the past and are still continuing or have just finished with visible results.",
                    structure_formula="S + have/has + been + V-ing"
                ),
                TenseRule(
                    tense_name="Past Simple",
                    description="Used for completed actions at a specific time in the past.",
                    structure_formula="S + V-ed/V2"
                ),
                TenseRule(
                    tense_name="Past Continuous",
                    description="Used for ongoing actions interrupted by another past action or happening at a specific time in the past.",
                    structure_formula="S + was/were + V-ing"
                ),
                TenseRule(
                    tense_name="Past Perfect",
                    description="Used to describe an action that was completed before another past action occurred.",
                    structure_formula="S + had + V-ed/V3"
                ),
                TenseRule(
                    tense_name="Past Perfect Continuous",
                    description="Used to show that an action started in the past and continued up until another time in the past.",
                    structure_formula="S + had + been + V-ing"
                ),
                TenseRule(
                    tense_name="Future Simple",
                    description="Used for future predictions, instant decisions, promises, and offers.",
                    structure_formula="S + will + V"
                ),
                TenseRule(
                    tense_name="Future Continuous",
                    description="Used for actions that will be in progress at a specific time in the future.",
                    structure_formula="S + will + be + V-ing"
                ),
                TenseRule(
                    tense_name="Future Perfect",
                    description="Used to describe an action that will be completed before a certain point in the future.",
                    structure_formula="S + will + have + V-ed/V3"
                ),
                TenseRule(
                    tense_name="Future Perfect Continuous",
                    description="Used to show that an action will continue up until a particular event or time in the future.",
                    structure_formula="S + will + have + been + V-ing"
                )
            ]
            session.add_all(default_rules)
            await session.commit()
            
    # Initialize BotSettings singleton row
    await get_settings()

# CRUD Functions

async def add_word(word: str, translation: str, description: str) -> Word:
    """Adds a new word to the database and schedules it for review in 1 day."""
    async with async_session() as session:
        clean_word = word.strip().lower()
        
        # Check if the word is already present
        result = await session.execute(select(Word).where(Word.word == clean_word))
        existing_word = result.scalar_one_or_none()
        if existing_word:
            return existing_word
        
        # Initial review schedule is tomorrow (24 hours from now)
        next_review = datetime.datetime.now() + datetime.timedelta(days=1)
        new_word = Word(
            word=clean_word,
            translation=translation.strip(),
            description=description.strip(),
            interval_stage=0,
            next_review_datetime=next_review
        )
        session.add(new_word)
        await session.commit()
        await session.refresh(new_word)
        return new_word

async def get_word_by_word(word: str) -> Word | None:
    """Retrieves a word entry by its text."""
    async with async_session() as session:
        clean_word = word.strip().lower()
        result = await session.execute(select(Word).where(Word.word == clean_word))
        return result.scalar_one_or_none()

async def get_word_by_id(word_id: int) -> Word | None:
    """Retrieves a word entry by its unique database ID."""
    async with async_session() as session:
        result = await session.execute(select(Word).where(Word.id == word_id))
        return result.scalar_one_or_none()

async def update_word_review(word_id: int, correct: bool) -> Word | None:
    """Updates the word's SRS stage and next review time based on answer correctness."""
    async with async_session() as session:
        result = await session.execute(select(Word).where(Word.id == word_id))
        word_entry = result.scalar_one_or_none()
        if not word_entry:
            return None
        
        if correct:
            # Shift to the next interval stage
            word_entry.interval_stage += 1
        else:
            # Reset stage to 0 on failure
            word_entry.interval_stage = 0
            
        # Get the delay duration in days
        days_delay = config.SRS_INTERVALS.get(word_entry.interval_stage, 120)
        word_entry.next_review_datetime = datetime.datetime.now() + datetime.timedelta(days=days_delay)
        
        await session.commit()
        await session.refresh(word_entry)
        return word_entry

async def get_due_words(limit: int) -> list[Word]:
    """Retrieves up to `limit` words that are due or overdue for review."""
    async with async_session() as session:
        now = datetime.datetime.now()
        result = await session.execute(
            select(Word)
            .where(Word.next_review_datetime <= now)
            .order_by(Word.next_review_datetime.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

async def get_tense_rule(tense_name: str) -> TenseRule | None:
    """Retrieves static grammar rule information by tense name."""
    async with async_session() as session:
        result = await session.execute(select(TenseRule).where(TenseRule.tense_name == tense_name))
        return result.scalar_one_or_none()

async def get_db_stats() -> dict:
    """Retrieves basic database statistics like word counts and stages."""
    async with async_session() as session:
        # Fetch all words
        result = await session.execute(select(Word))
        words = result.scalars().all()
        total_words = len(words)
        
        # Count due words
        now = datetime.datetime.now()
        due_result = await session.execute(select(Word).where(Word.next_review_datetime <= now))
        due_words = len(due_result.scalars().all())
        
        # Count words per SRS stage
        stages = {}
        for w in words:
            stages[w.interval_stage] = stages.get(w.interval_stage, 0) + 1
            
        return {
            "total_words": total_words,
            "due_words": due_words,
            "stages": stages
        }

async def get_settings() -> BotSettings:
    """Retrieves the singleton BotSettings row. If it doesn't exist, initializes it with config defaults."""
    async with async_session() as session:
        result = await session.execute(select(BotSettings).where(BotSettings.id == 1))
        settings = result.scalar_one_or_none()
        if not settings:
            # Create default settings using config.py
            settings = BotSettings(
                id=1,
                words_per_day=config.WORDS_PER_DAY,
                tenses_per_day=config.TENSES_PER_DAY,
                fill_in_blank_percentage=80,  # default split: 80% fill_in_the_blank
                tense_weights=json.dumps(config.TENSE_WEIGHTS),
                min_gap_minutes=config.MIN_GAP_MINUTES
            )
            session.add(settings)
            await session.commit()
            await session.refresh(settings)
        return settings

async def update_settings(words_per_day: int = None, tenses_per_day: int = None, fill_in_blank_percentage: int = None, tense_weights: dict = None, min_gap_minutes: int = None):
    """Updates BotSettings with any provided values."""
    async with async_session() as session:
        result = await session.execute(select(BotSettings).where(BotSettings.id == 1))
        settings = result.scalar_one_or_none()
        if not settings:
            # Initialize if not exists
            settings = BotSettings(
                id=1,
                words_per_day=words_per_day if words_per_day is not None else config.WORDS_PER_DAY,
                tenses_per_day=tenses_per_day if tenses_per_day is not None else config.TENSES_PER_DAY,
                fill_in_blank_percentage=fill_in_blank_percentage if fill_in_blank_percentage is not None else 80,
                tense_weights=json.dumps(tense_weights) if tense_weights is not None else json.dumps(config.TENSE_WEIGHTS),
                min_gap_minutes=min_gap_minutes if min_gap_minutes is not None else config.MIN_GAP_MINUTES
            )
            session.add(settings)
        else:
            if words_per_day is not None:
                settings.words_per_day = words_per_day
            if tenses_per_day is not None:
                settings.tenses_per_day = tenses_per_day
            if fill_in_blank_percentage is not None:
                settings.fill_in_blank_percentage = fill_in_blank_percentage
            if tense_weights is not None:
                settings.tense_weights = json.dumps(tense_weights)
            if min_gap_minutes is not None:
                settings.min_gap_minutes = min_gap_minutes
        await session.commit()

async def delete_word(word_text: str) -> bool:
    """Finds a word by its text, deletes it from the database, and returns True. Returns False if not found."""
    async with async_session() as session:
        clean_word = word_text.strip().lower()
        result = await session.execute(select(Word).where(Word.word == clean_word))
        word_entry = result.scalar_one_or_none()
        if not word_entry:
            return False
        await session.delete(word_entry)
        await session.commit()
        return True

