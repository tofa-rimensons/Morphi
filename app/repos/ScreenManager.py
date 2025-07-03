import json
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler


class ScreenManager:
    def __init__(self, log, json_path: str="Data/config/screens.json"):
        self.log = log
        with open(json_path, 'r', encoding='utf-8') as f:
            self.screens = json.load(f)

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

    def send_screen(
        self, update, context, screen_name: str,
        override_text: str = None, override_image_url: str = None
        ):
        
        screen = self.get_screen(screen_name)
        if not screen:
            self.log.warning(f"Screen '{screen_name}' not found.")
            return

        chat_id = update.effective_chat.id
        image_url = override_image_url or screen.get("image_url")
        text = override_text or screen.get("text", "")
        buttons = screen.get("buttons", [])
        callbacks = screen.get("callbacks", {})

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
