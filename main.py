import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackContext
from telegram.error import TelegramError
from openai import OpenAI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import html
import json

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get credentials from environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')

# Validate environment variables
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN environment variable is required")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
if not GROUP_CHAT_ID:
    raise ValueError("GROUP_CHAT_ID environment variable is required")

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class TelegramGroupManager:
    def __init__(self):
        self.bot_username = None
        
    async def initialize_bot(self, application):
        """Get bot username"""
        try:
            bot_info = await application.bot.get_me()
            self.bot_username = bot_info.username
            logger.info(f"Bot initialized: @{self.bot_username}")
            
            # Set commands
            await self.set_bot_commands(application)
            
        except Exception as e:
            logger.error(f"Error initializing bot: {e}")

    async def set_bot_commands(self, application):
        """Set bot commands menu"""
        commands = [
            ("start", "Start the bot"),
            ("help", "Show help message"),
            ("news", "Get latest news"),
            ("rules", "Show group rules"),
        ]
        await application.bot.set_my_commands(commands)

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        try:
            await update.message.reply_text(
                "🤖 Hello! I'm your group management bot!\n\n"
                "I can help with:\n"
                "• 📰 Posting daily news\n"
                "• 🛡️ Monitoring group activity\n"
                "• 💬 Smart chat responses\n"
                "• 🚫 Spam protection\n\n"
                "Use /help to see all commands!"
            )
        except Exception as e:
            logger.error(f"Error in start_command: {e}")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = """
📋 **Available Commands:**

/start - Start the bot
/help - Show this help message
/news - Get latest news summary
/rules - Show group rules

🔧 **Auto Features:**
• Daily news at 9:00 AM
• Smart chat responses
• Spam protection
• Content moderation

Add me to your group and make me an admin for full functionality!
        """
        try:
            await update.message.reply_text(help_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in help_command: {e}")

    async def news_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /news command"""
        try:
            news_message = await update.message.reply_text("📰 Fetching latest news...")
            news = await self.get_news_summary()
            await news_message.edit_text(news if news else "❌ Could not fetch news at the moment.")
        except Exception as e:
            logger.error(f"Error in news_command: {e}")
            await update.message.reply_text("❌ Error fetching news.")

    async def rules_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /rules command"""
        rules_text = """
📜 **Group Rules:**

1. Be respectful to all members
2. No spam or self-promotion
3. No offensive content
4. Keep discussions relevant
5. Follow Telegram's ToS

Violations may result in warnings or removal.
        """
        try:
            await update.message.reply_text(rules_text, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error in rules_command: {e}")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle all incoming messages"""
        try:
            # Ignore messages from bots
            if update.message.from_user.is_bot:
                return

            message = update.message
            chat_id = str(message.chat_id)
            text = message.text or message.caption or ""

            # Only respond in the designated group
            if chat_id != GROUP_CHAT_ID:
                logger.info(f"Message from non-target chat: {chat_id}")
                return

            # Log the message
            user = message.from_user
            logger.info(f"Message from {user.first_name} (@{user.username}): {text}")

            # Check for spam/inappropriate content
            if await self.is_inappropriate_content(text):
                await self.handle_inappropriate_content(update, context)
                return

            # Check if bot should respond
            if await self.should_respond(update, text):
                response = await self.generate_ai_response(text, user.first_name)
                if response:
                    await message.reply_text(response)

        except Exception as e:
            logger.error(f"Error handling message: {e}")

    async def should_respond(self, update: Update, text: str) -> bool:
        """Determine if bot should respond to a message"""
        if not text or len(text.strip()) < 5:
            return False

        text_lower = text.lower()
        
        # Check if bot is mentioned
        if self.bot_username and f"@{self.bot_username}" in text_lower:
            return True

        # Check for questions
        question_indicators = ['?', 'what', 'how', 'why', 'when', 'where', 'who', 'tell me', 'explain', 'help with']
        if any(indicator in text_lower for indicator in question_indicators):
            return True

        # Check for greetings directed at bot
        greetings = ['hello bot', 'hi bot', 'hey bot', 'good morning bot', 'good evening bot']
        if any(greeting in text_lower for greeting in greetings):
            return True

        return False

    async def generate_ai_response(self, user_message: str, user_name: str) -> str:
        """Generate AI response using OpenAI"""
        try:
            prompt = f"""
            You are a helpful assistant in a Telegram group chat. 
            User: {user_name}
            Message: {user_message}
            
            Respond in a friendly, conversational tone. Keep responses concise (1-2 sentences max). 
            Be helpful and engaging. If you don't know something, say so politely.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You're a friendly and helpful group chat assistant. Keep responses short and natural."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=100,
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
            return None

    async def is_inappropriate_content(self, text: str) -> bool:
        """Check if message contains inappropriate content"""
        if not text:
            return False

        text_lower = text.lower()
        
        inappropriate_patterns = [
            'http://', 'https://', 'www.', '.com', 'buy now', 'click here',
            'free money', 'lottery', 'casino', 'make money fast', 'work from home',
            'earn $', 'get rich', 'bitcoin investment', 'crypto investment'
        ]
        
        return any(pattern in text_lower for pattern in inappropriate_patterns)

    async def handle_inappropriate_content(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inappropriate content"""
        try:
            message = update.message
            user = message.from_user
            
            # Delete the message
            await message.delete()
            
            # Send warning
            warning_msg = (
                f"⚠️ Warning @{user.username or user.first_name}!\n"
                "Please avoid posting promotional or spam content in this group."
            )
            await context.bot.send_message(
                chat_id=message.chat_id,
                text=warning_msg
            )
            
            logger.info(f"Deleted inappropriate message from user {user.id}")
            
        except Exception as e:
            logger.error(f"Error handling inappropriate content: {e}")

    async def post_daily_news(self, context: CallbackContext):
        """Post daily news to the group"""
        try:
            logger.info("Posting daily news...")
            news = await self.get_news_summary()
            if news:
                await context.bot.send_message(
                    chat_id=GROUP_CHAT_ID,
                    text=news,
                    parse_mode='Markdown'
                )
                logger.info("Daily news posted successfully")
            else:
                logger.error("Failed to generate news")
        except Exception as e:
            logger.error(f"Error posting daily news: {e}")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        try:
            logger.error(f"Exception while handling an update: {context.error}")
            
            # Log the update that caused the error
            if update:
                update_dict = update.to_dict() if update else {}
                logger.error(f"Update that caused error: {update_dict}")
        except Exception as e:
            logger.error(f"Error in error_handler: {e}")

def setup_scheduler(application):
    """Setup scheduled tasks"""
    scheduler = AsyncIOScheduler()
    
    # Schedule daily news at 9:00 AM
    scheduler.add_job(
        application.bot_data['group_manager'].post_daily_news,
        trigger=CronTrigger(hour=9, minute=0),
        args=[application],
        id='daily_news'
    )
    
    scheduler.start()
    return scheduler

async def main():
    """Start the bot"""
    try:
        logger.info("Starting bot...")
        
        # Create application
        application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .build()
        )

        # Initialize group manager
        group_manager = TelegramGroupManager()
        application.bot_data['group_manager'] = group_manager

        # Add handlers
        application.add_handler(CommandHandler("start", group_manager.start_command))
        application.add_handler(CommandHandler("help", group_manager.help_command))
        application.add_handler(CommandHandler("news", group_manager.news_command))
        application.add_handler(CommandHandler("rules", group_manager.rules_command))
        application.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, group_manager.handle_message))
        
        # Error handler
        application.add_error_handler(group_manager.error_handler)

        # Initialize bot
        await group_manager.initialize_bot(application)

        # Setup scheduler
        scheduler = setup_scheduler(application)
        logger.info("Scheduler started")

        # Start polling
        logger.info("Bot is now polling...")
        await application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    asyncio.run(main())
