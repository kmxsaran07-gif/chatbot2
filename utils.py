import asyncio
from typing import List, Dict, Tuple
from datetime import datetime
import pytz
from telegram import Bot
from telegram.constants import ParseMode
from config import ADMIN_IDS, TIMEZONE, MAX_BROADCAST_CHUNK, BROADCAST_DELAY
from database import get_all_users

async def is_admin(user_id: int) -> bool:
    """Check if user is admin"""
    return user_id in ADMIN_IDS

async def send_broadcast(bot: Bot, message: str, parse_mode: ParseMode = ParseMode.HTML) -> Tuple[int, int]:
    """Send broadcast message to all users"""
    users = get_all_users()
    success = 0
    failed = 0
    
    # Split users into chunks
    chunks = [users[i:i + MAX_BROADCAST_CHUNK] for i in range(0, len(users), MAX_BROADCAST_CHUNK)]
    
    for chunk in chunks:
        tasks = []
        for user in chunk:
            try:
                task = bot.send_message(
                    chat_id=user['user_id'],
                    text=message,
                    parse_mode=parse_mode
                )
                tasks.append(task)
            except:
                failed += 1
        
        # Send chunk
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Count results
        for result in results:
            if isinstance(result, Exception):
                failed += 1
            else:
                success += 1
        
        # Delay between chunks
        await asyncio.sleep(BROADCAST_DELAY)
    
    return success, failed

def format_user_info(user_data: Dict, detailed: bool = False) -> str:
    """Format user information for display"""
    if detailed:
        info = f"""
👤 <b>Detailed User Information</b>

<b>Basic Info:</b>
├ ID: <code>{user_data.get('user_id', 'N/A')}</code>
├ Username: @{user_data.get('username', 'N/A')}
├ Name: {user_data.get('first_name', 'N/A')} {user_data.get('last_name', '')}
├ Bot: {'✅ Yes' if user_data.get('is_bot') else '❌ No'}
├ Language: {user_data.get('language_code', 'N/A')}
└ Join Date: {user_data.get('join_date', 'N/A')}

<b>Status:</b>
├ Banned: {'✅ Yes' if user_data.get('is_banned') else '❌ No'}
├ Ban Reason: {user_data.get('ban_reason', 'N/A')}
├ Banned By: {user_data.get('banned_by', 'N/A')}
└ Ban Date: {user_data.get('ban_date', 'N/A')}

<b>Statistics:</b>
├ Saved Stickers: {len(user_data.get('stickers', []))}
└ Last Seen: {user_data.get('last_seen', 'N/A')}
        """
    else:
        info = f"""
👤 <b>User Profile</b>

<b>Name:</b> {user_data.get('first_name', 'N/A')} {user_data.get('last_name', '')}
<b>Username:</b> @{user_data.get('username', 'Not set')}
<b>ID:</b> <code>{user_data.get('user_id', 'N/A')}</code>
<b>Join Date:</b> {user_data.get('join_date', 'N/A')}
<b>Saved Stickers:</b> {len(user_data.get('stickers', []))}
        """
    
    return info

def parse_time(time_str: str) -> int:
    """Parse time string to seconds"""
    time_units = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800
    }
    
    try:
        unit = time_str[-1].lower()
        value = int(time_str[:-1])
        
        if unit in time_units:
            return value * time_units[unit]
        else:
            return int(time_str)
    except:
        return 0

def format_time(seconds: int) -> str:
    """Format seconds to human readable time"""
    if seconds < 60:
        return f"{seconds} seconds"
    elif seconds < 3600:
        return f"{seconds // 60} minutes"
    elif seconds < 86400:
        return f"{seconds // 3600} hours"
    else:
        return f"{seconds // 86400} days"

def get_current_time():
    """Get current time in configured timezone"""
    return datetime.now(pytz.timezone(TIMEZONE))

def create_backup_dir():
    """Create backup directory if not exists"""
    import os
    os.makedirs('backups', exist_ok=True)
