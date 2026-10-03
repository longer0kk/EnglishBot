import asyncio
import logging
import socket
from aiogram import Bot
from aiogram.client.session.middlewares.base import BaseRequestMiddleware
from aiogram.exceptions import TelegramNetworkError, TelegramServerError, TelegramRetryAfter
from aiohttp import ClientError

logger = logging.getLogger(__name__)


class NetworkRetryMiddleware(BaseRequestMiddleware):
    """
    Simple request middleware for aiogram Bot session.
    Catches temporary network, DNS, and server errors, retrying the request 
    until connectivity is restored so that update handlers resume seamlessly.
    """
    def __init__(self, retry_delay: float = 3.0, max_retries: int = 100):
        self.retry_delay = retry_delay
        self.max_retries = max_retries

    async def __call__(self, make_request, bot: Bot, method):
        attempt = 0
        current_delay = self.retry_delay
        while True:
            try:
                return await make_request(bot, method)
            except TelegramRetryAfter as e:
                logger.warning(f"⏳ Telegram rate limit reached. Waiting {e.retry_after}s before retrying...")
                await asyncio.sleep(e.retry_after)
            except (TelegramNetworkError, TelegramServerError, ClientError, TimeoutError, socket.gaierror, OSError) as e:
                attempt += 1
                if self.max_retries and attempt > self.max_retries:
                    logger.error(f"❌ Max retries ({self.max_retries}) exceeded for {type(method).__name__}: {e}")
                    raise

                print(f"⚠️ Network error ({e.__class__.__name__}: {e}). Connection lost? Retrying in {current_delay:.1f}s (attempt {attempt})...")
                await asyncio.sleep(current_delay)
                # Slightly increase delay up to max 15 seconds
                current_delay = min(current_delay * 1.5, 15.0)
