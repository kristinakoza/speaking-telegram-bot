from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler
from database import *
import logging
import sqlite3


ADMIN_IDS = [#secret]  # admin ID


FEEDBACK, APPROVE_FEEDBACK, REJECT_FEEDBACK, REDO_FEEDBACK = range(4)

def is_admin(update):
    return update.effective_user.id in ADMIN_IDS

async def dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    users = get_all_users()
    tasks = get_all_tasks()
    submissions = get_all_submissions()

    total_users = len(users)
    approved_users = sum(1 for u in users if u['approved'])
    pending_users = total_users - approved_users

    pending_subs = sum(1 for s in submissions if s['status'] == SUBMISSION_PENDING)
    approved_subs = sum(1 for s in submissions if s['status'] == SUBMISSION_APPROVED)
    rejected_subs = sum(1 for s in submissions if s['status'] == SUBMISSION_REJECTED)
    redo_subs = sum(1 for s in submissions if s['status'] == SUBMISSION_NEEDS_REDO)

    text = (
        "📊 <b>Admin Dashboard</b>\n\n"
        f"👥 Users: {total_users} (✅ {approved_users}, ⏳ {pending_users})\n"
        f"📝 Tasks: {len(tasks)}\n"
        f"🎤 Submissions: {len(submissions)}\n"
        f"  - ✅ Approved: {approved_subs}\n"
        f"  - ❌ Rejected: {rejected_subs}\n"
        f"  - ⏳ Pending: {pending_subs}\n"
        f"  - 🟠 Needs Redo: {redo_subs}\n\n"
        "Use buttons below to browse."
    )
    
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("👥 View Users", callback_data="view_users_0")],
        [InlineKeyboardButton("📝 View Tasks", callback_data="view_tasks_0")],
        [InlineKeyboardButton("🎤 View Submissions", callback_data="view_subs_0")],
    ])
    logging.info(f"Dashboard buttons created with callback_data: {buttons.to_dict()}")
    await update.message.reply_text(text, reply_markup=buttons, parse_mode="HTML")

def pagination_buttons(prefix, page, total_items, per_page=5):
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⏪ Prev", callback_data=f"{prefix}_{page - 1}"))
    if (page + 1) * per_page < total_items:
        buttons.append(InlineKeyboardButton("Next ⏩", callback_data=f"{prefix}_{page + 1}"))
    return InlineKeyboardMarkup([buttons]) if buttons else None
async def view_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = int(query.data.split("_")[-1])
    users = get_all_users()
    per_page = 5

    start = page * per_page
    end = start + per_page
    total_pages = (len(users) - 1) // per_page + 1

    message = f"👥 <b>Users (Page {page + 1}/{total_pages})</b>\n\n"
    for user in users[start:end]:
        message += (
            f"🆔 {user['id']} | @{user['username']} | "
            f"{'✅' if user['approved'] else '⏳'} | "
            f"📌 Task: {user['current_task']}\n"
        )

    await query.edit_message_text(
        message,
        parse_mode="HTML",
        reply_markup=pagination_buttons("view_users", page, len(users), per_page)
    )
async def view_tasks_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = int(query.data.split("_")[-1])
    tasks = get_all_tasks()
    per_page = 5

    start = page * per_page
    end = start + per_page
    total_pages = (len(tasks) - 1) // per_page + 1

    message = f"📝 <b>Tasks (Page {page + 1}/{total_pages})</b>\n\n"
    for task in tasks[start:end]:
        message += f"📅 Day {task['day_number']}: {task['task_text']}\n"

    await query.edit_message_text(
        message,
        parse_mode="HTML",
        reply_markup=pagination_buttons("view_tasks", page, len(tasks), per_page)
    )

