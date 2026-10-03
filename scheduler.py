import asyncio
import datetime
import random
import json
from aiogram import Bot
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.context import FSMContext
from zoneinfo import ZoneInfo

import config
import database
import ai_logic
from config import QuizStates

task_queue = asyncio.Queue()

# In-memory daily schedule list. Each element is a dict:
# {
#     "task_type": "word" | "tense",
#     "item_id": int (word ID) | str (tense name),
#     "scheduled_time": datetime.datetime,
#     "status": "pending" | "queued" | "sent"
# }
daily_tasks = []

# Timestamp when the last proactive message was sent
last_sent_time = datetime.datetime.min

# Keep track of the date we last generated the schedule
last_schedule_date = None
last_reset_date = None


async def clear_task_queue():
    """Empties the global task queue."""
    while not task_queue.empty():
        try:
            task_queue.get_nowait()
            task_queue.task_done()
        except (asyncio.QueueEmpty, ValueError):
            break
    print("🗑️ Task queue has been cleared (Daily 3:00 AM reset).")


async def generate_daily_schedule():
    """Generates the schedule of word reviews and tense tasks for the current day."""
    global daily_tasks
    daily_tasks = []
    
    print("Generating daily schedule...")
    
    # Fetch settings dynamically from the database
    settings = await database.get_settings()
    words_per_day = settings.words_per_day
    tenses_per_day = settings.tenses_per_day
    tense_weights_dict = json.loads(settings.tense_weights)
    
    # 1. Fetch due words from the database
    due_words = await database.get_due_words(words_per_day)
    
    # 2. Pick random tenses using the probability weights
    tenses_pool = list(tense_weights_dict.keys())
    tense_weights = list(tense_weights_dict.values())
    selected_tenses = random.choices(
        tenses_pool, 
        weights=tense_weights, 
        k=tenses_per_day
    )
    
    # Combine tasks into a single pool
    tasks_pool = []
    for word in due_words:
        tasks_pool.append({"task_type": "word", "item_id": word.id})
    for tense_name in selected_tenses:
        tasks_pool.append({"task_type": "tense", "item_id": tense_name})
        
    N = len(tasks_pool)
    if N == 0:
        print("No tasks to schedule for today.")
        return
        
    # Shuffle tasks to mix words and tenses randomly
    random.shuffle(tasks_pool)
    
    # 3. Calculate timing offsets within active hours
    now = datetime.datetime.now(ZoneInfo("Europe/Kyiv"))
    start_dt = now.replace(hour=config.ACTIVE_HOURS[0], minute=0, second=0, microsecond=0)
    end_dt = now.replace(hour=config.ACTIVE_HOURS[1], minute=0, second=0, microsecond=0)
    
    # If the bot is started late in the day, adjust start time to now + 5 minutes
    if now > start_dt:
        start_dt = now + datetime.timedelta(minutes=5)
        
    # Calculate available timeframe in minutes
    total_minutes = int((end_dt - start_dt).total_seconds() / 60)
    
    # Spacing algorithm enforcing MIN_GAP_MINUTES
    min_gap = settings.min_gap_minutes
    required_gap_space = (N - 1) * min_gap
    
    if total_minutes <= 0:
        # If we are past the active hours, schedule them tomorrow (or print warning)
        print("Warning: Currently outside active training hours. Scheduling will resume tomorrow.")
        return
        
    if total_minutes < required_gap_space:
        # Fallback: divide the available window evenly without random offsets
        print("Warning: Active hours window is too small for the minimum gap. Spacing evenly.")
        step = max(1, total_minutes // N)
        scheduled_minutes = [step * i for i in range(N)]
    else:
        # Generate N sorted random points in the remaining free time
        free_time = total_minutes - required_gap_space
        offsets = [random.randint(0, free_time) for _ in range(N)]
        offsets.sort()
        # Add spacing gaps
        scheduled_minutes = [offsets[i] + i * min_gap for i in range(N)]
        
    # Build schedule list
    for i, task_data in enumerate(tasks_pool):
        task_time = start_dt + datetime.timedelta(minutes=scheduled_minutes[i])
        daily_tasks.append({
            "task_type": task_data["task_type"],
            "item_id": task_data["item_id"],
            "scheduled_time": task_time,
            "status": "pending"
        })
        print(f"Scheduled {task_data['task_type']} ({task_data['item_id']}) at {task_time.strftime('%H:%M')}")


async def send_task(bot: Bot, dp, task: dict):
    """Puts a task into the global task queue."""
    task["status"] = "queued"
    task_queue.put_nowait(task)


async def _execute_send_task(bot: Bot, state, user_id: int, task: dict) -> bool:
    """Internal helper to render and transmit a task to the user."""
    global last_sent_time
    
    if task["task_type"] == "word":
        word_entry = await database.get_word_by_id(task["item_id"])
        if not word_entry:
            task["status"] = "failed"
            return True  # Word was deleted in the meantime
            
        message_text = (
            f"🔔 <b>Spaced Repetition Review!</b>\n\n"
            f"Translate the following word to Ukrainian:\n"
            f"👉 <b>{word_entry.word.upper()}</b>"
        )
        try:
            await bot.send_message(chat_id=user_id, text=message_text, parse_mode="HTML")
            await state.set_state(QuizStates.waiting_for_word_translation)
            await state.update_data(word_id=word_entry.id)
            task["status"] = "sent"
            last_sent_time = datetime.datetime.now()
            print(f"Sent word review task: {word_entry.word}")
            return True
        except Exception as e:
            print(f"Failed to send word review task ({word_entry.word}): {e}")
            await state.clear()
            return False
            
    elif task["task_type"] == "tense":
        tense_name = task["item_id"]
        settings = await database.get_settings()
        fill_in_blank_percentage = settings.fill_in_blank_percentage
        
        task_type = "fill_in_the_blank" if random.randint(1, 100) <= fill_in_blank_percentage else "guess_the_tense"
        
        try:
            task_details = await ai_logic.generate_tense_task(tense_name, task_type)
        except Exception as e:
            print(f"Error generating tense task ({tense_name}): {e}")
            return False
        
        if task_details["task_type"] == "fill_in_the_blank":
            message_text = (
                f"📝 <b>Grammar Practice: Fill in the blank!</b>\n\n"
                f"Sentence:\n👉 {task_details['sentence']}\n\n"
                f"(Type the correct form of the verb. If the form is identical to the base verb in brackets, just type that verb)"
            )
        else:  # guess_the_tense
            message_text = (
                f"🔍 <b>Grammar Practice: Guess the Tense!</b>\n\n"
                f"Analyze this sentence:\n"
                f"👉 \"{task_details['sentence']}\"\n\n"
                f"(Type the name of the tense, e.g., 'Present Simple' or 'Past Continuous')"
            )
            
        try:
            await bot.send_message(chat_id=user_id, text=message_text, parse_mode="HTML")
            await state.set_state(QuizStates.waiting_for_tense_answer)
            await state.update_data(
                tense_name=tense_name,
                task_type=task_details["task_type"],
                sentence=task_details["sentence"],
                correct_answer=task_details["correct_answer"]
            )
            task["status"] = "sent"
            last_sent_time = datetime.datetime.now()
            print(f"Sent tense practice task ({tense_name}): {task_details['sentence']}")
            return True
        except Exception as e:
            print(f"Failed to send tense task ({tense_name}): {e}")
            await state.clear()
            return False

    return False


async def queue_worker(bot: Bot, dp):
    """Background worker continuously processing tasks from task_queue."""
    print("Queue worker started...")
    user_id = config.ADMIN_ID
    
    while True:
        task_data = await task_queue.get()
        try:
            state = dp.fsm.resolve_context(bot=bot, chat_id=user_id, user_id=user_id)
            
            # If user is busy with FSM state, quietly wait 30 seconds WITHOUT logging anything to avoid log spam
            while await state.get_state() is not None:
                await asyncio.sleep(30)
                
            # Once state is None, process and send the task to the user
            await _execute_send_task(bot, state, user_id, task_data)
        except Exception as e:
            print(f"Error in queue_worker processing task: {e}")
        finally:
            task_queue.task_done()


async def scheduler_loop(bot: Bot, dp):
    """Background loop checking the schedule and pushing due tasks to task_queue."""
    global daily_tasks, last_schedule_date, last_reset_date
    
    print("Scheduler loop started...")
    
    # Start the queue_worker background task
    asyncio.create_task(queue_worker(bot, dp))
    
    while True:
        try:
            now = datetime.datetime.now(ZoneInfo("Europe/Kyiv"))
            current_date = now.date()
            
            # Daily task queue reset trigger at 03:00 AM
            if now.time() >= datetime.time(3, 0) and last_reset_date != current_date:
                await clear_task_queue()
                last_reset_date = current_date
                
            # 1. Daily schedule generation trigger at 08:55 AM
            if now.time() >= datetime.time(8, 55) and last_schedule_date != current_date:
                await generate_daily_schedule()
                last_schedule_date = current_date
                
            # 2. Check for newly due tasks and push them to task_queue
            for task in daily_tasks:
                if task["status"] == "pending" and task["scheduled_time"] <= now:
                    task["status"] = "queued"
                    task_queue.put_nowait(task)
                    print(f"Task queued: {task['task_type']} ({task['item_id']})")
                        
        except Exception as e:
            print(f"Error in scheduler_loop: {e}")
            
        # Sleep for 5 seconds between checks to respond quickly
        await asyncio.sleep(5)
