import os
from telegram import Update
from dotenv import load_dotenv
from main import send_message
from models import Session, Message, User, Request 
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")


# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! I'm your assistant for the BlueChip Data & AI Event! 🤖")

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Send me any message and I will echo it!")

# Echo messages
async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE):

    user = update.effective_user
    user_id = str(user.id)
    username = user.username
    first_name = user.first_name
    user_text = update.message.text 
    user_text = str(user_text)

    request_data = Request(phone_number=user_id, message=user_text)

    response = await send_message(request_data)

    await update.message.reply_text(f"{response}")

# Main app
# app = ApplicationBuilder().token(TOKEN).build()


app = ApplicationBuilder().token(TOKEN)\
            .connect_timeout(30)\
            .read_timeout(30)\
            .write_timeout(30)\
            .build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

print("Bot is running...")
app.run_polling()







# from telegram import Update
# from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# TOKEN = "YOUR_BOT_TOKEN"

# async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
#     await update.message.reply_text("Hello! I'm your bot.")

# app = ApplicationBuilder().token(TOKEN).build()
# app.add_handler(CommandHandler("start", start))

# app.run_polling()