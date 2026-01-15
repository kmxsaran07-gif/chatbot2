import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Bot Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', '8518539584:AAGmEzfHMzZZgsUIY6gk1VQZ-SOP2FFdfe4')
OWNER_ID = int(os.getenv('OWNER_ID', '8327651421'))

# Admin IDs (comma-separated)
admin_ids_str = os.getenv('ADMIN_IDS', '')
if admin_ids_str:
    ADMIN_IDS = list(map(int, filter(None, admin_ids_str.split(','))))
else:
    ADMIN_IDS = []
ADMIN_IDS.append(OWNER_ID)  # Owner is always admin

# Messages
WELCOME_MESSAGE = """
🎉 Welcome <b>{first_name}</b>! 🎉

🤖 I'm <b>{bot_name}</b> - Your Advanced Telegram Bot

📌 <b>Your Info:</b>
├ Username: {username}
├ ID: <code>{user_id}</code>
└ Type: {is_bot}

🌟 <b>Features:</b>
• Sticker Collection
• User Management
• Media Support
• Advanced Admin Controls
• And much more!

Type /help to see all commands!
"""

BAN_MESSAGE = """
🚫 <b>You have been banned!</b>

❌ <b>Reason:</b> {reason}
👮 <b>Admin ID:</b> <code>{admin_id}</code>

If you think this is a mistake, contact: {appeal_contact}
"""

UNBAN_MESSAGE = """
✅ <b>You have been unbanned!</b>

You can now use the bot again.

👮 <b>Admin ID:</b> <code>{admin_id}</code>
"""

# Database Configuration
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot_database.db')

# Timezone
TIMEZONE = 'Asia/Kolkata'

# Webhook settings (for production)
WEBHOOK_URL = os.getenv('WEBHOOK_URL', '')
PORT = int(os.getenv('PORT', 8443))

# Logging level
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Backup settings
BACKUP_DIR = 'backups'
MAX_BACKUPS = 10

# Broadcast settings
MAX_BROADCAST_CHUNK = 30  # Users per second
BROADCAST_DELAY = 1  # Seconds between chunks

# Debug mode
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
