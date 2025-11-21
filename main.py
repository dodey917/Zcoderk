import os
import logging
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

# Validate environment variables
if not TELEGRAM_BOT_TOKEN:
    logger.error("TELEGRAM_BOT_TOKEN is not set!")
    exit(1)
if not OPENAI_API_KEY:
    logger.error("OPENAI_API_KEY is not set!")
    exit(1)

# Initialize bot and OpenAI
bot = TeleBot(TELEGRAM_BOT_TOKEN)
openai_client = OpenAI(api_key=OPENAI_API_KEY)

def generate_ai_response(user_message, username):
    """Generate AI response using OpenAI"""
    try:
        prompt = f"""
        You are a helpful assistant in a Telegram chat.
        User: {username}
        Message: {user_message}
        
        Respond in a friendly, conversational way. Keep it short and engaging.
        """
        
        response = openai_client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a friendly and helpful chat assistant."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=150,
            temperature=0.7
        )
        
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        logger.error(f"Error generating AI response: {e}")
        return "Sorry, I'm having trouble responding right now."

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    """Handle /start and /help commands"""
    welcome_text = """
🤖 Hello! I'm your AI chatbot!

I can:
• Chat with you naturally
• Answer questions
• Have conversations

Just send me a message and I'll respond!
    """
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['chat'])
def start_chat(message):
    """Start a chat conversation"""
    bot.reply_to(message, "Let's chat! Send me any message and I'll respond naturally. 😊")

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    """Handle all text messages"""
    try:
        # Don't respond to other bots
        if message.from_user.is_bot:
            return
        
        # Get message text
        text = message.text or ""
        
        # Ignore very short messages or commands
        if len(text.strip()) < 2 or text.startswith('/'):
            return
        
        # Generate AI response
        username = message.from_user.first_name
        response = generate_ai_response(text, username)
        
        # Send response
        if response:
            bot.reply_to(message, response)
            logger.info(f"Responded to {username}: {text[:50]}...")
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        bot.reply_to(message, "Sorry, I encountered an error. Please try again.")

def main():
    """Start the bot"""
    try:
        logger.info("Starting AI Chat Bot...")
        
        # Get bot info
        bot_info = bot.get_me()
        logger.info(f"Bot started successfully: @{bot_info.username}")
        
        # Start polling
        logger.info("Bot is now listening for messages...")
        bot.infinity_polling()
        
    except Exception as e:
        logger.error(f"Failed to start bot: {e}")
        raise

if __name__ == '__main__':
    main()
