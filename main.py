import os
import logging
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import openai

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Get tokens from environment
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
OPENAI_KEY = os.getenv('OPENAI_API_KEY')

# Set OpenAI key
openai.api_key = OPENAI_KEY

def start(update: Update, context: CallbackContext):
    update.message.reply_text('Hello! I am a simple AI chatbot. Send me any message!')

def chat(update: Update, context: CallbackContext):
    try:
        user_message = update.message.text
        
        # Get AI response
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": user_message}
            ],
            max_tokens=150
        )
        
        bot_reply = response.choices[0].message.content
        update.message.reply_text(bot_reply)
        
    except Exception as e:
        update.message.reply_text("Sorry, I'm having trouble responding.")
        logger.error(f"Error: {e}")

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, chat))

    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
