from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext
import json
from repos.CryptographyRepo import CryptographyRepo
from repos.GoogleDriveRepo import GoogleDriveRepo
from repos.DBRepo import DBRepo

class ScreenManager:
    def __init__(self, log):
        self.log = log

    def get_screen(self, name: str) -> dict:
        return self.screens.get(name)

    def build_keyboard(self, buttons: list, callbacks: dict) -> InlineKeyboardMarkup:
        keyboard = []
        for row in buttons:
            keyboard_row = [
                InlineKeyboardButton(text=label, callback_data=callbacks.get(label, label))
                for label in row
            ]
            keyboard.append(keyboard_row)
        return InlineKeyboardMarkup(keyboard)

    def send_screen(self, update, context, text, image_url: str=None, buttons: list=[], callbacks: dict={}):

        chat_id = update.effective_chat.id

        markup = self.build_keyboard(buttons, callbacks)

        # Attempt to get the last message from the chat
        last_message = update.effective_message

        # Check if the last message was sent by the bot
        if last_message and last_message.from_user.id == context.bot.id:
            try:
                if image_url:
                    # If there's an image, re-send the photo (editing photo is not supported by Telegram)
                    context.bot.delete_message(chat_id=chat_id, message_id=last_message.message_id)
                    context.bot.send_photo(chat_id=chat_id, photo=image_url, reply_markup=markup)
                    context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
                else:
                    # Safe to edit just the text and buttons
                    context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=last_message.message_id,
                        text=text,
                        reply_markup=markup
                    )
            except Exception as e:
                self.log.warning(f"Failed to edit message: {e}")
                # Fallback to sending a new message
                if image_url:
                    context.bot.send_photo(chat_id=chat_id, photo=image_url, reply_markup=markup)
                context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)
        else:
            # Not a bot message or can't edit
            if image_url:
                context.bot.send_photo(chat_id=chat_id, photo=image_url, reply_markup=markup)
            context.bot.send_message(chat_id=chat_id, text=text, reply_markup=markup)

class ActionManager:
    def __init__(self, log) -> None:
        self.cryptography = CryptographyRepo()
        self.database = DBRepo()
        self.google_drive = GoogleDriveRepo()
        self.screen_manager = ScreenManager(log)

        with open("Data/config/screens.json", 'r') as f:
            self.screen_config = json.load(f)

        self.action_methods = {

        }

    def call_action(self, update: Update, context: CallbackContext, action: str):
        pass

    def load_screen_from_config(self, update: Update, context: CallbackContext, screen_name: str):
        text = self.screen_config[screen_name]["text"]
        image_url = self.screen_config[screen_name]["image_url"]
        buttons = self.screen_config[screen_name]["buttons"]
        callbacks = self.screen_config[screen_name]["callbacks"]
        self.screen_manager.send_screen(update, context, text=text, image_url=image_url, buttons=buttons, callbacks=callbacks)

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


class BotManager