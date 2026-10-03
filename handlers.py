import datetime
import random
import json
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

import config
import database
import ai_logic
from config import QuizStates, SettingsStates

# Initialize the main router
router = Router()

# Security: Restrict all message handlers in this router to the ADMIN_ID
router.message.filter(F.from_user.id == config.ADMIN_ID)


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Sends the welcome message and instructions."""
    await message.answer(
        "👋 <b>Welcome to your Personal English Learning Bot!</b>\n\n"
        "This bot helps you master English vocabulary and grammar through two systems:\n\n"
        "1️⃣ <b>Spaced Repetition System</b>: Send me any English word. I will use AI to fetch its translation and context, then schedule daily reviews.\n"
        "2️⃣ <b>Grammar Trainer</b>: Bot will send daily quizzes for 12 English tenses, with AI-powered feedback if you make mistakes.\n\n"
        "📋 <b>Available Commands</b>:\n"
        "• /help - Show instruction details\n"
        "• /stats - Check your learning progress\n"
        "• /practiceword - Review a due word immediately\n"
        "• /practicetense - Practice a tense task immediately\n"
        "• /trigger - Manually generate today's learning schedule",
        parse_mode="HTML"
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Sends detailed instruction description."""
    await message.answer(
        "📖 <b>How to use this Bot</b>:\n\n"
        "• <b>Adding Words</b>: Just type any English word (e.g., meticulous) and send it. The bot will automatically translate it and save it.\n"
        "• <b>Answering Tasks</b>: When the bot sends you a quiz, simply reply by typing the answer. No buttons or suggestions are used to promote active recall.\n"
        "• <b>Scheduler</b>: The bot compiles your tasks at 08:55 AM daily and spaces them across active hours. If you are busy, tasks wait in a queue and are dispatched 7 seconds after you become free.\n\n"
        "📋 <b>Available Commands</b>:\n"
        "• /help - Show instruction details\n"
        "• /stats - Check your learning progress\n"
        "• /practiceword - Review a due word immediately\n"
        "• /practicetense - Practice a tense task immediately\n"
        "• /trigger - Manually generate today's learning schedule",
        parse_mode="HTML"
    )


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Shows statistics of learned vocabulary."""
    stats = await database.get_db_stats()
    
    stages_text = ""
    for stage in sorted(stats["stages"].keys()):
        count = stats["stages"][stage]
        interval = config.SRS_INTERVALS.get(stage, 120)
        stages_text += f"• Stage {stage} ({interval} days): <b>{count}</b> words\n"
        
    if not stages_text:
        stages_text = "No words saved yet."
        
    await message.answer(
        f"📊 <b>Your Learning Stats</b>:\n\n"
        f"• Total words in database: <b>{stats['total_words']}</b>\n"
        f"• Words due for review today: <b>{stats['due_words']}</b>\n\n"
        f"📋 <b>SRS Stages Breakdown</b>:\n{stages_text}",
        parse_mode="HTML"
    )


@router.message(Command("trigger"))
async def cmd_trigger(message: Message):
    """Manually triggers daily schedule generation."""
    import scheduler
    await scheduler.generate_daily_schedule()
    
    # Calculate scheduled count
    pending_count = len([t for t in scheduler.daily_tasks if t["status"] == "pending"])
    await message.answer(
        f"🔄 <b>Schedule Generated!</b>\n\n"
        f"Created <b>{pending_count}</b> tasks in the daily dispatcher. They will fire throughout active hours.",
        parse_mode="HTML"
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancels any current active state/task."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("ℹ️ No active task or action to cancel.")
    else:
        await state.clear()
        await message.answer("❌ Current active task has been cancelled.")


@router.message(Command("practiceword"))
async def cmd_practice_word(message: Message, state: FSMContext):
    """Forces an immediate manual word review if any is due."""
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer("⚠️ You are currently in an active task. Please answer it first or send /cancel!")
        return
        
    due_words = await database.get_due_words(1)
    if not due_words:
        await message.answer("✅ No words are currently due for review! Add some new words or wait for the next scheduled review.")
        return
        
    word_entry = due_words[0]
    
    try:
        await message.answer(
            f"🔔 <b>Spaced Repetition Review!</b>\n\n"
            f"Translate this word to Ukrainian:\n"
            f"👉 <b>{word_entry.word.upper()}</b>",
            parse_mode="HTML"
        )
        await state.set_state(QuizStates.waiting_for_word_translation)
        await state.update_data(word_id=word_entry.id)
    except Exception as e:
        print(f"Error sending manual word review: {e}")
        await state.clear()


@router.message(Command("practicetense"))
async def cmd_practice_tense(message: Message, state: FSMContext):
    """Forces an immediate random tense practice task."""
    current_state = await state.get_state()
    if current_state is not None:
        await message.answer("⚠️ You are currently in an active task. Please answer it first or send /cancel!")
        return
        
    # Load settings from database
    settings = await database.get_settings()
    tense_weights_dict = json.loads(settings.tense_weights)
    fill_in_blank_percentage = settings.fill_in_blank_percentage
    
    # Select random tense
    tenses_pool = list(tense_weights_dict.keys())
    tense_weights = list(tense_weights_dict.values())
    tense_name = random.choices(tenses_pool, weights=tense_weights, k=1)[0]
    
    # Python decides task_type beforehand based on split percentage settings
    task_type = "fill_in_the_blank" if random.randint(1, 100) <= fill_in_blank_percentage else "guess_the_tense"
    
    # Generate task details
    try:
        task_details = await ai_logic.generate_tense_task(tense_name, task_type)
    except Exception as e:
        await message.answer(f"⚠️ Error generating grammar task: {e}")
        return
    
    if task_details["task_type"] == "fill_in_the_blank":
        message_text = (
            f"📝 <b>Grammar Practice: Fill in the blank!</b>\n\n"
            f"Sentence:\n👉 {task_details['sentence']}\n\n"
            f"(Type the correct form of the verb. If the form is identical to the base verb, just type that)"
        )
    else:
        message_text = (
            f"🔍 <b>Grammar Practice: Guess the Tense!</b>\n\n"
            f"Analyze this sentence:\n"
            f"👉 \"{task_details['sentence']}\"\n\n"
            f"(Type the name of the tense)"
        )
        
    try:
        await message.answer(message_text, parse_mode="HTML")
        await state.set_state(QuizStates.waiting_for_tense_answer)
        await state.update_data(
            tense_name=tense_name,
            task_type=task_details["task_type"],
            sentence=task_details["sentence"],
            correct_answer=task_details["correct_answer"]
        )
    except Exception as e:
        print(f"Error sending manual tense practice: {e}")
        await state.clear()


# FSM Handler: Word Review
@router.message(QuizStates.waiting_for_word_translation)
async def process_word_review(message: Message, state: FSMContext):
    """Processes user's input for word reviews."""
    if not message.text:
        await message.answer("Please reply with a text translation.")
        return
        
    data = await state.get_data()
    word_id = data.get("word_id")
    if not word_id:
        await state.clear()
        await message.answer("Session expired. Please try again.")
        return
        
    word_entry = await database.get_word_by_id(word_id)
    if not word_entry:
        await message.answer("Error: Word not found in database.")
        await state.clear()
        return
        
    user_answer = message.text.strip().lower()
    
    try:
        # Clean and split the correct translation to handle multiple synonyms (e.g. split by commas, slashes, semicolons)
        temp_translation = word_entry.translation.replace(';', ',').replace('/', ',')
        parts = [p.strip().lower() for p in temp_translation.split(',')]
        
        # Check if user answer matches the full translation or any synonym part
        is_correct = user_answer in parts or user_answer == word_entry.translation.strip().lower()
        
        # If fast-path check failed, verify with AI (Gemini)
        if not is_correct:
            is_correct = await ai_logic.verify_translation(word_entry.word, word_entry.translation, user_answer)
        
        # Update word schedule in the database
        updated_word = await database.update_word_review(word_id, correct=is_correct)
        
        if is_correct:
            interval_days = config.SRS_INTERVALS.get(updated_word.interval_stage, 120) if updated_word else 1
            stage_num = updated_word.interval_stage if updated_word else 1
            await message.answer(
                f"✅ <b>Correct!</b>\n\n"
                f"Word: <b>{word_entry.word}</b>\n"
                f"Translation: {word_entry.translation}\n"
                f"Context: {word_entry.description}\n\n"
                f"📈 SRS Stage advanced to <b>{stage_num}</b>.\n"
                f"📅 Next review scheduled in <b>{interval_days}</b> days.",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"❌ <b>Incorrect.</b>\n\n"
                f"Word: <b>{word_entry.word}</b>\n"
                f"Correct Translation: <b>{word_entry.translation}</b>\n"
                f"Context: {word_entry.description}\n\n"
                f"📉 SRS Stage reset to <b>0</b>.\n"
                f"📅 Next review scheduled for tomorrow.",
                parse_mode="HTML"
            )
    finally:
        await state.clear()