async def view_subs_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    page = int(query.data.split("_")[-1])
    submissions = get_all_submissions()
    per_page = 5

    start = page * per_page
    end = start + per_page
    total_pages = (len(submissions) - 1) // per_page + 1

    status_map = {
        0: "🟡 Pending",
        1: "✅ Approved",
        2: "❌ Rejected",
        3: "🟠 Needs Redo"
    }
    message = f"🎤 <b>Submissions (Page {page + 1}/{total_pages})</b>\n\n"
    for s in submissions[start:end]:
        user = get_user_by_id(s['user_id'])
        username = user['username'] if user else "Unknown"
        message += (
            f"🆔 {s['id']} | 👤 @{username} | 📅 Day {s['task_id']} | {status_map.get(s['status'], '❓')}\n"
        )

    message = f"🎤 <b>Submissions (Page {page + 1}/{total_pages})</b>\n\n"
    for s in submissions[start:end]:
        user = get_user_by_id(s['user_id'])
        username = user['username'] if user else "Unknown"
        message += (
            f"🆔 {s['id']} | 👤 @{username} | 📅 Day {s['task_id']} | {status_map.get(s['status'], '❓')}\n"
        )

    await query.edit_message_text(
        message,
        parse_mode="HTML",
        reply_markup=pagination_buttons("view_subs", page, len(submissions), per_page)
    )

async def admin_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
   #ITS NOT FULL ILL UPDATE IT LATER I PROMISE!  
    help_text = (
        "<b>🛠️ Admin Commands</b>\n\n"
        "<b>👥 User Management</b>\n"
        "/approve &lt;id&gt; - Approve a user\n"
        "/unapproved - List pending approvals\n"
        "/remove_user &lt;id&gt; - Remove a user\n"
        "/all_users - List all users\n\n"
        "<b>📝 Task Management</b>\n"
        "/add_task &lt;day&gt; &lt;text&gt; - Create new task\n"
        "/send_task &lt;user_id&gt; &lt;day&gt; - Send task to user\n\n"
        "/remove_task &lt;day&gt; - Remove task\n"
        "/all_tasks - List all tasks\n\n"
        "<b>🎤 Submissions</b>\n"
        "/all_submissions - View all voice submissions\n"
        "/review &lt;submission_id&gt; - Review a submission"
    )
    
    await update.message.reply_text(help_text, parse_mode='HTML')

async def approve_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if not context.args:
        await update.message.reply_text("Usage: /approve <user_id>")
        return

    try:
        user_id = int(context.args[0])
        user = get_user_by_id(user_id)
        
        if not user:
            await update.message.reply_text(f"❌ User ID {user_id} not found")
            return
            
        if user['approved']:
            await update.message.reply_text(f"ℹ️ User @{user['username']} is already approved")
            return
            
        # only the approved status
        update_user(user_id, {'approved': True})
        
        # notify admin
        await update.message.reply_text(
            f"✅ Approved user:\n"
            f"ID: {user_id}\n"
            f"Username: @{user['username']}\n"
            f"Joined: {user['joined_date'].strftime('%Y-%m-%d')}"
        )
        
        # notify user
        try:
            await context.bot.send_message(
                chat_id=user['telegram_id'],
                text="🎉 Your account has been approved!\n\n"
                     "You can now access all marathon features with /start"
            )
        except Exception as e:
            logging.error(f"Failed to notify user: {e}")
            await update.message.reply_text("⚠️ Approved but couldn't notify user")
            
    except ValueError:
        await update.message.reply_text("❌ User ID must be a number")

async def list_unapproved_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return
    
    users = [u for u in get_all_users() if not u['approved']]
    
    if not users:
        await update.message.reply_text("🌟 All users are approved!")
        return
    
    response = "🔄 Pending Approvals:\n\n"
    for user in users:
        response += (
            f"🆔 {user['id']} - @{user['username']}\n"
            f"📅 Joined: {user['joined_date'].strftime('%Y-%m-%d')}\n"
            f"────────────────────\n"
        )
    
    await update.message.reply_text(response)

