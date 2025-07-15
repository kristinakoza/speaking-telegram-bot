from pathlib import Path
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, ConversationHandler, MessageHandler, filters
from database import *
import logging
import sqlite3

# States
GETTING_PAYMENT, CONFIRMING_DETAILS = range(2)
SUPPORT_CONTACT = 'If you have any questions, please message @goat_eto_koza'

# ------------------------
# Ensure folders exist
# ------------------------
Path("storage/screenshots").mkdir(parents=True, exist_ok=True)
Path("storage/voice").mkdir(parents=True, exist_ok=True)

# ------------------------
# Decorators
# ------------------------
def require_user(func):
    async def wrapper(update: Update, context, *args, **kwargs):
        user = get_user_by_telegram_id(update.effective_user.id)
        if not user:
            keyboard = [
                [InlineKeyboardButton("🏃‍♂️ Join", callback_data="participate")]
            ]
            if hasattr(update, 'message'):
                await update.message.reply_text(
                    "⚠️ Сначала зарегистрируйтесь.",
                    reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.callback_query.edit_message_text(
                    "⚠️ Сначала зарегистрируйтесь.",
                    reply_markup=InlineKeyboardMarkup(keyboard))
            return
        return await func(update, context, user, *args, **kwargs)
    return wrapper

def require_approved(func):
    async def wrapper(update: Update, context, user, *args, **kwargs):
        if not user['approved']:
            keyboard = [
                [InlineKeyboardButton("ℹ️ Поддержка", url="https://t.me/goat_eto_koza")]
            ]
            if hasattr(update, 'message'):
                await update.message.reply_text(
                    "⏳ Вы ещё не одобрены. Ждите подтверждения админа.",
                    reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.callback_query.edit_message_text(
                    "⏳ Вы ещё не одобрены. Ждите подтверждения админа.",
                    reply_markup=InlineKeyboardMarkup(keyboard))
            return
        return await func(update, context, user, *args, **kwargs)
    return wrapper

# ------------------------
# Helpers
# ------------------------

def screenshot_path(user_id, message_id):
    return f"storage/screenshots/{user_id}_{message_id}.jpg"

def voice_path(user_id, task_id, message_id):
    return f"storage/voice/{user_id}_{task_id}_{message_id}.ogg"
def format_user_status(user):
    """Format user information into a readable status message"""
    status_text = (
        f"👤 Пользователь:: @{user['username']}\n"
        f"✅ Одобрено:: {'Yes' if user['approved'] else 'No'}\n"
        f"📅 Дата вступления:: {user['joined_date'].strftime('%Y-%m-%d')}\n"
        f"📌 Текущее задание:: {user['current_task']}\n"
        f"🏁 Finished: {'Yes' if user['finished'] else 'No'}"
    )
    
    keyboard = []
    if user['approved']:
        if not user['finished']:
            keyboard.append([InlineKeyboardButton("📋 Мои задания", callback_data="show_my_tasks")])
            keyboard.append([InlineKeyboardButton("🎤 Current Task", callback_data="current_task")])
    
    return status_text, InlineKeyboardMarkup(keyboard) if keyboard else None

def handle_errors(func):
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            update = args[0] if args else None
            keyboard = [
                [InlineKeyboardButton("🆘 Contact Support", url="https://t.me/goat_eto_koza")]
            ]
            error_message = f"❌ Error: {str(e)}\n\n{SUPPORT_CONTACT}"
            if update and hasattr(update, 'message'):
                await update.message.reply_text(
                    error_message,
                    reply_markup=InlineKeyboardMarkup(keyboard))
            elif hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text(
                    error_message,
                    reply_markup=InlineKeyboardMarkup(keyboard))
            logging.error(f"Error in {func.__name__}: {str(e)}")
    return wrapper

# ------------------------
# User Start
# ------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user_by_telegram_id(update.effective_user.id)
    if not user:
        keyboard = [
            [InlineKeyboardButton("🏃‍♂️ Join", callback_data="participate"),
             InlineKeyboardButton("ℹ️ Learn More", callback_data="learn_more")]
        ]
        await update.message.reply_text(
            "🌟 Welcome to the Marathon Bot! Choose an option:\n\n"
            f"{SUPPORT_CONTACT}",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        if user['approved']:
            keyboard = [
                [InlineKeyboardButton("📋 My Tasks", callback_data="show_my_tasks"),
                 InlineKeyboardButton("🎤 Current Task", callback_data="current_task")],
                [InlineKeyboardButton("🏆 My Status", callback_data="my_status"),
                 InlineKeyboardButton("ℹ️ Help", callback_data="help")]
            ]
            
            await update.message.reply_text(
                "🏆 Main Menu - Speaking Marathon\n\n"
                "Choose an option below:",
                reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            keyboard = [
                [InlineKeyboardButton("ℹ️ Contact Support", url="https://t.me/goat_eto_koza")]
            ]
            await update.message.reply_text(
                "⌛ Your registration is pending approval\n\n"
                "We'll notify you when you're approved!",
                reply_markup=InlineKeyboardMarkup(keyboard))

async def show_user_status(update, user):
    text, keyboard = format_user_status(user)
    if hasattr(update, 'message') and update.message:
        await update.message.reply_text(text, reply_markup=keyboard)
    else:
        await update.edit_message_text(text, reply_markup=keyboard)

# ------------------------
# Buttons
# ------------------------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "participate":
            await handle_participate(query)
        elif query.data == "learn_more":
            await handle_learn_more(query)
        elif query.data == "after_learn_participate":
            await handle_participate(query)
        elif query.data == "after_learn_channel":
            await handle_channel_link(query)
        elif query.data == "show_my_tasks":
            await show_pending_tasks(update, context)
        elif query.data == "current_task":
            await handle_current_task(query, context)
        elif query.data == "my_status":
            await handle_my_status(query)
        elif query.data == "help":
            await handle_help(query)
        elif query.data == "start_menu":
            await handle_start_menu(query)
        elif query.data.startswith("select_task_"):
            await handle_task_selection(update, context)
        elif query.data.startswith("suggested_reply_"):
            await handle_suggested_reply(update, context)
    except Exception as e:
        await handle_error(update, context, e)

async def handle_participate(query):
    user = get_user_by_telegram_id(query.from_user.id)
    if not user:
        add_user(query.from_user.id, query.from_user.username)
    
    keyboard = [
        [InlineKeyboardButton("📞 Contact Admin", url="https://t.me/goat_eto_koza")],
        [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
    ]
    
    await query.edit_message_text(
        "🎉 To join the marathon:\n\n"
        "1. Contact @goat_eto_koza for payment\n"
        "2. Send your username with payment\n"
        "3. Wait for admin approval\n\n"
        "You'll get a notification when approved!",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_learn_more(query):
    keyboard = [
        [InlineKeyboardButton("📢 Join Channel", callback_data="after_learn_channel"),
         InlineKeyboardButton("🏃‍♂️ Join Now", callback_data="after_learn_participate")],
        [InlineKeyboardButton("🔙 Back", callback_data="start_menu")]
    ]
    await query.edit_message_text(
        "🏅 30-Day Speaking Challenge:\n"
        "• Daily voice tasks\n"
        "• Teacher feedback\n"
        "• Certificate on finish\n"
        "• $29 fee\n\nChoose an option:",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_channel_link(query):
    keyboard = [
        [InlineKeyboardButton("🔙 Back", callback_data="learn_more")]
    ]
    await query.edit_message_text(
        "📢 Join our channel:\n👉 https://t.me/your_channel_link",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_current_task(query, context):
    await query.answer()
    user = get_user_by_telegram_id(query.from_user.id)
    if not user:
        await query.edit_message_text("User not found. Please /start first.")
        return
    
    # get current task
    current_task = get_task_by_day(user['current_task'])
    if not current_task:
        await query.edit_message_text("No current task assigned yet.")
        return
    
    conn = sqlite3.connect('marathon_bot.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM submissions 
        WHERE user_id = ? AND task_id = ? AND checked = ?
    """, (user['id'], current_task['id'], SUBMISSION_APPROVED))
    already_completed = cursor.fetchone() is not None
    conn.close()
    
    if already_completed:
        pending_tasks = get_pending_tasks(user['id'])
        if pending_tasks:
            next_task = pending_tasks[0]
            update_user(user['id'], {'current_task': next_task['day']})
            current_task = get_task_by_day(next_task['day'])
        else:
            await query.edit_message_text(
                "🎉 You've completed all available tasks!\n\n"
                "Use /get_certificate to claim your reward."
            )
            return
    
    keyboard = [
        [InlineKeyboardButton("👍 I'll do it now", callback_data=f"suggested_reply_confirm_{current_task['day_number']}")],
        [InlineKeyboardButton("🕒 I'll do it later", callback_data=f"suggested_reply_later_{current_task['day_number']}")],
        [InlineKeyboardButton("❓ Need clarification", callback_data=f"suggested_reply_question_{current_task['day_number']}")],
        [InlineKeyboardButton("ℹ️ How to submit", callback_data="help_submit_voice")],
        [InlineKeyboardButton("📋 My Tasks", callback_data="show_my_tasks")]
    ]
    
    await query.edit_message_text(
        f"📝 Task Day {current_task['day_number']}:\n\n{current_task['task_text']}\n\n"
        "How would you like to respond?",
        reply_markup=InlineKeyboardMarkup(keyboard))

    
async def handle_suggested_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    action = parts[2]
    day_number = int(parts[3]) 
    
    task = get_task_by_day(day_number)
    if not task:
        await query.edit_message_text("Task not found.")
        return
    
    if action == "confirm":
        response = "✅ I'll complete this task right away!"
    elif action == "later":
        response = "⏳ I'll come back to this task later today."
    elif action == "question":
        response = "❓ I have a question about this task."
    else:
        response = "🤔 I'm working on this task."
    
    keyboard = [
        [InlineKeyboardButton("ℹ️ How to submit", callback_data="help_submit_voice")],
        [InlineKeyboardButton("📋 My Tasks", callback_data="show_my_tasks")]
    ]
    
    await query.edit_message_text(
        f"📝 Task Day {task['day_number']}:\n\n{task['task_text']}\n\n"
        f"Your response: {response}",
        reply_markup=InlineKeyboardMarkup(keyboard))
    
    admin_ids = [1093135523]  
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🗣️ User @{query.from_user.username} responded to task {task['day_number']}:\n{response}"
            )
        except Exception as e:
            print(f"⚠️ Failed to notify admin: {e}")

async def handle_my_status(query):
    await query.answer()
    user = get_user_by_telegram_id(query.from_user.id)
    if not user:
        await query.edit_message_text("User not found. Please /start first.")
        return
    text, keyboard = format_user_status(user)
    await query.edit_message_text(text, reply_markup=keyboard)

async def handle_help(query):
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("📞 Contact Support", url="https://t.me/goat_eto_koza")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]
    ]
    await query.edit_message_text(
        "🆘 Help Center\n\n"
        "Here's what you can do:\n"
        "• Use buttons to navigate\n"
        "• Send voice messages for tasks\n"
        "• Contact support if stuck\n\n"
        f"{SUPPORT_CONTACT}",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_start_menu(query):
    await query.answer()
    user = get_user_by_telegram_id(query.from_user.id)
    if not user:
        return
    
    if user['approved']:
        keyboard = [
            [InlineKeyboardButton("📋 My Tasks", callback_data="show_my_tasks"),
             InlineKeyboardButton("🎤 Current Task", callback_data="current_task")],
            [InlineKeyboardButton("🏆 My Status", callback_data="my_status"),
             InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ]
        await query.edit_message_text(
            "🏆 Main Menu - Speaking Marathon\n\n"
            "Choose an option below:",
            reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        keyboard = [
            [InlineKeyboardButton("ℹ️ Contact Support", url="https://t.me/goat_eto_koza")]
        ]
        await query.edit_message_text(
            "⌛ Your registration is pending approval\n\n"
            "We'll notify you when you're approved!",
            reply_markup=InlineKeyboardMarkup(keyboard))

# ------------------------
# Task Management
# ------------------------

@require_user
async def my_status(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    await show_user_status(update, user)

@require_user
@require_approved
@handle_errors
async def submit_voice(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    if not update.message.voice:
        keyboard = [
            [InlineKeyboardButton("📋 My Tasks", callback_data="show_my_tasks")]
        ]
        await update.message.reply_text(
            "❗ Please send a voice message.",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    current_task = get_task_by_day(user['current_task'])
    if not current_task:
        keyboard = [
            [InlineKeyboardButton("📋 My Tasks", callback_data="show_my_tasks")]
        ]
        await update.message.reply_text(
            "❗ No active task found.",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    # Generate a unique filename
    voice_filename = f"voice_{user['id']}_{current_task['id']}_{update.message.id}.ogg"
    voice_filepath = f"storage/voice/{voice_filename}"

    # Ensure directory exists
    Path("storage/voice").mkdir(parents=True, exist_ok=True)

    try:
        # Download the voice file
        voice_file = await update.message.voice.get_file()
        await voice_file.download_to_drive(custom_path=voice_filepath)
        print(f"✅ Saved voice to: {voice_filepath}")
    except Exception as e:
        keyboard = [
            [InlineKeyboardButton("🔄 Try Again", switch_inline_query_current_chat=""),
             InlineKeyboardButton("📋 My Tasks", callback_data="show_my_tasks")]
        ]
        await update.message.reply_text(
            "❌ Failed to save voice. Please try again.",
            reply_markup=InlineKeyboardMarkup(keyboard))
        return

    submission_id = add_submission(
        user_id=user['id'],
        task_id=current_task['id'],
        voice_file_path=voice_filename,
        checked=SUBMISSION_PENDING 
    )

    # Notify admin
    admin_ids = [1093135523]
    for admin_id in admin_ids:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"🎤 New submission from @{user['username']}\n"
                     f"Task: Day {current_task['day_number']}\n"
                     f"File: {voice_filename}"
            )
            await context.bot.send_voice(
                chat_id=admin_id,
                voice=update.message.voice.file_id,
                caption=f"From @{user['username']}"
            )
        except Exception as e:
            print(f"⚠️ Failed to notify admin: {e}")

    keyboard = [
        [InlineKeyboardButton("📋 My Tasks", callback_data="show_my_tasks")]
    ]
    await update.message.reply_text(
        "🎤 Voice submission received!",
        reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_help_submit_voice(query):
    await query.answer()
    await query.edit_message_text(
        "🎤 To submit your task, please record a voice message right here in the chat. "
        "Your teacher will review it and give feedback!"
    )
  
async def show_pending_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display incomplete tasks with selection buttons"""
    try:
        query = update.callback_query if hasattr(update, 'callback_query') else None
        user_id = query.from_user.id if query else update.effective_user.id

        user = get_user_by_telegram_id(user_id)
        if not user:
            await show_not_registered_message(update, context, query)
            return

        pending_tasks = get_pending_tasks(user['id'])
        
        if not pending_tasks:
            # Check if user has actually completed all tasks
            all_tasks = get_all_tasks()
            completed_tasks = len(get_user_submissions(user['id'], SUBMISSION_APPROVED))
            
            if completed_tasks >= len(all_tasks):
                # User has completed all tasks
                keyboard = [
                    [InlineKeyboardButton("🏆 My Status", callback_data="my_status")]
                ]
                message = "🎉 🎉 You've completed all tasks! An admin will review your submissions soon. Or the task will be sent to you soon, as well!"
            else:
                # User has some tasks but they're all pending review
                keyboard = [
                    [InlineKeyboardButton("🔄 Refresh", callback_data="show_my_tasks")],
                    [InlineKeyboardButton("🏆 My Status", callback_data="my_status")]
                ]
                message = "📝 All your submissions are pending review. Please wait for feedback."
            
            if query:
                await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
            else:
                await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = [
            [InlineKeyboardButton(
                f"Day {task['day']}: {task['text'][:20]}...", 
                callback_data=f"select_task_{task['day']}")]
            for task in pending_tasks
        ]
        keyboard.append([InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")])

        reply_text = "📋 Your pending tasks:\nChoose which one to work on:"
        
        if query:
            await query.edit_message_text(reply_text, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            await update.message.reply_text(reply_text, reply_markup=InlineKeyboardMarkup(keyboard))

    except Exception as e:
        print(f"Error in show_pending_tasks: {e}")
        await handle_error(update, context, e)

async def show_not_registered_message(update, context, query=None):
    keyboard = [[InlineKeyboardButton("🏃‍♂️ Join", callback_data="participate")]]
    message = "⚠️ Сначала зарегистрируйтесь."
    if query:
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.message:
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await send_fallback_message(update, context, message, keyboard)

async def show_no_pending_tasks_message(update, context, query=None):
    keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="start_menu")]]
    message = "🎉 You have no pending tasks!"
    if query:
        await query.edit_message_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    elif update.message:
        await update.message.reply_text(message, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await send_fallback_message(update, context, message, keyboard)

async def handle_error(update, context, error):
    keyboard = [[InlineKeyboardButton("🆘 Contact Support", url="https://t.me/goat_eto_koza")]]
    error_msg = f"❌ Error: {str(error)}\n\n{SUPPORT_CONTACT}"
    
    if hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text(error_msg, reply_markup=InlineKeyboardMarkup(keyboard))
    elif hasattr(update, 'message') and update.message:
        await update.message.reply_text(error_msg, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await send_fallback_message(update, context, error_msg, keyboard)

async def send_fallback_message(update, context, text, keyboard):
    """Fallback method to send messages when no message object is available"""
    if update.effective_chat:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        user_id = update.callback_query.from_user.id if hasattr(update, 'callback_query') else update.effective_user.id
        await context.bot.send_message(
            chat_id=user_id,
            text=text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

async def handle_task_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set selected task as current focus"""
    query = update.callback_query
    await query.answer()
    
    day_number = int(query.data.split('_')[-1]) 
    user = get_user_by_telegram_id(query.from_user.id)
    
    # Update user's current task 
    update_user(user['id'], {'current_task': day_number})
    
    # Get the task details
    task = get_task_by_day(day_number)
    if not task:
        await query.edit_message_text("Task not found.")
        return
    
    # Create suggested reply buttons
    keyboard = [
        [InlineKeyboardButton("👍 I'll do it now", callback_data=f"suggested_reply_confirm_{day_number}")],
        [InlineKeyboardButton("🕒 I'll do it later", callback_data=f"suggested_reply_later_{day_number}")],
        [InlineKeyboardButton("❓ Need clarification", callback_data=f"suggested_reply_question_{day_number}")],
        [InlineKeyboardButton("ℹ️ How to submit", callback_data="help_submit_voice")],
        [InlineKeyboardButton("📋 My Tasks", callback_data="show_my_tasks")]
    ]
    
    await query.edit_message_text(
        f"📝 Task Day {day_number}:\n\n{task['task_text']}\n\n"
        "How would you like to respond?",
        reply_markup=InlineKeyboardMarkup(keyboard))

# ------------------------
#  Finish & Certificate
# ------------------------
@require_user
async def finish(update: Update, context: ContextTypes.DEFAULT_TYPE, user):
    update_user(user['id'], {'finished': True})
    await update.message.reply_text(
        "🎉 Congratulations on completing the marathon!\n"
        "An admin will review your submissions and send your certificate soon."
    )

# ------------------------
#  Register all
# ------------------------
def get_user_handlers():
    return [
        CommandHandler("start", start),
        CallbackQueryHandler(button_handler),
        CommandHandler("submit_voice", submit_voice),
        CommandHandler("my_status", my_status),
        MessageHandler(filters.VOICE, submit_voice),
        CommandHandler("finish", finish),
    ]