# FSM Handler: Tense Quiz
@router.message(QuizStates.waiting_for_tense_answer)
async def process_tense_answer(message: Message, state: FSMContext):
    """Processes user's input for grammar quizzes."""
    if not message.text:
        await message.answer("Please reply with a text answer.")
        return
        
    data = await state.get_data()
    tense_name = data.get("tense_name")
    sentence = data.get("sentence")
    correct_answer = data.get("correct_answer")
    
    if not tense_name or not sentence or not correct_answer:
        await state.clear()
        await message.answer("Session expired. Please try again.")
        return
        
    user_answer = message.text.strip()
    
    try:
        # Simple case-insensitive comparison
        is_correct = user_answer.lower() == correct_answer.lower()
        
        # Fetch static rule information
        rule = await database.get_tense_rule(tense_name)
        rule_info = ""
        if rule:
            rule_info = (
                f"\n\n📖 <b>Grammar Formula for {tense_name}</b>:\n"
                f"• Structure: {rule.structure_formula}\n"
                f"• Rule: {rule.description}"
            )
            
        if is_correct:
            await message.answer(
                f"✅ <b>Correct! Excellent work!</b>{rule_info}",
                parse_mode="HTML"
            )
        else:
            # User made a mistake. Call AI to generate description explanation
            explanation_msg = await message.answer(
                "❌ <b>Incorrect. Let's ask AI for an explanation...</b>",
                parse_mode="HTML"
            )
            explanation = await ai_logic.explain_tense_mistake(
                tense_name=tense_name,
                sentence=sentence,
                correct_answer=correct_answer,
                user_answer=user_answer
            )
            
            await explanation_msg.edit_text(
                f"❌ <b>Incorrect.</b>\n\n"
                f"💡 <b>AI Explanation</b>:\n{explanation}{rule_info}",
                parse_mode="HTML"
            )
    finally:
        await state.clear()

