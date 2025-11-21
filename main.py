import os
import logging
import threading
import time
import schedule
from telebot import TeleBot
from telebot.types import Message
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

# Initialize bot and OpenAI
bot = TeleBot(TELEGRAM_BOT_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

class TelegramBot:
    def __init__(self):
        self.last_news_post = None
    
    def start_command(self, message: Message):
        """Handle /start command"""
        bot.reply_to(
            message,
            '🤖 Hello! I am your group management bot!\n\n'
            'I can help with:\n'
            '• Monitoring group activity\n'
            '• Posting daily news\n'
            '• Answering questions\n'
            '• Keeping the group safe\n\n'
            'Add me to your group and make me an admin!'
        )
    
    def help_command(self, message: Message):
        """Handle /help command"""
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
        bot.reply_to(message, help_text)
    
    def news_command(self, message: Message):
        """Handle /news command"""
        try:
            news_text = self.get_news_summary()
            if news_text:
                bot.reply_to(message, news_text, parse_mode='Markdown')
            else:
                bot.reply_to(message, "❌ Sorry, couldn't fetch news right now.")
        except Exception as e:
            logger.error(f"Error in news command: {e}")
            bot.reply_to(message, "❌ Error fetching news.")
    
    def handle_message(self, message: Message):
        """Handle all incoming messages"""
        try:
            # Ignore messages from bots
            if message.from_user.is_bot:
                return
            
            chat_id = str(message.chat.id)
            text = message.text or ""
            
            # Only process messages from the target group
            if chat_id != GROUP_CHAT_ID:
                logger.info(f"Message from non-target chat: {chat_id}")
                return
            
            # Check for spam
            if self.is_spam(text):
                self.handle_spam(message)
                return
            
            # Check if we should respond
            if self.should_respond(text, message):
                response = self.generate_response(text, message.from_user.first_name)
                if response:
                    bot.reply_to(message, response)
                    
        except Exception as e:
            logger.error(f"Error handling message: {e}")
    
    def is_spam(self, text: str) -> bool:
        """Check if message contains spam"""
        if not text:
            return False
        
        spam_indicators = [
            'http://', 'https://', 'www.', '.com', 'buy now', 'click here',
            'free money', 'lottery', 'casino', 'make money fast', 'earn $',
            'get rich', 'bitcoin investment', 'crypto investment'
        ]
        
        text_lower = text.lower()
        return any(indicator in text_lower for indicator in spam_indicators)
    
    def handle_spam(self, message: Message):
        """Handle spam messages"""
        try:
            # Delete the spam message
            bot.delete_message(message.chat.id, message.message_id)
            
            # Send warning
            user = message.from_user
            warning = f"⚠️ Warning @{user.username or user.first_name}! Please avoid spam messages."
            bot.send_message(message.chat.id, warning)
            logger.info(f"Deleted spam from user {user.id}")
        except Exception as e:
            logger.error(f"Error handling spam: {e}")
    
    def should_respond(self, text: str, message: Message) -> bool:
        """Determine if bot should respond to message"""
        if not text or len(text.strip()) < 3:
            return False
        
        text_lower = text.lower()
        
        # Respond if bot is mentioned
        bot_user = bot.get_me()
        if bot_user.username and f"@{bot_user.username}" in text_lower:
            return True
        
        # Respond to questions
        question_words = ['?', 'what', 'how', 'why', 'when', 'where', 'who', 'tell me', 'explain']
        if any(word in text_lower for word in question_words):
            return True
        
        # Respond to greetings directed at bot
        greetings = ['hello bot', 'hi bot', 'hey bot', 'good morning bot', 'good evening bot']
        if any(greeting in text_lower for greeting in greetings):
            return True
        
        # Check if message is a reply to bot
        if message.reply_to_message and message.reply_to_message.from_user.id == bot_user.id:
            return True
        
        return False
    
    def generate_response(self, user_message: str, username: str) -> str:
        """Generate AI response using OpenAI"""
        try:
            prompt = f"""
            You are a helpful assistant in a Telegram group chat.
            User: {username}
            Message: {user_message}
            
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
    
    def get_news_summary(self) -> str:
        """Get news summary from OpenAI"""
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
    
    def post_daily_news(self):
        """Post daily news to the group"""
        try:
            logger.info("Posting daily news...")
            news = self.get_news_summary()
            if news:
                bot.send_message(GROUP_CHAT_ID, news, parse_mode='Markdown')
                logger.info("Daily news posted successfully")
        except Exception as e:
            logger.error(f"Error posting daily news: {e}")

# Initialize bot instance
telegram_bot = TelegramBot()

# Register handlers
@bot.message_handler(commands=['start'])
def handle_start(message):
    telegram_bot.start_command(message)

@bot.message_handler(commands=['help'])
def handle_help(message):
    telegram_bot.help_command(message)

@bot.message_handler(commands=['news'])
def handle_news(message):
    telegram_bot.news_command(message)

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    telegram_bot.handle_message(message)

def run_scheduler():
    """Run the scheduler for daily tasks"""
    # Schedule daily news at 9:00 AM
    schedule.every().day.at("09:00").do(telegram_bot.post_daily_news)
    
    while True:
        schedule.run_pending()
        time.sleep(60)

def main():
    """Start the bot"""
    try:
        logger.info("Initializing bot...")
        
        # Start scheduler in a separate thread
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("Scheduler started")
        
        # Get bot info
        bot_info = bot.get_me()
        logger.info(f"Bot username: @{bot_info.username}")
        
        # Start polling
        logger.info("Bot is starting polling...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()
