import os
import logging
import sys
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import sqlite3
from datetime import datetime

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Get bot token from environment
BOT_TOKEN = os.getenv('BOT_TOKEN')
OWNER_ID = int(os.getenv('OWNER_ID', '1234567890'))

if not BOT_TOKEN:
    logger.error("❌ BOT_TOKEN environment variable is not set!")
    sys.exit(1)

# Simple Database
class SimpleDB:
    def __init__(self):
        self.conn = sqlite3.connect('bot.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.create_tables()
    
    def create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TEXT,
                sticker_count INTEGER DEFAULT 0
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stickers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_id TEXT,
                emoji TEXT,
                added_date TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS banned_users (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                banned_date TEXT
            )
        ''')
        self.conn.commit()
        logger.info("✅ Database ready")
    
    def add_user(self, user_id, username, first_name, last_name):
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.cursor.execute('''
                INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, join_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, current_time))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        row = self.cursor.fetchone()
        if row:
            return {
                'user_id': row[0],
                'username': row[1],
                'first_name': row[2],
                'last_name': row[3],
                'join_date': row[4],
                'sticker_count': row[5]
            }
        return None
    
    def add_sticker(self, user_id, file_id, emoji):
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            # Add sticker
            self.cursor.execute('INSERT INTO stickers (user_id, file_id, emoji, added_date) VALUES (?, ?, ?, ?)',
                              (user_id, file_id, emoji, current_time))
            # Update count
            self.cursor.execute('UPDATE users SET sticker_count = sticker_count + 1 WHERE user_id = ?', (user_id,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding sticker: {e}")
            return False
    
    def get_user_stickers(self, user_id):
        self.cursor.execute('SELECT file_id, emoji FROM stickers WHERE user_id = ? ORDER BY id DESC LIMIT 5', (user_id,))
        return self.cursor.fetchall()
    
    def get_total_users(self):
        self.cursor.execute('SELECT COUNT(*) FROM users')
        return self.cursor.fetchone()[0]
    
    def ban_user(self, user_id, reason):
        try:
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.cursor.execute('INSERT OR REPLACE INTO banned_users (user_id, reason, banned_date) VALUES (?, ?, ?)',
                              (user_id, reason, current_time))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error banning user: {e}")
            return False
    
    def unban_user(self, user_id):
        self.cursor.execute('DELETE FROM banned_users WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return True
    
    def is_banned(self, user_id):
        self.cursor.execute('SELECT * FROM banned_users WHERE user_id = ?', (user_id,))
        return self.cursor.fetchone() is not None
    
    def get_banned_users(self):
        self.cursor.execute('SELECT user_id, reason, banned_date FROM banned_users')
        return self.cursor.fetchall()

# Initialize database
db = SimpleDB()

# Check if user is admin
def is_admin(user_id):
    return user_id == OWNER_ID

# ========== COMMAND HANDLERS ==========

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_msg = f"""
🎉 *Welcome {user.first_name}!* 🎉

🤖 *I'm {context.bot.first_name} - Your Telegram Bot*

📌 *Your Info:*
• Username: @{user.username if user.username else 'No username'}
• ID: `{user.id}`
• Type: {'🤖 Bot' if user.is_bot else '👤 Human'}

✨ *Features:*
• Save stickers
• View profiles
• Admin controls
• User management

📖 *Commands:* /help
    """
    
    keyboard = [
        [InlineKeyboardButton("📊 My Stats", callback_data="stats"),
         InlineKeyboardButton("👤 My Profile", callback_data="profile")],
        [InlineKeyboardButton("🛠 Admin Panel", callback_data="admin"),
         InlineKeyboardButton("📖 Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_msg, reply_markup=reply_markup, parse_mode=ParseMode.MARKDOWN)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
*🤖 BOT COMMANDS*

👤 *User Commands:*
/start - Start the bot
/profile - View your profile
/stats - Your statistics
/id - Get your ID
/stickers - Your saved stickers
/ping - Check bot status

👮 *Admin Commands:*
/users - Total users count
/ban [id] [reason] - Ban user
/unban [id] - Unban user
/banned - List banned users

🎨 *Sticker Features:*
• Send any sticker to save it
• Animated stickers supported
• View saved stickers

📊 *Other Features:*
• User profiles
• Welcome messages
• Admin controls
• Database backup
    """
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if user_data:
        profile_text = f"""
*👤 PROFILE INFORMATION*

*Name:* {user_data['first_name']} {user_data.get('last_name', '')}
*Username:* @{user_data['username'] if user_data['username'] else 'Not set'}
*ID:* `{user_data['user_id']}`
*Join Date:* {user_data['join_date']}
*Stickers Saved:* {user_data['sticker_count']}
*Status:* {'🚫 Banned' if db.is_banned(user.id) else '✅ Active'}
        """
    else:
        profile_text = f"""
*👤 PROFILE INFORMATION*

*Name:* {user.full_name}
*ID:* `{user.id}`
*Username:* @{user.username if user.username else 'Not set'}
*Status:* {'🚫 Banned' if db.is_banned(user.id) else '✅ Active'}
        """
    
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    total_users = db.get_total_users()
    
    if user_data:
        stats_text = f"""
*📊 YOUR STATISTICS*

*User ID:* `{user.id}`
*Join Date:* {user_data['join_date']}
*Stickers Saved:* {user_data['sticker_count']}
*Total Bot Users:* {total_users}
*Your Status:* {'🚫 Banned' if db.is_banned(user.id) else '✅ Active'}
        """
    else:
        stats_text = f"""
*📊 BOT STATISTICS*

*Your ID:* `{user.id}`
*Total Users:* {total_users}
*Your Status:* {'🚫 Banned' if db.is_banned(user.id) else '✅ Active'}
        """
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"*Your ID:* `{user.id}`", parse_mode=ParseMode.MARKDOWN)

async def ping_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 *Pong! Bot is working perfectly!*", parse_mode=ParseMode.MARKDOWN)

async def show_stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stickers = db.get_user_stickers(user.id)
    
    if stickers:
        sticker_text = f"*📁 Your Stickers ({len(stickers)})*\n\n"
        for i, (file_id, emoji) in enumerate(stickers, 1):
            sticker_text += f"{i}. {emoji}\n"
        
        await update.message.reply_text(sticker_text, parse_mode=ParseMode.MARKDOWN)
        
        # Send the most recent sticker
        if stickers:
            file_id, emoji = stickers[0]
            await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=file_id)
    else:
        await update.message.reply_text("*📭 No stickers saved yet!*\nSend me a sticker and I'll save it for you! 😊", parse_mode=ParseMode.MARKDOWN)

async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sticker = update.message.sticker
    
    # Check if user is banned
    if db.is_banned(user.id):
        await update.message.reply_text("🚫 *You are banned from using this bot!*", parse_mode=ParseMode.MARKDOWN)
        return
    
    # Save sticker
    db.add_sticker(user.id, sticker.file_id, sticker.emoji)
    
    # Send response
    if sticker.is_animated:
        await update.message.reply_text("✨ *Nice animated sticker!* Saved to your collection.", parse_mode=ParseMode.MARKDOWN)
    elif sticker.is_video:
        await update.message.reply_text("🎥 *Cool video sticker!* Saved to your collection.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("👍 *Nice sticker!* Saved to your collection.", parse_mode=ParseMode.MARKDOWN)

# ========== ADMIN COMMANDS ==========

async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ *Permission denied!*", parse_mode=ParseMode.MARKDOWN)
        return
    
    total = db.get_total_users()
    await update.message.reply_text(f"*👥 Total Users:* {total}", parse_mode=ParseMode.MARKDOWN)

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ *Permission denied!*", parse_mode=ParseMode.MARKDOWN)
        return
    
    if not context.args:
        await update.message.reply_text("*Usage:* /ban <user_id> <reason>", parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        target_id = int(context.args[0])
        reason = ' '.join(context.args[1:]) or "No reason provided"
        
        db.ban_user(target_id, reason)
        await update.message.reply_text(f"✅ *User {target_id} banned!*\nReason: {reason}", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ *Invalid user ID!*", parse_mode=ParseMode.MARKDOWN)

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ *Permission denied!*", parse_mode=ParseMode.MARKDOWN)
        return
    
    if not context.args:
        await update.message.reply_text("*Usage:* /unban <user_id>", parse_mode=ParseMode.MARKDOWN)
        return
    
    try:
        target_id = int(context.args[0])
        db.unban_user(target_id)
        await update.message.reply_text(f"✅ *User {target_id} unbanned!*", parse_mode=ParseMode.MARKDOWN)
    except ValueError:
        await update.message.reply_text("❌ *Invalid user ID!*", parse_mode=ParseMode.MARKDOWN)

async def banned_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ *Permission denied!*", parse_mode=ParseMode.MARKDOWN)
        return
    
    banned_users = db.get_banned_users()
    
    if banned_users:
        banned_text = "*🚫 Banned Users*\n\n"
        for user_id, reason, banned_date in banned_users:
            banned_text += f"• ID: `{user_id}`\nReason: {reason}\nDate: {banned_date}\n\n"
        
        await update.message.reply_text(banned_text, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("*✅ No banned users!*", parse_mode=ParseMode.MARKDOWN)

# ========== BUTTON HANDLERS ==========

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if data == "stats":
        user_data = db.get_user(user.id)
        total_users = db.get_total_users()
        
        if user_data:
            stats_text = f"""
*📊 YOUR STATISTICS*

*User ID:* `{user.id}`
*Join Date:* {user_data['join_date']}
*Stickers Saved:* {user_data['sticker_count']}
*Total Bot Users:* {total_users}
*Status:* {'🚫 Banned' if db.is_banned(user.id) else '✅ Active'}
            """
        else:
            stats_text = f"""
*📊 STATISTICS*

*Your ID:* `{user.id}`
*Total Users:* {total_users}
*Status:* {'🚫 Banned' if db.is_banned(user.id) else '✅ Active'}
            """
        
        await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    elif data == "profile":
        user_data = db.get_user(user.id)
        
        if user_data:
            profile_text = f"""
*👤 YOUR PROFILE*

*Name:* {user_data['first_name']} {user_data.get('last_name', '')}
*Username:* @{user_data['username'] if user_data['username'] else 'Not set'}
*ID:* `{user_data['user_id']}`
*Join Date:* {user_data['join_date']}
*Stickers Saved:* {user_data['sticker_count']}
*Status:* {'🚫 Banned' if db.is_banned(user.id) else '✅ Active'}
            """
        else:
            profile_text = f"""
*👤 YOUR PROFILE*

*Name:* {user.full_name}
*ID:* `{user.id}`
*Username:* @{user.username if user.username else 'Not set'}
*Status:* {'🚫 Banned' if db.is_banned(user.id) else '✅ Active'}
            """
        
        await query.edit_message_text(profile_text, parse_mode=ParseMode.MARKDOWN)
    
    elif data == "admin":
        if is_admin(user.id):
            admin_text = """
*🛠 ADMIN PANEL*

*Commands:*
/users - Total users count
/ban - Ban a user
/unban - Unban a user
/banned - List banned users

*Quick Actions:*
• Check /users for statistics
• Use /banned to see banned users
            """
            await query.edit_message_text(admin_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("❌ *Admin access only!*", parse_mode=ParseMode.MARKDOWN)
    
    elif data == "help":
        help_text = """
*📖 HELP MENU*

*Commands:*
/start - Start bot
/profile - Your profile
/stats - Your statistics
/id - Get your ID
/stickers - Your saved stickers
/ping - Check bot status

*Admin:*
/users - Total users
/ban - Ban user
/unban - Unban user
/banned - Banned users list

*Features:*
• Save stickers
• User profiles
• Admin controls
            """
        await query.edit_message_text(help_text, parse_mode=ParseMode.MARKDOWN)

# ========== ERROR HANDLER ==========

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    try:
        await context.bot.send_message(
            chat_id=OWNER_ID,
            text=f"⚠️ *Bot Error:*\n\n`{context.error}`",
            parse_mode=ParseMode.MARKDOWN
        )
    except:
        pass

# ========== MAIN FUNCTION ==========

def main():
    """Start the bot"""
    logger.info("🤖 Starting Telegram Bot...")
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("id", get_id))
    app.add_handler(CommandHandler("ping", ping_command))
    app.add_handler(CommandHandler("stickers", show_stickers))
    app.add_handler(CommandHandler("users", total_users))
    app.add_handler(CommandHandler("ban", ban_user))
    app.add_handler(CommandHandler("unban", unban_user))
    app.add_handler(CommandHandler("banned", banned_list))
    
    # Add message handlers
    app.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    
    # Add callback handler
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Start polling
    logger.info("✅ Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()
