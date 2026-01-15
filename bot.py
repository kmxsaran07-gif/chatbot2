import os
import logging
import asyncio
import sys
import signal
from datetime import datetime
from typing import Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)
from telegram.constants import ParseMode, ChatType
import pytz

# Import custom modules
from config import (
    BOT_TOKEN, OWNER_ID, WELCOME_MESSAGE, BAN_MESSAGE,
    UNBAN_MESSAGE, ADMIN_IDS, TIMEZONE
)
from database import (
    init_db, add_user, get_user, update_user,
    get_all_users, ban_user, unban_user,
    get_banned_users, get_user_stats, backup_database, add_log
)
from utils import (
    send_broadcast, format_user_info,
    is_admin, parse_time, format_time,
    get_current_time, create_backup_dir
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

class AdvancedTelegramBot:
    def __init__(self):
        self.application = None
        self.bot_start_time = get_current_time()
        self.is_running = False
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        
        # Add user to database
        user_data = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_bot': user.is_bot,
            'language_code': user.language_code,
            'join_date': get_current_time()
        }
        
        add_user(user_data)
        
        # Send welcome message with customization
        welcome_msg = WELCOME_MESSAGE.format(
            first_name=user.first_name,
            username=f"@{user.username}" if user.username else "No username",
            user_id=user.id,
            bot_name=context.bot.first_name,
            is_bot='Bot' if user.is_bot else 'Human'
        )
        
        keyboard = [
            [InlineKeyboardButton("📊 Stats", callback_data="stats"),
             InlineKeyboardButton("👤 Profile", callback_data="profile")],
            [InlineKeyboardButton("🛠 Admin Panel", callback_data="admin_panel")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            welcome_msg,
            reply_markup=reply_markup,
            parse_mode=ParseMode.HTML
        )
        
        add_log(user.id, "start_command", "User used /start command")
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
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
/broadcast [message] - Broadcast message to all users
/users - Get total user count
/banned - List banned users
/backup - Get database backup
/userinfo [user_id] - Get user information

*Sticker Features:*
- Send any sticker and I'll save it
- Use /mystickers to see your saved stickers
- Send animated stickers too!

*Other Features:*
- Welcome messages
- User profile viewing
- Media sharing
- Advanced admin controls
- Activity logs
        """
        
        keyboard = [
            [InlineKeyboardButton("📞 Contact Admin", url=f"tg://user?id={OWNER_ID}")],
            [InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user profile with photo"""
        user = update.effective_user
        
        try:
            # Get user photos
            photos = await context.bot.get_user_profile_photos(user.id, limit=1)
            
            # Get user info from database
            user_info = get_user(user.id)
            if user_info:
                profile_text = format_user_info(user_info)
            else:
                profile_text = f"""
👤 *Profile Information*

*Name:* {user.full_name}
*ID:* `{user.id}`
*Username:* @{user.username if user.username else 'Not set'}
*Bot:* {'Yes' if user.is_bot else 'No'}
*Language:* {user.language_code if user.language_code else 'Unknown'}
                """
            
            if photos.total_count > 0:
                # Send profile with photo
                photo_file = await photos.photos[0][-1].get_file()
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=photo_file.file_id,
                    caption=profile_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                # Send profile without photo
                await update.message.reply_text(
                    profile_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
        except Exception as e:
            logger.error(f"Error in profile command: {e}")
            await update.message.reply_text(
                "❌ Could not fetch profile information. Please try again later."
            )
    
    async def ban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Ban a user from using the bot"""
        user_id = update.effective_user.id
        if not await is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /ban <user_id> <reason>")
            return
        
        try:
            target_id = int(context.args[0])
            reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
            
            # Ban user in database
            ban_user(target_id, reason, user_id)
            
            # Send ban message to user if possible
            try:
                ban_msg = BAN_MESSAGE.format(
                    reason=reason,
                    admin_id=user_id,
                    appeal_contact=f"tg://user?id={OWNER_ID}"
                )
                await context.bot.send_message(
                    chat_id=target_id,
                    text=ban_msg,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Could not send ban message to user {target_id}: {e}")
            
            await update.message.reply_text(
                f"✅ User {target_id} has been banned.\nReason: {reason}"
            )
            add_log(user_id, "ban_user", f"Banned user {target_id} for: {reason}")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
        except Exception as e:
            logger.error(f"Error in ban command: {e}")
            await update.message.reply_text("❌ Error banning user!")
    
    async def unban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unban a user"""
        user_id = update.effective_user.id
        if not await is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unban <user_id>")
            return
        
        try:
            target_id = int(context.args[0])
            
            # Unban user
            unban_user(target_id)
            
            # Send unban message to user
            try:
                unban_msg = UNBAN_MESSAGE.format(admin_id=user_id)
                await context.bot.send_message(
                    chat_id=target_id,
                    text=unban_msg,
                    parse_mode=ParseMode.HTML
                )
            except Exception as e:
                logger.error(f"Could not send unban message to user {target_id}: {e}")
            
            await update.message.reply_text(f"✅ User {target_id} has been unbanned.")
            add_log(user_id, "unban_user", f"Unbanned user {target_id}")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
        except Exception as e:
            logger.error(f"Error in unban command: {e}")
            await update.message.reply_text("❌ Error unbanning user!")
    
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message to all users"""
        user_id = update.effective_user.id
        if not await is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /broadcast <message>")
            return
        
        message = ' '.join(context.args)
        confirmation_keyboard = [
            [InlineKeyboardButton("✅ Confirm", callback_data=f"confirm_broadcast:{message}"),
             InlineKeyboardButton("❌ Cancel", callback_data="cancel_broadcast")]
        ]
        reply_markup = InlineKeyboardMarkup(confirmation_keyboard)
        
        await update.message.reply_text(
            f"⚠️ *Broadcast Confirmation*\n\nMessage: {message}\n\nSend to all users?",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    async def total_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show total users count"""
        user_id = update.effective_user.id
        if not await is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        stats = get_user_stats()
        uptime = get_current_time() - self.bot_start_time
        
        # Format uptime
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        stats_text = f"""
📊 *Bot Statistics*

👥 Total Users: {stats['total_users']}
📈 Today's New Users: {stats['today_users']}
🚫 Banned Users: {stats['banned_users']}
📅 Bot Uptime: {uptime_str}
🔄 Last Backup: {stats.get('last_backup', 'Never')}
        """
        
        await update.message.reply_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def user_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get detailed user information"""
        user_id = update.effective_user.id
        if not await is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /userinfo <user_id>")
            return
        
        try:
            target_id = int(context.args[0])
            user_data = get_user(target_id)
            
            if user_data:
                info_text = format_user_info(user_data, detailed=True)
                await update.message.reply_text(
                    info_text,
                    parse_mode=ParseMode.HTML
                )
            else:
                await update.message.reply_text("❌ User not found in database!")
                
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
        except Exception as e:
            logger.error(f"Error in userinfo command: {e}")
            await update.message.reply_text("❌ Error getting user info!")
    
    async def handle_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle sticker messages"""
        user = update.effective_user
        sticker = update.message.sticker
        
        try:
            # Save sticker info to user's collection
            user_info = get_user(user.id)
            if user_info:
                stickers = user_info.get('stickers', [])
                sticker_data = {
                    'file_id': sticker.file_id,
                    'emoji': sticker.emoji,
                    'file_size': sticker.file_size,
                    'is_animated': sticker.is_animated,
                    'is_video': sticker.is_video,
                    'date': get_current_time()
                }
                stickers.append(sticker_data)
                update_user(user.id, {'stickers': stickers})
            
            # React to sticker
            if sticker.is_animated:
                response = "✨ Cool animated sticker! Saved to your collection."
            elif sticker.is_video:
                response = "🎥 Nice video sticker! Saved to your collection."
            else:
                response = "👍 Nice sticker! Saved to your collection."
            
            await update.message.reply_text(response)
            add_log(user.id, "sticker_sent", f"Sticker: {sticker.emoji}")
            
        except Exception as e:
            logger.error(f"Error handling sticker: {e}")
            await update.message.reply_text("👍 Nice sticker!")
    
    async def my_stickers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's saved stickers"""
        user = update.effective_user
        user_info = get_user(user.id)
        
        try:
            if user_info and 'stickers' in user_info and user_info['stickers']:
                sticker_count = len(user_info['stickers'])
                animated_count = sum(1 for s in user_info['stickers'] if s.get('is_animated'))
                video_count = sum(1 for s in user_info['stickers'] if s.get('is_video'))
                
                stats_text = f"""
📊 *Your Sticker Collection*

Total Stickers: {sticker_count}
✨ Animated: {animated_count}
🎥 Video: {video_count}

*Recent stickers:*
                """
                
                await update.message.reply_text(
                    stats_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
                # Send recent stickers (last 3)
                recent_stickers = user_info['stickers'][-3:]
                for sticker_data in recent_stickers:
                    try:
                        await context.bot.send_sticker(
                            chat_id=update.effective_chat.id,
                            sticker=sticker_data['file_id']
                        )
                        await asyncio.sleep(0.5)  # Small delay
                    except Exception as e:
                        logger.error(f"Error sending sticker: {e}")
                        continue
            else:
                await update.message.reply_text(
                    "📭 You haven't saved any stickers yet!\n\nSend me a sticker and I'll save it for you! 😊"
                )
                
        except Exception as e:
            logger.error(f"Error in mystickers command: {e}")
            await update.message.reply_text("❌ Error fetching your stickers!")
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        try:
            if data == "stats":
                user_data = get_user(query.from_user.id)
                if user_data:
                    sticker_count = len(user_data.get('stickers', []))
                    stats_text = f"""
📊 *Your Statistics*

User ID: `{query.from_user.id}`
Join Date: {user_data.get('join_date', 'Unknown')}
Saved Stickers: {sticker_count}
Last Seen: {user_data.get('last_seen', 'Unknown')}
                    """
                else:
                    stats_text = f"""
📊 *Your Statistics*

User ID: `{query.from_user.id}`
Join Date: Unknown (You're not in database yet!)
                    """
                
                await query.edit_message_text(
                    stats_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
            elif data == "profile":
                user = query.from_user
                user_data = get_user(user.id)
                if user_data:
                    profile_text = format_user_info(user_data)
                else:
                    profile_text = f"""
👤 *Profile Information*

*Name:* {user.full_name}
*ID:* `{user.id}`
*Username:* @{user.username if user.username else 'Not set'}
*Bot:* {'Yes' if user.is_bot else 'No'}
                    """
                
                await query.edit_message_text(
                    profile_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
            elif data == "admin_panel":
                if await is_admin(query.from_user.id):
                    admin_text = """
🛠 *Admin Panel*

*Commands:*
/ban - Ban a user
/unban - Unban a user
/broadcast - Send message to all users
/users - View statistics
/banned - List banned users
/backup - Get database backup
/userinfo - Get user details

*Quick Actions:*
• Check /users for statistics
• Use /banned to see banned users
• /broadcast to message everyone
                    """
                    await query.edit_message_text(
                        admin_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await query.edit_message_text("❌ Access denied!")
                    
            elif data == "help":
                await query.edit_message_text(
                    "Type /help to see all available commands!",
                    parse_mode=ParseMode.MARKDOWN
                )
                
            elif data.startswith("confirm_broadcast:"):
                message = data.split(":", 1)[1]
                await query.edit_message_text("📢 Broadcasting message to all users...")
                
                success, failed = await send_broadcast(
                    context.bot,
                    message,
                    parse_mode=ParseMode.HTML
                )
                
                await query.edit_message_text(
                    f"✅ Broadcast completed!\n\nSuccess: {success}\nFailed: {failed}"
                )
                
            elif data == "cancel_broadcast":
                await query.edit_message_text("❌ Broadcast cancelled.")
                
        except Exception as e:
            logger.error(f"Error in button callback: {e}")
            await query.edit_message_text("❌ An error occurred!")
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create database backup"""
        user_id = update.effective_user.id
        if not await is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        await update.message.reply_text("🔄 Creating database backup...")
        
        try:
            backup_file = backup_database()
            if backup_file and os.path.exists(backup_file):
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=open(backup_file, 'rb'),
                    filename=os.path.basename(backup_file),
                    caption="📦 Database Backup"
                )
            else:
                await update.message.reply_text("❌ Failed to create backup!")
        except Exception as e:
            logger.error(f"Error in backup command: {e}")
            await update.message.reply_text("❌ Error creating backup!")
    
    async def banned_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all banned users"""
        user_id = update.effective_user.id
        if not await is_admin(user_id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        try:
            banned = get_banned_users()
            if banned:
                banned_text = "🚫 *Banned Users*\n\n"
                for user in banned:
                    banned_text += f"• ID: `{user['user_id']}`\nReason: {user['ban_reason']}\n\n"
                
                if len(banned_text) > 4000:
                    # Split long messages
                    parts = [banned_text[i:i+4000] for i in range(0, len(banned_text), 4000)]
                    for part in parts:
                        await update.message.reply_text(
                            part,
                            parse_mode=ParseMode.MARKDOWN
                        )
                else:
                    await update.message.reply_text(
                        banned_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
            else:
                await update.message.reply_text("✅ No users are currently banned.")
        except Exception as e:
            logger.error(f"Error in banned command: {e}")
            await update.message.reply_text("❌ Error fetching banned users!")
    
    async def get_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user ID"""
        user = update.effective_user
        await update.message.reply_text(f"Your ID: `{user.id}`", parse_mode=ParseMode.MARKDOWN)
    
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user statistics"""
        user = update.effective_user
        user_data = get_user(user.id)
        
        if user_data:
            sticker_count = len(user_data.get('stickers', []))
            stats_text = f"""
📊 *Your Statistics*

User ID: `{user.id}`
Join Date: {user_data.get('join_date', 'Unknown')}
Saved Stickers: {sticker_count}
Last Seen: {user_data.get('last_seen', 'Unknown')}
            """
        else:
            stats_text = f"""
📊 *Your Statistics*

User ID: `{user.id}`
Join Date: Unknown (You're not in database yet!)
            """
        
        await update.message.reply_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def ping_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Check if bot is alive"""
        await update.message.reply_text("🏓 Pong! Bot is alive and working!")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"⚠️ Bot Error:\n\n{context.error}"
            )
        except Exception as e:
            logger.error(f"Could not send error to owner: {e}")
    
    def setup_handlers(self):
        """Setup all command handlers"""
        # Command handlers
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CommandHandler("profile", self.profile))
        self.application.add_handler(CommandHandler("ban", self.ban_user))
        self.application.add_handler(CommandHandler("unban", self.unban_user))
        self.application.add_handler(CommandHandler("broadcast", self.broadcast))
        self.application.add_handler(CommandHandler("users", self.total_users))
        self.application.add_handler(CommandHandler("userinfo", self.user_info))
        self.application.add_handler(CommandHandler("mystickers", self.my_stickers))
        self.application.add_handler(CommandHandler("backup", self.backup_command))
        self.application.add_handler(CommandHandler("banned", self.banned_users))
        self.application.add_handler(CommandHandler("id", self.get_id))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("ping", self.ping_command))
        
        # Message handlers
        self.application.add_handler(MessageHandler(
            filters.Sticker.ALL, self.handle_sticker))
        
        # Callback query handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def start_polling(self):
        """Start the bot with polling"""
        # Initialize database
        init_db()
        create_backup_dir()
        
        logger.info("Initializing bot...")
        
        # Create application
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Setup handlers
        self.setup_handlers()
        
        # Start bot
        logger.info("Bot is starting...")
        
        # Get bot info
        bot_info = await self.application.bot.get_me()
        logger.info(f"Bot @{bot_info.username} is running!")
        
        # Start polling
        await self.application.initialize()
        await self.application.start()
        
        # Start polling manually without updater
        await self.application.updater.start_polling()
        
        # Set running flag
        self.is_running = True
        logger.info("Bot is now polling for updates...")
        
        # Keep bot running
        while self.is_running:
            await asyncio.sleep(1)
    
    async def stop(self):
        """Stop the bot gracefully"""
        logger.info("Stopping bot...")
        self.is_running = False
        
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
        
        logger.info("Bot stopped successfully")

def signal_handler(signum, frame):
    """Handle shutdown signals"""
    logger.info(f"Received signal {signum}, shutting down...")
    sys.exit(0)

def main():
    """Main function to run the bot"""
    # Set up signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        logger.info("Starting Telegram Bot...")
        bot = AdvancedTelegramBot()
        
        # Run bot
        asyncio.run(bot.start_polling())
        
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

if __name__ == '__main__':
    main()