async def all_submissions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return

    conn = None
    try:
        conn = sqlite3.connect('marathon_bot.db')
        cursor = conn.cursor()

        
        cursor.execute("""
            SELECT s.id, u.username, t.day_number, s.checked, s.voice_file_path
            FROM submissions s
            JOIN users u ON s.user_id = u.id
            JOIN tasks t ON s.task_id = t.id
            ORDER BY s.id DESC
        """)

        submissions = cursor.fetchall()

        if not submissions:
            await update.message.reply_text("No submissions yet.")
            return

        response = "📝 All Submissions:\n\n"
        for sub in submissions:
            status_map = {
                0: "🟡 Pending",
                1: "✅ Approved", 
                2: "❌ Rejected",
                3: "🟠 Needs Redo"
            }
            status = status_map.get(sub[3], "❓ Unknown")
            
            response += (
                f"🆔 {sub[0]} | 👤 @{sub[1]} | 📅 Day {sub[2]} | {status}\n"
                f"🔗 Path: {sub[4]}\n"
                f"────────────────────\n"
            )

        await update.message.reply_text(response)
    except Exception as e:
        logging.error(f"Error fetching submissions: {e}")
        await update.message.reply_text("❌ Failed to fetch submissions")
    finally:
        if conn:
            conn.close()

async def add_task_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /add_task <day_number> <task_text>\n\n"
            "Example: /add_task 1 \"Send a voice introduction\""
        )
        return

    try:
        day_number = int(context.args[0])
        task_text = " ".join(context.args[1:])
        
        # check if task exists
        if get_task_by_day(day_number):
            await update.message.reply_text(f"❌ Task for day {day_number} already exists")
            return
            
        # add to database
        task_id = add_task(day_number, task_text)
        
        await update.message.reply_text(
        f"✅ Task added successfully!\n"
        f"Day: {day_number}\n"
        f"ID: {task_id}\n"
        f"Task: {task_text}"  
        )
        
    except ValueError:
        await update.message.reply_text("❌ Day number must be an integer")
    except Exception as e:
        logging.error(f"Error adding task: {e}")
        await update.message.reply_text("❌ Failed to add task - check logs")

async def remove_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if not context.args:
        await update.message.reply_text(
            "Usage: /remove_task <day_number>\n\n"
            "Example: /remove_task 3 - removes task for day 3\n"
            "Use /all_tasks to see existing tasks"
        )
        return

    try:
        day_number = int(context.args[0])
        task = get_task_by_day(day_number)
        
        if not task:
            await update.message.reply_text(f"❌ No task found for day {day_number}")
            return
            
        conn = None
        try:
            conn = sqlite3.connect('marathon_bot.db')
            cursor = conn.cursor()
            
            
            cursor.execute("DELETE FROM submissions WHERE task_id = ?", (task['id'],))
            deleted_submissions = cursor.rowcount
            
            
            cursor.execute("DELETE FROM tasks WHERE day_number = ?", (day_number,))
            conn.commit()
            
            await update.message.reply_text(
                f"✅ Task removed successfully!\n"
                f"Day: {day_number}\n"
                f"Task: {task['task_text']}\n"
                f"Also deleted {deleted_submissions} submissions"
            )
        finally:
            if conn:
                conn.close()
        
    except ValueError:
        await update.message.reply_text("❌ Day number must be an integer")
    except Exception as e:
        logging.error(f"Error removing task: {e}")
        await update.message.reply_text("❌ Failed to remove task - check logs")

async def all_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    tasks = get_all_tasks()
    
    if not tasks:
        await update.message.reply_text("No tasks in database")
        return

    response = "📝 All Tasks:\n\n"
    for task in tasks:
        response += f"Day {task['day_number']}: {task['task_text']}\n"
    
    response += "\nUse /remove_task <day> to delete a task"
    
    await update.message.reply_text(response)