def get_settings_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Words Per Day", callback_data="set_words_per_day")
    builder.button(text="Tenses Per Day", callback_data="set_tenses_per_day")
    builder.button(text="Task Type Split %", callback_data="set_split")
    builder.button(text="Tense Weights", callback_data="set_weights")
    builder.button(text="Min Gap (mins)", callback_data="set_min_gap")
    builder.button(text="Delete Word", callback_data="delete_word")
    builder.button(text="Close Settings", callback_data="close_settings")
    builder.adjust(2)
    return builder.as_markup()


@router.message(Command("settings"))
async def cmd_settings(message: Message):
    """Displays the current settings and the Inline menu to edit them."""
    settings = await database.get_settings()
    weights = json.loads(settings.tense_weights)
    
    weights_text = "\n".join([f"• {k}: {v * 100:.1f}%".replace(".0%", "%") for k, v in weights.items()])
    
    text = (
        f"⚙️ <b>Bot Settings</b>\n\n"
        f"• <b>Words Per Day:</b> {settings.words_per_day}\n"
        f"• <b>Tenses Per Day:</b> {settings.tenses_per_day}\n"
        f"• <b>Task Type Split:</b> {settings.fill_in_blank_percentage}% fill-in, "
        f"{100 - settings.fill_in_blank_percentage}% guess-the-tense\n"
        f"• <b>Min Gap:</b> {settings.min_gap_minutes} mins\n\n"
        f"📊 <b>Tense Weights:</b>\n{weights_text}\n\n"
        f"Select a setting to modify:"
    )
    await message.answer(text, reply_markup=get_settings_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "set_words_per_day")
