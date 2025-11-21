import os
import logging
import requests
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI
import schedule
import time
import threading
from datetime import datetime

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get credentials from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')  # Your group chat ID

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class TelegramGroupManager:
    def __init__(self):
        self.bot_username = None
        
    async def initialize_bot(self, application):
        """Get bot username"""
        bot_info = await application.bot.get_me()
        self.bot_username = bot_info.username
        logger.info(f"Bot initialized: @{self.bot_username}")

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        await update.message.reply_text(
            "🤖 Hello! I'm your group management bot. I can:\n"
            "• Monitor group activity\n"
            "• Post daily news\n"
            "• Respond to messages intelligently\n"
            "• Keep the group safe from spam\n\n"
            "Add me to your group and make me an admin for full functionality!"
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📋 **Available Commands:**
/start - Start the bot
/help - Show this help message
/news - Get latest news summary
/rules - Show group rules
/stats - Group statistics (admin only)

🔧 **Auto Features:**
• Daily news posting
• Smart chat responses
• Spam protection
• Content moderation
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def post_news_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Post news to group"""
        if str(update.effective_chat.id) != GROUP_CHAT_ID:
            return
            
        news = await self.get_news_summary()
        if news:
            await context.bot.send_message(
                chat_id=GROUP_CHAT_ID,
                text=news,
                parse_mode='Markdown'
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all incoming messages"""
        try:
            # Ignore messages from bots
            if update.message.from_user.is_bot:
                return

            message = update.message
            chat_id = message.chat_id
            text = message.text or message.caption or ""

            # Only respond in the designated group
            if str(chat_id) != GROUP_CHAT_ID:
                return

            # Check if bot is mentioned or message is a reply to bot
            should_respond = (
                self.bot_username and f"@{self.bot_username}" in text
                or (message.reply_to_message and 
                    message.reply_to_message.from_user.username == self.bot_username)
                or await self.should_respond_to_message(text)
            )

            if should_respond:
                response = await self.generate_ai_response(text, message.from_user.first_name)
                if response:
                    await message.reply_text(response)

            # Monitor for inappropriate content
            await self.monitor_content(update, context)

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def should_respond_to_message(self, text: str) -> bool:
        """Determine if bot should respond to a message"""
        if not text.strip():
            return False

        # Check for questions or direct addressing
        triggers = ['?', 'what', 'how', 'why', 'when', 'where', 'who', 'tell me', 'explain']
        text_lower = text.lower()
        
        return any(trigger in text_lower for trigger in triggers) and len(text) > 10

    async def generate_ai_response(self, user_message: str, user_name: str) -> str:
        """Generate AI response using OpenAI"""
        try:
            prompt = f"""
            You are a helpful assistant in a Telegram group chat. 
            User: {user_name}
            Message: {user_message}
            
            Respond in a friendly, conversational tone. Keep responses concise (1-2 sentences max). 
            If it's a question, answer helpfully. If it's just a statement, respond appropriately.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You're a friendly group chat assistant. Be concise and helpful."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=150,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            return None

    async def get_news_summary(self) -> str:
        """Get news summary using OpenAI"""
        try:
            prompt = """
            Create a brief daily news summary with 3-5 interesting news headlines from around the world.
            Format it nicely with emojis and make it engaging for a group chat.
            Include diverse topics like technology, science, world news, and interesting facts.
            Keep it concise and under 400 characters.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You're a news reporter creating engaging daily summaries."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.7
            )
            
            news = response.choices[0].message.content.strip()
            return f"📰 **Daily News Update** 📰\n\n{news}\n\n#News #Update"
            
        except Exception as e:
            logger.error(f"Error getting news: {e}")
            return "❌ Could not fetch news at the moment. Please try again later."

    async def monitor_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Monitor messages for inappropriate content"""
        try:
            message = update.message
            text = (message.text or message.caption or "").lower()

            # List of inappropriate words/phrases (you can expand this)
            inappropriate_words = [
                'spam', 'http://', 'https://', 'www.', '.com', 'buy now',
                'click here', 'free money', 'lottery', 'casino'
            ]

            # Check for spammy content
            if any(word in text for word in inappropriate_words):
                # Delete the message
                await message.delete()
                
                # Warn the user
                warning_msg = (
                    f"⚠️ Warning @{message.from_user.username or message.from_user.first_name}!\n"
                    "Please avoid posting spam or promotional content in this group."
                )
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=warning_msg
                )
                logger.info(f"Deleted spam message from user {message.from_user.id}")

        except Exception as e:
            logger.error(f"Error monitoring content: {e}")

    async def post_daily_news(self, application):
        """Post daily news to the group"""
        try:
            news = await self.get_news_summary()
            if news:
                await application.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=news,
                    parse_mode='Markdown'
                )
                logger.info("Daily news posted successfully")
        except Exception as e:
            logger.error(f"Error posting daily news: {e}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")

def schedule_daily_tasks(application, group_manager):
    """Schedule daily tasks"""
    def run_scheduler():
        # Schedule daily news at 9:00 AM
        schedule.every().day.at("09:00").do(
            lambda: asyncio.run_coroutine_threadsafe(
                group_manager.post_daily_news(application), 
                application.create_task
            )
        )

        while True:
            schedule.run_pending()
            time.sleep(60)

    # Start scheduler in a separate thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()

async def post_manual_news(application):
    """Manual news posting function"""
    group_manager = TelegramGroupManager()
    await group_manager.post_daily_news(application)

def main():
    """Start the bot"""
    if not all([TELEGRAM_BOT_TOKEN, OPENAI_API_KEY, GROUP_CHAT_ID]):
        raise ValueError("Please set all required environment variables")
    
    # Create application
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    group_manager = TelegramGroupManager()

    # Add handlers
    application.add_handler(CommandHandler("start", group_manager.start_command))
    application.add_handler(CommandHandler("help", group_manager.help_command))
    application.add_handler(CommandHandler("news", group_manager.post_news_command))
    application.add_handler(MessageHandler(filters.ALL, group_manager.handle_message))
    
    # Error handler
    application.add_error_handler(group_manager.error_handler)

    # Initialize bot
    application.post_init(group_manager.initialize_bot)

    # Start scheduled tasks
    schedule_daily_tasks(application, group_manager)

    # Start the Bot
    logger.info("Bot is starting...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