async def send_task(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage: /send_task <user_id> <day_number>\n\n"
            "Example: /send_task 5 3 - sends day 3 task to user with ID 5"
        )
        return

    try:
        user_id = int(context.args[0])
        day_number = int(context.args[1])
    except ValueError:
        await update.message.reply_text("❌ Both arguments must be numbers")
        return

    # get user and task
    user = get_user_by_id(user_id)
    task = get_task_by_day(day_number)

    if not user:
        await update.message.reply_text(f"❌ User with ID {user_id} not found")
        return
    if not task:
        await update.message.reply_text(f"❌ Task for day {day_number} not found")
        return

    update_user(user_id, {'current_task': day_number})

    # send task to user
    try:
        await context.bot.send_message(
            chat_id=user['telegram_id'],
            text=f"📣 Admin sent you task {day_number}:\n\n{task['task_text']}"
        )
        await update.message.reply_text(
            f"✅ Task {day_number} sent to @{user['username']} (ID: {user_id})"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Failed to send task to user: {str(e)}\n"
            f"User may have blocked the bot or left."
        )

def update_submission(submission_id: int, updates: dict):
    """Update submission fields"""
    conn = None
    try:
        conn = sqlite3.connect('marathon_bot.db')
        cursor = conn.cursor()
        
        set_clause = ", ".join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values())
        values.append(submission_id)
        
        cursor.execute(
            f"UPDATE submissions SET {set_clause} WHERE id = ?",
            values
        )
        
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logging.error(f"Error updating submission: {e}")
        return False
    finally:
        if conn:
            conn.close()

