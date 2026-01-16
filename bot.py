import os
import logging
import sys
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ParseMode
import pytz

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

# Bot configuration
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN_HERE')
OWNER_ID = int(os.getenv('OWNER_ID', 'YOUR_TELEGRAM_ID_HERE'))

# Database (simple file-based for now)
import json
import sqlite3

class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot_data.db', check_same_thread=False)
        self.cursor = self.conn.cursor()
        self.init_db()
    
    def init_db(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                join_date TEXT,
                last_seen TEXT,
                sticker_count INTEGER DEFAULT 0,
                is_banned BOOLEAN DEFAULT FALSE,
                ban_reason TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stickers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                file_id TEXT,
                emoji TEXT,
                is_animated BOOLEAN,
                added_date TEXT
            )
        ''')
        
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                timestamp TEXT
            )
        ''')
        
        self.conn.commit()
        logger.info("Database initialized")
    
    def add_user(self, user_id, username, first_name, last_name):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            self.cursor.execute('''
                INSERT OR REPLACE INTO users (user_id, username, first_name, last_name, join_date, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (user_id, username, first_name, last_name, current_time, current_time))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding user: {e}")
            return False
    
    def get_user(self, user_id):
        self.cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
        user = self.cursor.fetchone()
        if user:
            columns = ['user_id', 'username', 'first_name', 'last_name', 'join_date', 'last_seen', 'sticker_count', 'is_banned', 'ban_reason']
            return dict(zip(columns, user))
        return None
    
    def update_last_seen(self, user_id):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute('UPDATE users SET last_seen = ? WHERE user_id = ?', (current_time, user_id))
        self.conn.commit()
    
    def add_sticker(self, user_id, file_id, emoji, is_animated):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        try:
            # Add sticker
            self.cursor.execute('''
                INSERT INTO stickers (user_id, file_id, emoji, is_animated, added_date)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, file_id, emoji, is_animated, current_time))
            
            # Update sticker count
            self.cursor.execute('UPDATE users SET sticker_count = sticker_count + 1 WHERE user_id = ?', (user_id,))
            
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error adding sticker: {e}")
            return False
    
    def get_user_stickers(self, user_id, limit=5):
        self.cursor.execute('''
            SELECT file_id, emoji, is_animated FROM stickers 
            WHERE user_id = ? 
            ORDER BY id DESC 
            LIMIT ?
        ''', (user_id, limit))
        return self.cursor.fetchall()
    
    def get_total_users(self):
        self.cursor.execute('SELECT COUNT(*) FROM users')
        return self.cursor.fetchone()[0]
    
    def get_banned_users(self):
        self.cursor.execute('SELECT user_id, username, first_name, ban_reason FROM users WHERE is_banned = TRUE')
        return self.cursor.fetchall()
    
    def ban_user(self, user_id, reason):
        self.cursor.execute('UPDATE users SET is_banned = TRUE, ban_reason = ? WHERE user_id = ?', (reason, user_id))
        self.conn.commit()
        return True
    
    def unban_user(self, user_id):
        self.cursor.execute('UPDATE users SET is_banned = FALSE, ban_reason = NULL WHERE user_id = ?', (user_id,))
        self.conn.commit()
        return True
    
    def add_log(self, user_id, action):
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.cursor.execute('INSERT INTO logs (user_id, action, timestamp) VALUES (?, ?, ?)', 
                          (user_id, action, current_time))
        self.conn.commit()

# Initialize database
db = Database()

# Admin check
def is_admin(user_id):
    return user_id == OWNER_ID

