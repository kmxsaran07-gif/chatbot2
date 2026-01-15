# Advanced Telegram Bot

A feature-rich Telegram bot with professional features, optimized for Render deployment.

## Features

✅ Custom Welcome Message
✅ Sticker Support (Animated + Video)
✅ User Ban/Unban System
✅ User Profile Viewing
✅ Total Users Count
✅ Broadcast System
✅ Database Backup
✅ Admin Panel
✅ Activity Logs
✅ Error Handling
✅ Media Support

## Setup Instructions

1. **Get Bot Token:**
   - Message @BotFather on Telegram
   - Send `/newbot`
   - Follow instructions
   - Copy the bot token

2. **Get Your User ID:**
   - Message @userinfobot on Telegram
   - Send `/start`
   - Copy your user ID

3. **Update Configuration:**
   - Copy `.env.example` to `.env`
   - Update with your bot token and user ID

4. **Deploy on Render:**
   - Create new Web Service
   - Connect GitHub repository
   - Set environment variables
   - Deploy

## Environment Variables in Render

Add these variables in Render dashboard:

- `BOT_TOKEN`: Your bot token from @BotFather
- `OWNER_ID`: Your Telegram user ID
- `ADMIN_IDS`: Additional admin IDs (comma-separated)
- `PORT`: 8443

## Bot Commands

### User Commands:
- `/start` - Start the bot
- `/help` - Show help
- `/profile` - View profile
- `/stats` - Your statistics
- `/id` - Get your ID
- `/mystickers` - Your saved stickers
- `/ping` - Check if bot is alive

### Admin Commands:
- `/ban <id> <reason>` - Ban user
- `/unban <id>` - Unban user
- `/broadcast <msg>` - Send to all users
- `/users` - Bot statistics
- `/userinfo <id>` - User details
- `/banned` - List banned users
- `/backup` - Database backup

## Support

If you encounter issues:
1. Check Render logs
2. Verify environment variables
3. Ensure bot token is correct