async def process_set_words_per_day(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter the number of words per day:")
    await state.set_state(SettingsStates.waiting_for_words_per_day)
    await callback.answer()


@router.callback_query(F.data == "set_tenses_per_day")
async def process_set_tenses_per_day(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter the number of tenses per day:")
    await state.set_state(SettingsStates.waiting_for_tenses_per_day)
    await callback.answer()


@router.callback_query(F.data == "set_split")
async def process_set_split(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter the fill-in-the-blank percentage:")
    await state.set_state(SettingsStates.waiting_for_split)
    await callback.answer()


@router.callback_query(F.data == "set_weights")
async def process_set_weights(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="Change All", callback_data="weights_change_all")
    builder.button(text="Change Specific Tense", callback_data="weights_change_specific")
    builder.adjust(1)
    await callback.message.edit_text("How would you like to update the tense weights?", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data == "weights_change_specific")
async def process_weights_change_specific(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    for tense in config.TENSE_WEIGHTS.keys():
        builder.button(text=tense, callback_data=f"set_specific_weight:{tense}")
    builder.adjust(2)
    await callback.message.edit_text("Select the tense to update:", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(F.data.startswith("set_specific_weight:"))
async def process_set_specific_weight(callback: CallbackQuery, state: FSMContext):
    tense_name = callback.data.split(":", 1)[1]
    await callback.message.answer(f"Enter the new percentage for {tense_name}:")
    await state.set_state(SettingsStates.waiting_for_specific_weight)
    await state.update_data(tense_name=tense_name)
    await callback.answer()


@router.callback_query(F.data == "weights_change_all")
async def process_weights_change_all(callback: CallbackQuery, state: FSMContext):
    tenses = list(config.TENSE_WEIGHTS.keys())
    await state.update_data(tenses=tenses, current_index=0, new_weights={})
    await state.set_state(SettingsStates.waiting_for_all_weights_step)
    first_tense = tenses[0]
    await callback.message.answer(f"Enter the percentage for {first_tense}:")
    await callback.answer()


@router.callback_query(F.data == "set_min_gap")
async def process_set_min_gap(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Enter the minimum gap in minutes:")
    await state.set_state(SettingsStates.waiting_for_min_gap)
    await callback.answer()


@router.callback_query(F.data == "close_settings")
async def process_close_settings(callback: CallbackQuery):
    await callback.message.delete()
    await callback.answer("Settings menu closed.")


@router.message(SettingsStates.waiting_for_words_per_day)
async def process_words_per_day_input(message: Message, state: FSMContext):
    val_text = message.text.strip()
    try:
        val = int(val_text)
        if val <= 0:
            raise ValueError()
        await database.update_settings(words_per_day=val)
        await message.answer(f"✅ Words per day updated to <b>{val}</b>.", parse_mode="HTML")
        await state.clear()
        await cmd_settings(message)
    except ValueError:
        await message.answer("⚠️ Invalid value. Please enter a valid number.")


@router.message(SettingsStates.waiting_for_tenses_per_day)
async def process_tenses_per_day_input(message: Message, state: FSMContext):
    val_text = message.text.strip()
    try:
        val = int(val_text)
        if val <= 0:
            raise ValueError()
        await database.update_settings(tenses_per_day=val)
        await message.answer(f"✅ Tenses per day updated to <b>{val}</b>.", parse_mode="HTML")
        await state.clear()
        await cmd_settings(message)
    except ValueError:
        await message.answer("⚠️ Invalid value. Please enter a valid number.")


@router.message(SettingsStates.waiting_for_split)
async def process_split_input(message: Message, state: FSMContext):
    val_text = message.text.strip()
    try:
        val = int(val_text)
        if val < 0 or val > 100:
            raise ValueError()
        await database.update_settings(fill_in_blank_percentage=val)
        await message.answer(f"✅ Fill-in-the-blank percentage updated to <b>{val}%</b>.", parse_mode="HTML")
        await state.clear()
        await cmd_settings(message)
    except ValueError:
        await message.answer("⚠️ Invalid value. Please enter a valid percentage.")


@router.message(SettingsStates.waiting_for_specific_weight)
async def process_specific_weight_input(message: Message, state: FSMContext):
    val_text = message.text.strip()
    data = await state.get_data()
    tense_name = data.get("tense_name")
    
    try:
        val = int(val_text)
        if val < 0:
            raise ValueError()
            
        settings = await database.get_settings()
        current_weights = json.loads(settings.tense_weights)
        current_weights[tense_name] = val / 100.0
        
        await database.update_settings(tense_weights=current_weights)
        await message.answer(f"✅ Weight for <b>{tense_name}</b> updated to <b>{val}%</b>.", parse_mode="HTML")
        await state.clear()
        await cmd_settings(message)
    except ValueError:
        await message.answer("⚠️ Invalid value.")


@router.message(SettingsStates.waiting_for_all_weights_step)
async def process_all_weights_step_input(message: Message, state: FSMContext):
    val_text = message.text.strip()
    data = await state.get_data()
    tenses = data["tenses"]
    current_index = data["current_index"]
    new_weights = data["new_weights"]
    current_tense = tenses[current_index]
    
    try:
        val = int(val_text)
        if val < 0:
            raise ValueError()
            
        new_weights[current_tense] = val / 100.0
        current_index += 1
        
        if current_index < len(tenses):
            next_tense = tenses[current_index]
            await state.update_data(current_index=current_index, new_weights=new_weights)
            await message.answer(f"Enter the percentage for {next_tense}:")
        else:
            await database.update_settings(tense_weights=new_weights)
            await message.answer("✅ All tense weights updated successfully.")
            await state.clear()
            await cmd_settings(message)
    except ValueError:
        await message.answer("⚠️ Invalid value.")


@router.message(SettingsStates.waiting_for_min_gap)
async def process_min_gap_input(message: Message, state: FSMContext):
    val_text = message.text.strip()
    try:
        val = int(val_text)
        if val <= 0:
            raise ValueError()
        await database.update_settings(min_gap_minutes=val)
        await message.answer(f"✅ Min gap updated to <b>{val}</b> minutes.", parse_mode="HTML")
        await state.clear()
        await cmd_settings(message)
    except ValueError:
        await message.answer("⚠️ Invalid value. Please enter a valid number.")


@router.callback_query(F.data == "delete_word")
async def process_delete_word_callback(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Type the exact word you want to delete:")
    await state.set_state(SettingsStates.waiting_for_word_delete)
    await callback.answer()


@router.message(SettingsStates.waiting_for_word_delete)
async def process_word_delete_input(message: Message, state: FSMContext):
    word_text = message.text.strip()
    success = await database.delete_word(word_text)
    if success:
        await message.answer(f"✅ Word <b>{word_text}</b> deleted successfully.", parse_mode="HTML")
    else:
        await message.answer(f"❌ Word <b>{word_text}</b> not found in database.", parse_mode="HTML")
    await state.clear()
    await cmd_settings(message)


# Default Message Handler: Add new word when idle (acting as catch-all at bottom)
@router.message(F.text)
async def process_new_word(message: Message, state: FSMContext):
    """Treats incoming text as a request to add a new vocabulary word when user is idle."""
    word_text = message.text.strip()
    
    # Basic protection against command inputs that didn't match previous handlers
    if word_text.startswith("/"):
        await message.answer("⚠️ Unknown command. Type /help to see available commands.")
        return
        
    # Check if the word is already in the database
    existing_word = await database.get_word_by_word(word_text)
    if existing_word:
        await message.answer(
            f"⚠️ <b>'{word_text}' is already in your database!</b>\n\n"
            f"• Translation: {existing_word.translation}\n"
            f"• Context: {existing_word.description}\n"
            f"• Current SRS Stage: {existing_word.interval_stage}\n"
            f"• Next review: {existing_word.next_review_datetime.strftime('%Y-%m-%d %H:%M')}",
            parse_mode="HTML"
        )
        return
        
    processing_msg = await message.answer(
        f"🔍 <b>AI is translating and creating context for '{word_text}'...</b>",
        parse_mode="HTML"
    )
    
    # Query AI for translation and context description
    details = await ai_logic.generate_word_details(word_text)
    
    # Save the word to the database
    await database.add_word(
        word=word_text,
        translation=details["translation"],
        description=details["description"]
    )
    
    await processing_msg.edit_text(
        f"🆕 <b>Word Added successfully!</b>\n\n"
        f"• Word: <b>{word_text.upper()}</b>\n"
        f"• Translation: <b>{details['translation']}</b>\n"
        f"• Context: {details['description']}\n\n"
        f"📅 Scheduled for your first review tomorrow.",
        parse_mode="HTML"
    )
