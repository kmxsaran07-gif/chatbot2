# Advanced Telegram Bot

A feature-rich Telegram bot with professional features, optimized for Render deployment.

## Features

✅ **User Management**
- User banning/unbanning
- User profile viewing
- Total user statistics
- Activity logs

✅ **Sticker Support**
- Save and collect stickers
- Animated sticker support
- Video sticker support
- Personal sticker collection

✅ **Admin Features**
- Broadcast messages
- Database backup
- User information lookup
- Advanced admin controls

✅ **Professional Features**
- Custom welcome messages
- Timezone support
- Error handling
- Automatic backups
- Activity logging

## Deployment on Render

### Prerequisites
1. Telegram Bot Token from [@BotFather](https://t.me/botfather)
2. Your Telegram User ID
3. Render account (free tier available)

### Step-by-Step Deployment

1. **Create a new bot on Telegram:**
   - Message [@BotFather](https://t.me/botfather)
   - Send `/newbot`
   - Follow instructions to get your `BOT_TOKEN`

2. **Get your Telegram User ID:**
   - Message [@userinfobot](https://t.me/userinfobot)
   - Copy your user ID

3. **Prepare the code:**
   - Download all files
   - Update `.env.example` with your credentials
   - Rename `.env.example` to `.env`

4. **Create GitHub Repository:**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
   git push -u origin main
