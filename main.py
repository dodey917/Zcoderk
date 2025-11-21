import os
import logging
import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from openai import OpenAI

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get environment variables
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
GROUP_CHAT_ID = os.getenv('GROUP_CHAT_ID')

# Validate environment variables
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN is not set!")
    exit(1)
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY is not set!")
    exit(1)
if not GROUP_CHAT_ID:
    logger.error("GROUP_CHAT_ID is not set!")
    exit(1)

# Initialize OpenAI
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class TelegramBot:
    def __init__(self):
        self.bot_username = None
        self.last_news_post = None
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /start is issued."""
        await update.message.reply_text(
            '🤖 Hello! I am your group management bot!\n\n'
            'I can help with:\n'
            '• Monitoring group activity\n'
            '• Posting daily news\n'
            '• Answering questions\n'
            '• Keeping the group safe\n\n'
            'Add me to your group and make me an admin!'
        )
    
    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Send a message when the command /help is issued."""
        help_text = """
📋 Available commands:
/start - Start the bot
/help - Show this help message
/news - Get latest news

🔧 Features:
• Smart chat responses
• Spam protection
• Daily news updates
        """
        await update.message.reply_text(help_text)
    
    async def news(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Post news to the group."""
        try:
            news_text = await self.get_news_summary()
            if news_text:
                await update.message.reply_text(news_text, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Sorry, couldn't fetch news right now.")
        except Exception as e:
            logger.error(f"Error in news command: {e}")
            await update.message.reply_text("❌ Error fetching news.")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle incoming messages."""
        try:
            # Ignore messages from bots
            if update.message.from_user.is_bot:
                return
            
            message = update.message
            chat_id = str(message.chat_id)
            text = message.text or ""
            
            # Only process messages from the target group
            if chat_id != GROUP_CHAT_ID:
                logger.info(f"Message from non-target chat: {chat_id}")
                return
            
            # Check for spam
            if await self.is_spam(text):
                await self.handle_spam(update, context)
                return
            
            # Auto-post news at 9:00 AM
            await self.check_auto_news(context)
            
            # Check if we should respond
            if await self.should_respond(text):
                response = await self.generate_response(text, update.message.from_user.first_name)
                if response:
                    await update.message.reply_text(response)
                    
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    async def is_spam(self, text: str) -> bool:
        """Check if message contains spam."""
        if not text:
            return False
        
        spam_indicators = [
            'http://', 'https://', 'www.', '.com', 'buy now', 'click here',
            'free money', 'lottery', 'casino', 'make money fast', 'earn $',
            'get rich', 'bitcoin investment', 'crypto investment'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in spam_indicators)
    
    async def handle_spam(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle spam messages."""
        try:
            # Delete the spam message
            await update.message.delete()
            
            # Send warning
            user = update.message.from_user
            warning = f"⚠️ Warning @{user.username or user.first_name}! Please avoid spam messages."
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=warning
            )
            logger.info(f"Deleted spam from user {user.id}")
        except Exception as e:
            logger.error(f"Error handling spam: {e}")
    
    async def should_respond(self, text: str) -> bool:
        """Determine if bot should respond to message."""
        if not text or len(text.strip()) < 3:
            return False
        
        text_lower = text.lower()
        
        # Respond if bot is mentioned
        if self.bot_username and f"@{self.bot_username}" in text_lower:
            return True
        
        # Respond to questions
        question_words = ['?', 'what', 'how', 'why', 'when', 'where', 'who', 'tell me', 'explain']
        if any(word in text_lower for word in question_words):
            return True
        
        # Respond to greetings
        greetings = ['hello bot', 'hi bot', 'hey bot', 'good morning bot', 'good evening bot']
        if any(greeting in text_lower for greeting in greetings):
            return True
        
        return False
    
    async def generate_response(self, message: str, username: str) -> str:
        """Generate AI response using OpenAI."""
        try:
            prompt = f"""
            You are a helpful assistant in a Telegram group chat.
            User: {username}
            Message: {message}
            
            Respond in a friendly, conversational way. Keep it short (1-2 sentences).
            Be helpful and engaging. If you don't know something, say so politely.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a friendly group chat assistant. Keep responses natural and concise."},
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
        """Get news summary from OpenAI."""
        try:
            prompt = """
            Create a brief daily news summary with 3-5 interesting headlines from around the world.
            Include technology, science, world news, and interesting facts.
            Make it engaging and concise. Use emojis. Keep it under 400 characters.
            """
            
            response = openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a news reporter creating engaging daily summaries."},
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
    
    async def check_auto_news(self, context: ContextTypes.DEFAULT_TYPE):
        """Check if it's time to post auto news."""
        try:
            now = datetime.datetime.now()
            current_time = now.strftime("%H:%M")
            current_date = now.date()
            
            # Post news at 9:00 AM if not posted today
            if current_time == "09:00":
                if self.last_news_post != current_date:
                    news = await self.get_news_summary()
                    if news:
                        await context.bot.send_message(
                            chat_id=GROUP_CHAT_ID,
                            text=news,
                            parse_mode='Markdown'
                        )
                        self.last_news_post = current_date
                        logger.info("Auto-posted daily news")
        except Exception as e:
            logger.error(f"Error in auto news check: {e}")
    
    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors."""
        logger.error(f"Exception while handling an update: {context.error}")

def main():
    """Start the bot."""
    try:
        logger.info("Initializing bot...")
        
        # Create application - FIXED: Use create_application pattern
        application = (
            Application.builder()
            .token(TELEGRAM_BOT_TOKEN)
            .concurrent_updates(True)
            .build()
        )
        
        # Initialize bot instance
        bot = TelegramBot()
        
        # Add handlers
        application.add_handler(CommandHandler("start", bot.start))
        application.add_handler(CommandHandler("help", bot.help))
        application.add_handler(CommandHandler("news", bot.news))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
        
        # Error handler
        application.add_error_handler(bot.error_handler)
        
        # Start polling
        logger.info("Bot is starting polling...")
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=Update.ALL_TYPES
        )
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()
