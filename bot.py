import logging
from telegram.ext import Application
from user_handlers import get_user_handlers
from admin_handlers import get_admin_handlers
from database import init_db

# logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    """Run the bot."""
    # Initialize database
    #init_db()
    #logger.info("Database initialized")
    
    # create the application
    application = Application.builder().token("7741652804:AAHoRFab6KNATIGJEoSFJfUJKxkWc4g3s3A").build()
    
    # add handlers
    for handler in get_admin_handlers():
        application.add_handler(handler)

    for handler in get_user_handlers():
        application.add_handler(handler)
    
    application.run_polling()

if __name__ == "__main__":
    main()