# Start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.add_user(user.id, user.username, user.first_name, user.last_name)
    db.update_last_seen(user.id)
    db.add_log(user.id, "start_command")
    
    welcome_message = f"""
🎉 Welcome <b>{user.first_name}</b>! 🎉

🤖 I'm <b>{context.bot.first_name}</b> - Your Advanced Telegram Bot

📌 <b>Your Info:</b>
├ Username: @{user.username if user.username else 'Not set'}
├ ID: <code>{user.id}</code>
└ Type: {'Bot' if user.is_bot else 'Human'}

🌟 <b>Features:</b>
• Sticker Collection
• User Management
• Media Support
• Admin Controls

Type /help to see all commands!
    """
    
    keyboard = [
        [InlineKeyboardButton("📊 Stats", callback_data="stats"),
         InlineKeyboardButton("👤 Profile", callback_data="profile")],
        [InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel"),
         InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

# Help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
🤖 *Bot Commands Menu* 🤖

*User Commands:*
/start - Start the bot
/profile - View your profile
/stats - View bot statistics
/id - Get your user ID
/help - Show this help message

*Admin Commands:*
/ban [user_id] [reason] - Ban a user
/unban [user_id] - Unban a user
/users - Get total user count
/banned - List banned users

*Sticker Features:*
- Send any sticker and I'll save it
- Send animated stickers too!

*Other Features:*
- Welcome messages
- User profile viewing
- Media sharing
- Admin controls
    """
    
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)

# Profile command
async def profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    db.update_last_seen(user.id)
    
    if user_data:
        profile_text = f"""
👤 *Profile Information*

*Name:* {user_data['first_name']} {user_data.get('last_name', '')}
*Username:* @{user_data['username'] if user_data['username'] else 'Not set'}
*ID:* `{user_data['user_id']}`
*Join Date:* {user_data['join_date']}
*Last Seen:* {user_data['last_seen']}
*Stickers Saved:* {user_data['sticker_count']}
*Status:* {'🚫 Banned' if user_data['is_banned'] else '✅ Active'}
        """
    else:
        profile_text = f"""
👤 *Profile Information*

*Name:* {user.full_name}
*ID:* `{user.id}`
*Username:* @{user.username if user.username else 'Not set'}
*Bot:* {'Yes' if user.is_bot else 'No'}
        """
    
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)

# Stats command
async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_data = db.get_user(user.id)
    total_users = db.get_total_users()
    
    if user_data:
        stats_text = f"""
📊 *Your Statistics*

User ID: `{user.id}`
Join Date: {user_data['join_date']}
Stickers Saved: {user_data['sticker_count']}
Last Seen: {user_data['last_seen']}
Total Bot Users: {total_users}
        """
    else:
        stats_text = f"""
📊 *Statistics*

User ID: `{user.id}`
Total Bot Users: {total_users}
        """
    
    await update.message.reply_text(stats_text, parse_mode=ParseMode.MARKDOWN)

# ID command
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Your ID: `{user.id}`", parse_mode=ParseMode.MARKDOWN)

# Handle stickers
async def handle_sticker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    sticker = update.message.sticker
    db.update_last_seen(user.id)
    
    # Save sticker
    db.add_sticker(user.id, sticker.file_id, sticker.emoji, sticker.is_animated)
    db.add_log(user.id, f"sticker_sent:{sticker.emoji}")
    
    # Send response
    if sticker.is_animated:
        await update.message.reply_text("✨ Cool animated sticker! Saved to your collection.")
    else:
        await update.message.reply_text("👍 Nice sticker! Saved to your collection.")

# Show user stickers
async def show_stickers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    stickers = db.get_user_stickers(user.id)
    db.update_last_seen(user.id)
    
    if stickers:
        response = f"📁 *Your Recent Stickers* ({len(stickers)})\n\n"
        for sticker in stickers:
            file_id, emoji, is_animated = sticker
            response += f"• {emoji} ({'Animated' if is_animated else 'Static'})\n"
        
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
        
        # Send the most recent sticker
        if stickers:
            most_recent = stickers[0]
            file_id, emoji, is_animated = most_recent
            await context.bot.send_sticker(chat_id=update.effective_chat.id, sticker=file_id)
    else:
        await update.message.reply_text("📭 You haven't saved any stickers yet! Send me a sticker and I'll save it for you! 😊")

# Admin: Total users
async def total_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command!")
        return
    
    total = db.get_total_users()
    await update.message.reply_text(f"👥 Total Users: {total}")

# Admin: Ban user
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id> <reason>")
        return
    
    try:
        target_id = int(context.args[0])
        reason = ' '.join(context.args[1:]) or "No reason provided"
        
        db.ban_user(target_id, reason)
        db.add_log(user.id, f"banned:{target_id}")
        
        await update.message.reply_text(f"✅ User {target_id} has been banned.\nReason: {reason}")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID!")

# Admin: Unban user
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command!")
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    
    try:
        target_id = int(context.args[0])
        db.unban_user(target_id)
        db.add_log(user.id, f"unbanned:{target_id}")
        
        await update.message.reply_text(f"✅ User {target_id} has been unbanned.")
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID!")

# Admin: List banned users
async def banned_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if not is_admin(user.id):
        await update.message.reply_text("❌ You are not authorized to use this command!")
        return
    
    banned = db.get_banned_users()
    
    if banned:
        response = "🚫 *Banned Users*\n\n"
        for banned_user in banned:
            user_id, username, first_name, reason = banned_user
            response += f"• ID: `{user_id}`\nName: {first_name}\nReason: {reason}\n\n"
        
        await update.message.reply_text(response, parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text("✅ No users are currently banned.")

# Ping command
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🏓 Pong! Bot is alive and working!")

# Button callbacks
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "stats":
        user = query.from_user
        user_data = db.get_user(user.id)
        total_users = db.get_total_users()
        
        if user_data:
            stats_text = f"""
📊 *Your Statistics*

User ID: `{user.id}`
Join Date: {user_data['join_date']}
Stickers Saved: {user_data['sticker_count']}
Last Seen: {user_data['last_seen']}
Total Bot Users: {total_users}
            """
        else:
            stats_text = f"""
📊 *Statistics*

User ID: `{user.id}`
Total Bot Users: {total_users}
            """
        
        await query.edit_message_text(stats_text, parse_mode=ParseMode.MARKDOWN)
    
    elif data == "profile":
        user = query.from_user
        user_data = db.get_user(user.id)
        
        if user_data:
            profile_text = f"""
👤 *Profile Information*

*Name:* {user_data['first_name']} {user_data.get('last_name', '')}
*Username:* @{user_data['username'] if user_data['username'] else 'Not set'}
*ID:* `{user_data['user_id']}`
*Join Date:* {user_data['join_date']}
*Last Seen:* {user_data['last_seen']}
*Stickers Saved:* {user_data['sticker_count']}
*Status:* {'🚫 Banned' if user_data['is_banned'] else '✅ Active'}
            """
        else:
            profile_text = f"""
👤 *Profile Information*

*Name:* {user.full_name}
*ID:* `{user.id}`
*Username:* @{user.username if user.username else 'Not set'}
            """
        
        await query.edit_message_text(profile_text, parse_mode=ParseMode.MARKDOWN)
    
    elif data == "admin_panel":
        if is_admin(query.from_user.id):
            admin_text = """
🛠 *Admin Panel*

*Commands:*
/ban - Ban a user
/unban - Unban a user
/users - View statistics
/banned - List banned users

*Quick Actions:*
• Check /users for statistics
• Use /banned to see banned users
            """
            await query.edit_message_text(admin_text, parse_mode=ParseMode.MARKDOWN)
        else:
            await query.edit_message_text("❌ Access denied!")
    
    elif data == "help":
        await query.edit_message_text("Type /help to see all available commands!", parse_mode=ParseMode.MARKDOWN)

# Error handler
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Update {update} caused error {context.error}")
    try:
        await context.bot.send_message(chat_id=OWNER_ID, text=f"⚠️ Bot Error:\n\n{context.error}")
    except:
        pass

# Main function
def main():
    """Start the bot"""
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", profile))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("id", get_id))
    application.add_handler(CommandHandler("ping", ping))
    application.add_handler(CommandHandler("stickers", show_stickers))
    application.add_handler(CommandHandler("users", total_users))
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("banned", banned_users))
    
    # Add message handlers
    application.add_handler(MessageHandler(filters.Sticker.ALL, handle_sticker))
    
    # Add callback query handler
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
