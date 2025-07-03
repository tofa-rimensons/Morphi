from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
from repos.ScreenManager import ScreenManager
from repos.CryptographyRepo import CryptographyRepo
from repos.GoogleDriveRepo import GoogleDriveRepo
from repos.DBRepo import DBRepo


class ActionManager:
    def __init__(self, log) -> None:
        self.cryptography = CryptographyRepo()
        self.database = DBRepo()
        self.google_drive = GoogleDriveRepo()
        self.screen_manager = ScreenManager(log)

        self.action_methods = {

        }

    def call_action(self, update: Update, context: CallbackContext, action: str):
        pass

    def load_screen(self, update: Update, context: CallbackContext, screen_name: str, override_text: str = None, override_image_url: str = None):
        self.screen_manager.send_screen(update=update, context=context, screen_name=screen_name, override_text=override_text, override_image_url=override_image_url)

    def toggleHrt(self, update: Update, context: CallbackContext):
        pass


    

    def askAll(self, update: Update, context: CallbackContext):
        pass





class ButtonManager:
    def __init__(self, log) -> None:
        self.action = ActionManager(log)

    async def button_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()  # Acknowledge button press

        data = query.data

        if data[:3] == 'scr':
            screen_name = data.split("_")[-1]
            self.action.load_screen(update=update, context=context, screen_name=screen_name)
        else:
            action = data.split("_")[-1]
            self.action.call_action(update=update, context=context, action=action)