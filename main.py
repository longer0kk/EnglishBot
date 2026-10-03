import asyncio
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database
import handlers
import scheduler
from network_retry import NetworkRetryMiddleware

async def main():
    # Verify that the bot token is configured
    if config.ENGLISH_BOT_TOKEN == "ENGLISH_BOT_TOKEN":
        print("❌ ERROR: Please configure your ENGLISH_BOT_TOKEN in the root .env file!")
        sys.exit(1)
        
    print("🚀 Initializing English Learning Bot...")
    
    # 1. Initialize the SQLite database and seed the 12 English tense rules
    await database.init_db()
    print("✅ Database initialized successfully.")
    
    # 2. Instantiate the bot and memory-based dispatcher
    bot = Bot(token=config.ENGLISH_BOT_TOKEN)
    bot.session.middleware.register(NetworkRetryMiddleware())
    dp = Dispatcher(storage=MemoryStorage())
    
    # 3. Include our admin handlers router
    dp.include_router(handlers.router)
    print("✅ Message handlers and admin filters registered.")
    
    # 4. Start the scheduler background loop task
    asyncio.create_task(scheduler.scheduler_loop(bot, dp))
    print("✅ Background scheduler loop started.")
    
    # 5. Start polling
    print(f"🤖 Bot is now polling for ADMIN_ID: {config.ADMIN_ID}. Press Ctrl+C to exit.")
    
    try:
        await dp.start_polling(bot)
    finally:
        # Graceful shutdown of bot session on exit
        await bot.session.close()
        print("👋 Bot session closed. Goodbye!")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 Bot execution terminated by user.")