async def start_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return ConversationHandler.END
    
    context.user_data.clear()
    
    if not context.args:
        await update.message.reply_text("Usage: /review <submission_id>")
        return ConversationHandler.END
    
    try:
        submission_id = int(context.args[0])
        submission = get_submission_by_id(submission_id)
        
        if not submission:
            await update.message.reply_text("❌ Submission not found")
            return ConversationHandler.END
        
        
        user = get_user_by_id(submission['user_id'])
        username = user['username'] if user else "Unknown"
        
        
        context.user_data.update({
            'submission_id': submission_id,
            'original_message': update.message.message_id
        })
        
        buttons = [
            [InlineKeyboardButton("✅ Approve", callback_data=f"approve_{submission_id}")],
            [InlineKeyboardButton("🔁 Request Redo", callback_data=f"redo_{submission_id}")],
            [InlineKeyboardButton("❌ Reject", callback_data=f"reject_{submission_id}")]
        ]
        
        await update.message.reply_text(
            f"📝 Review submission #{submission_id}\n"
            f"👤 User: @{username}\n"
            f"📅 Day: {submission['task_id']}\n\n"
            f"Please select an action:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        
    except ValueError:
        await update.message.reply_text("❌ Submission ID must be a number")
    except Exception as e:
        logging.error(f"Review error: {e}", exc_info=True)
        await update.message.reply_text("❌ Failed to start review")
    
    return ConversationHandler.END

async def handle_review_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all review buttons"""
    query = update.callback_query
    await query.answer()
    
    try:
        action, submission_id = query.data.split('_')
        submission_id = int(submission_id)
        submission = get_submission_by_id(submission_id)
        
        if not submission:
            await query.edit_message_text("❌ Submission not found")
            return ConversationHandler.END
            
        # get task info
        task = get_task_by_day(submission['task_id'])
        task_text = task['task_text'] if task else "Unknown Task"
        
        # store in context
        context.user_data.update({
            'action': action,
            'submission_id': submission_id,
            'original_query': query
        })
        
        await query.edit_message_text(
            f"⚡ Action: {action.upper()} submission #{submission_id}\n"
            f"Task: {task_text}\n\n"
            f"Please enter your feedback:"
        )
        
        if action == "approve":
            return APPROVE_FEEDBACK
        elif action == "redo":
            return REDO_FEEDBACK
        elif action == "reject":
            return REJECT_FEEDBACK
            
    except Exception as e:
        logging.error(f"Button error: {e}", exc_info=True)
        await query.edit_message_text("❌ Failed to process selection")
        return ConversationHandler.END

async def approve_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage:\n/approve_feedback <submission_id> <feedback>"
        )
        return

    try:
        submission_id = int(context.args[0])
        feedback = " ".join(context.args[1:])

        # Update to use 'status' instead of 'checked'
        update_submission(submission_id, {
            'checked': SUBMISSION_APPROVED,
            'feedback_text': feedback
        })

        await notify_user(
            context,
            submission_id,
            f"✅ Your submission was approved!\n\n📝 Feedback: {feedback}"
        )

        await update.message.reply_text(f"✅ Approved submission #{submission_id}")

    except ValueError:
        await update.message.reply_text("❌ Invalid submission ID")
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

async def reject_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage:\n/reject_feedback <submission_id> <feedback>"
        )
        return

    try:
        submission_id = int(context.args[0])
        feedback = " ".join(context.args[1:])

        update_submission(submission_id, {
            'checked': SUBMISSION_REJECTED,
            'feedback_text': feedback
        })

        await notify_user(
            context,
            submission_id,
            f"❌ Your submission was rejected.\n\n📝 Feedback: {feedback}"
        )

        await update.message.reply_text(f"❌ Rejected submission #{submission_id}")

    except ValueError:
        await update.message.reply_text("❌ submission_id must be a number")
    except Exception as e:
        logging.error(f"Error rejecting feedback: {e}", exc_info=True)
        await update.message.reply_text("❌ Failed to reject feedback")

async def redo_feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if len(context.args) < 2:
        await update.message.reply_text(
            "Usage:\n/redo_feedback <submission_id> <instructions>"
        )
        return

    try:
        submission_id = int(context.args[0])
        instructions = " ".join(context.args[1:])

        update_submission(submission_id, {
        'checked': SUBMISSION_NEEDS_REDO,
        'feedback_text': f"REDO REQUESTED: {instructions}"
        })

        await notify_user(
            context,
            submission_id,
            f"🔁 Please redo this task:\n\n{instructions}\n\nSubmit your new attempt with /submit_voice"
        )

        await update.message.reply_text(f"🔁 Redo request sent for submission #{submission_id}")

    except ValueError:
        await update.message.reply_text("❌ submission_id must be a number")
    except Exception as e:
        logging.error(f"Error sending redo feedback: {e}", exc_info=True)
        await update.message.reply_text("❌ Failed to send redo request")

async def cancel_review(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current review session"""
    context.user_data.clear()
    await update.message.reply_text("❌ Review cancelled")
    return ConversationHandler.END

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if not context.args:
        await update.message.reply_text("Usage: /remove_user <user_id>")
        return

    try:
        user_id = int(context.args[0])
        conn = None
        try:
            conn = sqlite3.connect('marathon_bot.db')
            cursor = conn.cursor()

            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                await update.message.reply_text(f"✅ User {user_id} removed")
            else:
                await update.message.reply_text(f"❌ User {user_id} not found")
        finally:
            if conn:
                conn.close()
    except ValueError:
        await update.message.reply_text("❌ User ID must be a number")
    except Exception as e:
        logging.error(f"Error removing user: {e}")
        await update.message.reply_text("❌ Failed to remove user")

async def notify_user(context: ContextTypes.DEFAULT_TYPE, submission_id: int, message: str):
    try:
        submission = get_submission_by_id(submission_id)
        if not submission:
            logging.error(f"Submission {submission_id} not found")
            return

        user = get_user_by_id(submission['user_id'])
        if not user:
            logging.error(f"User for submission {submission_id} not found")
            return

        try:
            await context.bot.send_message(
                chat_id=int(user['telegram_id']),  
                text=message[:4000] 
            )
        except Exception as e:
            logging.error(f"Failed to notify user {user['telegram_id']}: {str(e)}")
    except Exception as e:
        logging.error(f"Error in notify_user: {str(e)}", exc_info=True)

async def all_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    users = get_all_users()

    if not users:
        await update.message.reply_text("No users in database")
        return

    response = "📊 All Users:\n\n"
    for user in users:
        response += (
            f"🆔 ID: {user['id']}\n"
            f"👤 @{user['username']}\n"
            f"✅ Approved: {'Yes' if user['approved'] else 'No'}\n"
            f"📌 Task: {user['current_task']} | ✅ Finished: {'Yes' if user['finished'] else 'No'}\n"
            f"📅 Joined: {user['joined_date'].strftime('%Y-%m-%d')}\n"
            f"────────────────────\n"
        )

    # split long messages
    max_length = 4000
    for i in range(0, len(response), max_length):
        await update.message.reply_text(response[i:i+max_length])

import re

async def send_certificate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        await update.message.reply_text("❌ Admin only command")
        return

    if not (update.message.document and update.message.caption):
        await update.message.reply_text(
            "❌ Usage instructions:\n"
            "1. Attach the certificate file\n"
            "2. In the caption, include @username and your message\n\n"
            "Example caption:\n"
            "/send_certificate @username Congratulations!"
        )
        return

    try:
        caption = update.message.caption

        match = re.search(r'@(\w+)', caption)
        if not match:
            await update.message.reply_text("❌ Please include a @username in the caption")
            return

        username = match.group(1).lower()

        user = get_user_by_username(username)
        if not user:
            await update.message.reply_text(f"❌ User @{username} not found in database")
            return

        completed_count = get_completed_task_count(user['id'])
        total_count = get_total_task_count()

        if completed_count < total_count:
            await update.message.reply_text(
                f"⚠️ User hasn't completed all tasks.\n"
                f"Completed: {completed_count}/{total_count}\n"
            )
            return


        file = await update.message.document.get_file()
        if '.' in update.message.document.file_name:
            file_ext = update.message.document.file_name.rsplit('.', 1)[-1]
        else:
            file_ext = 'pdf'
        cert_path = f"storage/certificates/{user['id']}.{file_ext}"
        await file.download_to_drive(custom_path=cert_path)

        # send the certificate to the user
        with open(cert_path, 'rb') as doc_file:
            await context.bot.send_document(
                chat_id=user['telegram_id'],
                document=doc_file,
                caption=caption
            )

        await update.message.reply_text(f"✅ Certificate sent successfully to @{username}")

    except Exception as e:
        logging.error(f"Certificate error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Failed to send certificate: {str(e)}")



def get_admin_handlers():
    return [
        CallbackQueryHandler(view_users_callback, pattern=r'^view_users_\d+$'),
        CallbackQueryHandler(view_tasks_callback, pattern=r'^view_tasks_\d+$'),
        CallbackQueryHandler(view_subs_callback, pattern=r'^view_subs_\d+$'),
        CommandHandler("all_submissions", all_submissions),
        CommandHandler("add_task", add_task_handler),
        CommandHandler("remove_task", remove_task),
        CommandHandler("send_task", send_task),
        CommandHandler("all_tasks", all_tasks),
        CommandHandler("remove_user", remove_user),
        CommandHandler("all_users", all_users),
        CommandHandler("admin_help", admin_help),
        CommandHandler("approve", approve_user),
        CommandHandler("unapproved", list_unapproved_users),
        MessageHandler(
            filters.Document.ALL & filters.CaptionRegex(r'^/send_certificate\b'),
            send_certificate
        ),
        CommandHandler("review", start_review),
        CommandHandler("approve_feedback", approve_feedback_command),
        CommandHandler("reject_feedback", reject_feedback_command),
        CommandHandler("redo_feedback", redo_feedback_command),
        CommandHandler("dashboard", dashboard),
        

    ]
