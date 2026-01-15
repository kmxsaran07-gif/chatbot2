import os
import logging
import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatPermissions
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
    get_banned_users, get_user_stats, add_log
)
from utils import (
    send_broadcast, format_user_info, 
    is_admin, parse_time, backup_database
)

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class AdvancedTelegramBot:
    def __init__(self):
        self.application = None
        self.bot_start_time = datetime.now(pytz.timezone(TIMEZONE))
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        chat = update.effective_chat
        
        # Add user to database
        user_data = {
            'user_id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'is_bot': user.is_bot,
            'language_code': user.language_code,
            'join_date': datetime.now(pytz.timezone(TIMEZONE))
        }
        
        if chat.type == ChatType.PRIVATE:
            add_user(user_data)
            
            # Send welcome message with customization
            welcome_msg = WELCOME_MESSAGE.format(
                first_name=user.first_name,
                username=f"@{user.username}" if user.username else "No username",
                user_id=user.id,
                bot_name=context.bot.first_name
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
        else:
            await update.message.reply_text(
                f"👋 Hello {user.first_name}! I'm alive and working in this group!"
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
/ban [user_id/reply] [reason] - Ban a user
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
        if not await is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /ban <user_id> <reason>")
            return
        
        try:
            user_id = int(context.args[0])
            reason = ' '.join(context.args[1:]) if len(context.args) > 1 else "No reason provided"
            
            # Ban user in database
            ban_user(user_id, reason, update.effective_user.id)
            
            # Send ban message to user if possible
            try:
                ban_msg = BAN_MESSAGE.format(
                    reason=reason,
                    admin_id=update.effective_user.id,
                    appeal_contact=f"tg://user?id={OWNER_ID}"
                )
                await context.bot.send_message(
                    chat_id=user_id,
                    text=ban_msg,
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
            
            await update.message.reply_text(
                f"✅ User {user_id} has been banned.\nReason: {reason}"
            )
            add_log(update.effective_user.id, "ban_user", f"Banned user {user_id}")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
    
    async def unban_user(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Unban a user"""
        if not await is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /unban <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            
            # Unban user
            unban_user(user_id)
            
            # Send unban message to user
            try:
                unban_msg = UNBAN_MESSAGE.format(admin_id=update.effective_user.id)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=unban_msg,
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
            
            await update.message.reply_text(f"✅ User {user_id} has been unbanned.")
            add_log(update.effective_user.id, "unban_user", f"Unbanned user {user_id}")
            
        except ValueError:
            await update.message.reply_text("❌ Invalid user ID!")
    
    async def broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Broadcast message to all users"""
        if not await is_admin(update.effective_user.id):
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
        if not await is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        stats = get_user_stats()
        uptime = datetime.now(pytz.timezone(TIMEZONE)) - self.bot_start_time
        
        stats_text = f"""
📊 *Bot Statistics*

👥 Total Users: {stats['total_users']}
📈 Today's New Users: {stats['today_users']}
🚫 Banned Users: {stats['banned_users']}
📅 Bot Uptime: {str(uptime).split('.')[0]}
🔄 Last Backup: {stats.get('last_backup', 'Never')}
        """
        
        await update.message.reply_text(
            stats_text,
            parse_mode=ParseMode.MARKDOWN
        )
    
    async def user_info(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get detailed user information"""
        if not await is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        if not context.args:
            await update.message.reply_text("Usage: /userinfo <user_id>")
            return
        
        try:
            user_id = int(context.args[0])
            user_data = get_user(user_id)
            
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
    
    async def handle_sticker(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle sticker messages"""
        user = update.effective_user
        sticker = update.message.sticker
        
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
                'date': datetime.now(pytz.timezone(TIMEZONE))
            }
            stickers.append(sticker_data)
            update_user(user.id, {'stickers': stickers})
        
        # React to sticker
        if sticker.is_animated:
            response = "✨ Cool animated sticker!"
        elif sticker.is_video:
            response = "🎥 Nice video sticker!"
        else:
            response = "👍 Nice sticker!"
        
        await update.message.reply_text(response)
        add_log(user.id, "sticker_sent", f"Sticker: {sticker.emoji}")
    
    async def my_stickers(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's saved stickers"""
        user = update.effective_user
        user_info = get_user(user.id)
        
        if user_info and 'stickers' in user_info and user_info['stickers']:
            sticker_count = len(user_info['stickers'])
            animated_count = sum(1 for s in user_info['stickers'] if s.get('is_animated'))
            video_count = sum(1 for s in user_info['stickers'] if s.get('is_video'))
            
            stats_text = f"""
📊 *Your Sticker Collection*

Total Stickers: {sticker_count}
✨ Animated: {animated_count}
🎥 Video: {video_count}

Send any sticker to add it to your collection!
            """
            
            # Send last 5 stickers
            await update.message.reply_text(
                stats_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Send recent stickers
            recent_stickers = user_info['stickers'][-5:]  # Last 5 stickers
            for sticker in recent_stickers:
                try:
                    await context.bot.send_sticker(
                        chat_id=update.effective_chat.id,
                        sticker=sticker['file_id']
                    )
                except:
                    continue
        else:
            await update.message.reply_text(
                "📭 You haven't saved any stickers yet!\n\nSend me a sticker and I'll save it for you! 😊"
            )
    
    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button callbacks"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        
        if data == "stats":
            stats = get_user_stats()
            stats_text = f"""
📊 *Your Statistics*

User ID: `{query.from_user.id}`
Join Date: {get_user(query.from_user.id).get('join_date', 'Unknown')}
Saved Stickers: {len(get_user(query.from_user.id).get('stickers', []))}
            """
            await query.edit_message_text(
                stats_text,
                parse_mode=ParseMode.MARKDOWN
            )
            
        elif data == "profile":
            await self.profile(query, context)
            
        elif data == "admin_panel":
            if await is_admin(query.from_user.id):
                admin_text = """
🛠 *Admin Panel*

Commands:
/ban - Ban a user
/unban - Unban a user
/broadcast - Send message to all users
/users - View statistics
/banned - List banned users
/backup - Get database backup
/userinfo - Get user details
                """
                await query.edit_message_text(
                    admin_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await query.edit_message_text("❌ Access denied!")
                
        elif data == "help":
            await self.help_command(query, context)
            
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
    
    async def backup_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Create database backup"""
        if not await is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        backup_file = backup_database()
        if backup_file:
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=open(backup_file, 'rb'),
                filename=os.path.basename(backup_file),
                caption="📦 Database Backup"
            )
        else:
            await update.message.reply_text("❌ Failed to create backup!")
    
    async def banned_users(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """List all banned users"""
        if not await is_admin(update.effective_user.id):
            await update.message.reply_text("❌ You are not authorized to use this command!")
            return
        
        banned = get_banned_users()
        if banned:
            banned_text = "🚫 *Banned Users*\n\n"
            for user in banned:
                banned_text += f"• ID: `{user['user_id']}`\nReason: {user['ban_reason']}\n\n"
            
            await update.message.reply_text(
                banned_text,
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            await update.message.reply_text("✅ No users are currently banned.")
    
    async def get_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Get user ID"""
        user = update.effective_user
        await update.message.reply_text(f"Your ID: `{user.id}`", parse_mode=ParseMode.MARKDOWN)
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        try:
            await context.bot.send_message(
                chat_id=OWNER_ID,
                text=f"⚠️ Bot Error:\n\n{context.error}"
            )
        except:
            pass
    
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
        
        # Message handlers
        self.application.add_handler(MessageHandler(
            filters.Sticker.ALL, self.handle_sticker))
        
        # Callback query handler
        self.application.add_handler(CallbackQueryHandler(self.button_callback))
        
        # Error handler
        self.application.add_error_handler(self.error_handler)
    
    async def run(self):
        """Start the bot"""
        # Initialize database
        init_db()
        
        # Create application
        self.application = Application.builder().token(BOT_TOKEN).build()
        
        # Setup handlers
        self.setup_handlers()
        
        # Start bot
        logger.info("Bot is starting...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        # Keep running
        await self.application.idle()
        
        # Stop bot
        await self.application.stop()

def main():
    """Main function to run the bot"""
    bot = AdvancedTelegramBot()
    
    # Run bot with asyncio
    asyncio.run(bot.run())

if __name__ == '__main__':
    main()
