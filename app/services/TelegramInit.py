from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, PicklePersistence, CallbackQueryHandler, CallbackContext, ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram.request import HTTPXRequest
from services.BackupService import BackupService
from apscheduler.schedulers.background import BackgroundScheduler
from functools import partial
from types import SimpleNamespace
import os
import io
from pydub import AudioSegment
from datetime import datetime
import json
import time
from repos.GoogleDriveRepo import GoogleDriveRepo
from repos.DBRepo import DBRepo
import logging
from services.DownloaderService import DownloaderService
from services.FetchService import FetchService
import asyncio


# Example: increase read timeout to 60 seconds
request = HTTPXRequest(read_timeout=30)


logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("telegram.bot").setLevel(logging.WARNING)
logging.getLogger('apscheduler').setLevel(logging.WARNING)

class ScreenManager:

    @staticmethod
    def build_keyboard(buttons: list, callbacks: dict) -> InlineKeyboardMarkup:
        keyboard = []
        for row in buttons:
            keyboard_row = [
                InlineKeyboardButton(text=label, callback_data=callbacks.get(label, label))
                for label in row
            ]
            keyboard.append(keyboard_row)
        return InlineKeyboardMarkup(keyboard)

    @staticmethod
    async def send_screen(
        context,
        text,
        image_url: str = "",
        buttons: list = [],
        callbacks: dict = {},
        edit_if_possible: bool = True,
        screen: str = '',
        update=None,  # Optional
        chat_id: int = None  # Required if no update
    ):
        # Use chat_id from update or fallback
        if update:
            chat_id = update.effective_chat.id
            last_message = update.effective_message
        elif chat_id:
            last_message = None
        else:
            raise ValueError("Either `update` or `chat_id` must be provided.")

        # Build markup and clean text
        markup = ScreenManager.build_keyboard(buttons, callbacks)
        text = ScreenManager.escape_markdown(text)

        # Try editing previous bot message (only if update is available)
        if update and edit_if_possible and last_message and last_message.from_user.id == context.bot.id:
            if not image_url and not getattr(last_message, 'photo', None):
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=last_message.message_id,
                        text=text,
                        parse_mode='MarkdownV2',
                        reply_markup=markup
                    )
                    if screen:
                        context.user_data['current_screen'] = screen
                    return
                except Exception:
                    pass  # fallback to sending new if edit fails

        # Otherwise: send new message
        if image_url:
            sent_message = await context.bot.send_photo(
                chat_id=chat_id,
                photo=image_url,
                caption=text,
                parse_mode='MarkdownV2',
                reply_markup=markup
            )
        else:
            sent_message = await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode='MarkdownV2',
                reply_markup=markup
            )

        # Optionally delete last message if it's a bot message
        if update and last_message and last_message.from_user.id == context.bot.id \
                and last_message.message_id != sent_message.message_id and edit_if_possible:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=last_message.message_id)
            except Exception:
                pass

        if screen:
            context.user_data['current_screen'] = screen

    @staticmethod
    def escape_markdown(text: str) -> str:
        escape_chars = r'_[]()~`>#+-=|{}.!'
        return ''.join(f'\\{c}' if c in escape_chars else c for c in text)

class ActionManager:
    def __init__(self) -> None:
        self.database = DBRepo()
        self.google_drive = GoogleDriveRepo()
        self.screen_manager = ScreenManager()
        self.downloader = DownloaderService()
        self.backuper = BackupService(log=logging)
        self.fetcher = FetchService()

        self.image_folder = os.getenv('IMAGE_FOLDER')
        self.vocals_folder = os.getenv('VOCALS_FOLDER')

        self.max_zip_size = 200*1024*1024

        with open("Data/config/screens.json", 'r') as f:
            self.screen_config = json.load(f)

        with open("Data/config/config.json", 'r') as f:
            self.config = json.load(f)

        self.measurement_to_human_names = {
            "weight": "Weight",
            "height": "Height",
            "bonemassFatMuscle": "Body Composition",
            "chestBustWaistHipThigh": "Anthropometrics",
            "bloodPressure": "Blood Pressure",
            "physicalSelfEsteem": "Physical Self Esteem",
            "menthalSelfEsteem": "Mental Self Esteem",
            "libidoSelfEsteem": "Libido Self Esteem",
            "voiceFragment": "Voice Fragment",
            "photoBody": "Body Photo",
            "photoFace": "Face Photo"
        }

        self.measurement_to_unit_names = {
            'weight': 'weight_kg',
            'height': 'height_cm',
            'bonemass': 'bonemass_pct',
            'fat': 'fat_pct',
            'muscle': 'muscle_pct',
            'chest': 'chest_cm',
            'bust': 'bust_cm',
            'waist': 'waist_cm',
            'hip': 'hip_cm',
            'thigh': 'thigh_cm',
            'systolic': 'systolic_mmhg',
            'diastolic': 'diastolic_mmhg',
            'heartRate': 'heartRate_bpm',
            'physicalSelfEsteem': 'physicalSelfEsteem',
            'menthalSelfEsteem': 'menthalSelfEsteem',
            'libidoSelfEsteem': 'libidoSelfEsteem',
            'voiceFragment': 'voiceFragment_url',
            'photoBody': 'photoBody_url',
            'photoFace': 'photoFace_url'
        }

        self.action_methods = {
            "settings": self.settings,
            "masterInterval": self.masterInterval,
            "masterIntervalSet": self.masterIntervalSet,
            "measurementInterval": self.measurementInterval,
            "measurementIntervalSet": self.measurementIntervalSet,
            "measurementIntervalMove": self.measurementIntervalMove,
            "deleteUserData": self.deleteUserData,
            "hrtInfo": self.hrtInfo,
            "hrtInfoSet": self.hrtInfoSet,
            "hrtInfoType": self.hrtInfoSet,
            "hrtInfoDose": self.hrtInfoSet,
            "switchResearchAllowance": self.switchResearchAllowance,
            "stats": self.stats,
            "measurementSeq": self.measurementSeq,
            "measurementSeqNext": self.measurementSeqNext,
            "measurementSeqSetText": self.measurementSeqSetText,
            "measurementSeqSetVoice": self.measurementSeqSetVoice,
            "measurementSeqSetImage": self.measurementSeqSetImage,
            "downloadImages": self.downloadImages,
            "downloadVocals": self.downloadVocals,
            "downloadDatabase": self.downloadDatabase,
            "admin": self.admin
        }

    async def call_action(self, update: Update, context: CallbackContext, action: str):
        await self.action_methods[action](update, context)

    def get_screen_data(self, screen: str):
        text = self.screen_config[screen]["text"]
        image_url = self.screen_config[screen]["image_url"]
        buttons = self.screen_config[screen]["buttons"]
        callbacks = self.screen_config[screen]["callbacks"]

        return text, image_url, buttons, callbacks
    
    def get_user_data(self, update: Update):
        user_id = update.effective_user.id
        data = self.database.get_user_dict(user_id)
        return data
    
    def get_measurements_row_count(self, update: Update):
        user_id = update.effective_user.id
        row_count, first_measurement, last_measurement = self.database.get_measurements_row_count(user_id)
        return row_count, first_measurement, last_measurement

    async def load_screen(self, update: Update, context: CallbackContext, screen: str):
        text, image_url, buttons, callbacks = self.get_screen_data(screen)
        await self.screen_manager.send_screen(update=update, context=context, screen=screen, text=text, image_url=image_url, buttons=buttons, callbacks=callbacks)

    async def downloadZip(self, update: Update, context: CallbackContext, col_name_list: list[str], zip_name: str, file_extension: str):
        await self.load_screen(update, context, screen='download')

        if context.user_data.get('is_downloading'):
            await self.load_screen(update, context, screen='downloadInProgress')
            return

        context.user_data['is_downloading'] = True

        try:

            user_id = update.effective_user.id
            file_ids = self.database.get_measurement_values(user_id, col_name_list=col_name_list)

            zip_bytes = self.downloader.download_files_as_zip(zip_name=f"{zip_name}_{user_id}.zip", 
                                                            file_ids=file_ids, decode=True, file_extension=file_extension, 
                                                            max_zip_size=self.max_zip_size)
            
            zip_file = io.BytesIO(zip_bytes)
            zip_file.name = f"{zip_name}_{user_id}.zip"
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=zip_file
            )
            await self.load_screen(update, context, screen='downloadComplete')
            
        finally:
            
            context.user_data['is_downloading'] = False

    async def incorrect_input_warning(self, update: Update, info: str):
        text, _, _, _ = self.get_screen_data('incorrectInputWarning')
        text = self.screen_manager.escape_markdown(text+info)
        await update.message.reply_text(text=text, parse_mode='MarkdownV2')
    
    async def broadcast_screen(self, application=None, screen='broadcast', context=None, all_users: bool=False):
        text, image_url, buttons, callbacks = self.get_screen_data(screen)

        if all_users:
            user_ids = self.database.get_users()  
        else:
            user_ids = self.database.users_to_broadcast()  

        logging.info(f"Broadcasting to {len(user_ids)} bunnies with [{screen}] :3")

        i = 0
        for user_id in user_ids:
            try:

                if not context:
                    # Create minimal fake context
                    context = SimpleNamespace(
                        bot=application.bot,
                        user_data={}  # or preload per-user data if needed
                    )

                await self.screen_manager.send_screen(
                    context=context,
                    chat_id=user_id,
                    text=text,
                    image_url=image_url,
                    buttons=buttons,
                    callbacks=callbacks,
                )
                i += 1
            except Exception as e:
                logging.warning(f"Failed to send screen to {user_id}: {e}")

        logging.info(f"{i} heard broadcast!")

    async def admin(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        if user_id != self.config["admin_id"]:
            await self.load_screen(update, context, screen='start')
            return

        callback_query = update.callback_query


        if update.message and (update.message.text in self.screen_config and not update.message.text in self.action_methods):
            await self.broadcast_screen(context=context, screen=update.message.text, all_users=True)
            await self.load_screen(update, context, screen='admin')
            return
        elif callback_query:
            data = callback_query.data.split('_')
        else:
            await self.load_screen(update, context, screen='admin')
            return
        
        if data[-1] == 'updateScreenConfig':
            self.fetcher.fetch_all()
            with open("Data/config/screens.json", 'r') as f:
                self.screen_config = json.load(f)
            logging.info("Config Updated!")
        
        await self.load_screen(update, context, screen='admin')



    async def settings(self, update: Update, context: CallbackContext):
        text, image_url, buttons, callbacks = self.get_screen_data('settings')
        user_data = self.get_user_data(update)

        # Basic info
        research_allowed = 'yes' if user_data['is_research_allowed'] else 'no'
        hrt_type = user_data['hrt_type'] if user_data['hrt_type'] else 'no'
        hrt_dose = f"{user_data['hrt_dose']} mg" if user_data['hrt_dose'] else 'no'

        # Measurement Intervals
        measurement_lines = []
        for key, display_name in self.measurement_to_human_names.items():
            interval = user_data.get(f"{key}_interval")
            interval_text = f"every {interval} measurement(s)" if interval else "no"
            measurement_lines.append(f"{display_name}: *{interval_text}*")

        dynamic_text = f"""
Research Allowed: *{research_allowed}*
HRT Type: *{hrt_type}*
HRT Dose: *{hrt_dose}*

Measurement Intervals:
{chr(10).join(measurement_lines)}
        """

        await self.screen_manager.send_screen(update=update, context=context, screen='settings', text=text + dynamic_text, image_url=image_url, buttons=buttons, callbacks=callbacks)

    async def hrtInfo(self, update: Update, context: CallbackContext):
        text, image_url, buttons, callbacks = self.get_screen_data('hrtInfo')
        user_data = self.get_user_data(update)

        # Basic info
        hrt_type = user_data['hrt_type'] if user_data['hrt_type'] else 'no'
        hrt_dose = f"{user_data['hrt_dose']} mg/day" if user_data['hrt_dose'] else 'no'

        dynamic_text = f"""
HRT Type: *{hrt_type}*
HRT Dose: *{hrt_dose}*
        """
        await self.screen_manager.send_screen(update=update, context=context, screen='hrtInfo', text=text + dynamic_text, image_url=image_url, buttons=buttons, callbacks=callbacks)

    async def hrtInfoSet(self, update: Update, context: CallbackContext):
        callback_query = update.callback_query
        user_id = update.effective_user.id

        if callback_query:
            action = callback_query.data.split('_')[-1]

            if action == 'remove':
                self.database.set_user_data(user_id, {'hrt_type': 'NULL', 'hrt_dose': 'NULL'})
                await self.hrtInfo(update, context)
            elif action == 'type':
                await self.load_screen(update, context, screen='hrtInfoType')
            elif action == 'dose':
                await self.load_screen(update, context, screen='hrtInfoDose')

        else:
            current_screen = context.user_data.get('current_screen')
            if current_screen == 'hrtInfoType':
                text = update.message.text 
                self.database.set_user_data(user_id, hrt_type=text)
                await self.hrtInfo(update, context)
            elif current_screen == 'hrtInfoDose':
                text = update.message.text 

                try:
                    # Replace comma with dot for EU-style decimals
                    cleaned_input = text.replace(',', '.').strip()
                    value = float(cleaned_input)
                    if value < 0:
                        await self.incorrect_input_warning(update, "*Value should be positive*")
                        return
                except (ValueError, TypeError):
                    # Call your custom error function
                    await self.incorrect_input_warning(update, "*Incorrect format*\n(Enter number only)")
                    return

                user_id = update.effective_user.id
                self.database.set_user_data(user_id, hrt_dose=value)
                await self.hrtInfo(update, context)
        
    async def masterInterval(self, update: Update, context: CallbackContext):
        text, image_url, buttons, callbacks = self.get_screen_data('masterInterval')
        user_data = self.get_user_data(update)

        master_interval = user_data['master_interval'] if user_data['master_interval'] else 0

        dynamic_text = f'''
Current Interval: *{master_interval} days*
        '''
        await self.screen_manager.send_screen(update=update, context=context, screen='masterInterval', text=text+dynamic_text, image_url=image_url, buttons=buttons, callbacks=callbacks)

    async def masterIntervalSet(self, update: Update, context: CallbackContext):
        data = update.callback_query.data
        interval = int(data.split('_')[2])

        user_id = update.effective_user.id

        self.database.set_user_data(user_id, master_interval=interval)
        await self.masterInterval(update, context)

    async def measurementInterval(self, update: Update, context: CallbackContext):
        user_data = self.get_user_data(update)
        
        current_screen = context.user_data.get('current_screen', '')
        current_measurement = current_screen.split('_')[-1] if current_screen else None
        
        keys = list(self.measurement_to_human_names.keys())
        
        if current_measurement not in keys:
            current_measurement = keys[0]  # fallback to first key
            context.user_data['current_screen'] = f'measurementInterval_{current_measurement}'
        
        interval_key = f'{current_measurement}_interval'
        interval_value = user_data.get(interval_key)
        value_to_display = f"every {interval_value} measurement(s)" if interval_value else 'no'
        if value_to_display == 'prc':
            value_to_display = '%'
        
        dynamic_text = f'''
*{self.measurement_to_human_names[current_measurement]}:*
Current Interval: *{value_to_display}*
        '''
        
        text, image_url, buttons, callbacks = self.get_screen_data('measurementInterval')
        await self.screen_manager.send_screen(update=update, context=context, text=text+dynamic_text, image_url=image_url, buttons=buttons, callbacks=callbacks)

    async def measurementIntervalSet(self, update: Update, context: CallbackContext):
        data = update.callback_query.data
        interval = int(data.split('_')[2])
        current_screen = context.user_data.get('current_screen').split('_')[1] + '_interval'

        user_id = update.effective_user.id
        self.database.set_user_data(user_id, **{current_screen: interval})
        await self.measurementInterval(update, context)

    async def measurementIntervalMove(self, update: Update, context: CallbackContext):
        data = update.callback_query.data
        try:
            direction = int(data.split('_')[-1])
        except:
            return
        
        current_screen = context.user_data.get('current_screen').split('_')[1]

        keys = list(self.measurement_to_human_names.keys())
        i = keys.index(current_screen)
        next_measurement = keys[(i + direction) % len(keys)]

        context.user_data['current_screen'] = 'measurementInterval_'+next_measurement
        await self.measurementInterval(update, context)

    async def switchResearchAllowance(self, update: Update, context: CallbackContext):
        user_id = update.effective_user.id
        user_data = self.get_user_data(update)
        new_state = not user_data['is_research_allowed']

        self.database.set_user_data(user_id, is_research_allowed=new_state)
        await self.settings(update, context)

    async def deleteUserData(self, update: Update, context: CallbackContext):
        current_screen = context.user_data.get('current_screen')
        if current_screen != 'deleteUserData':
            text, image_url, buttons, callbacks = self.get_screen_data('deleteUserData')
            await self.screen_manager.send_screen(update=update, context=context, screen='deleteUserData', text=text, image_url=image_url, buttons=buttons, callbacks=callbacks)
            return
        
        text = update.message.text
        if text == 'delete':
            user_id = update.effective_user.id
            file_ids = self.database.get_measurement_values(user_id, col_name_list=['voiceFragment_url', 'photoBody_url', 'photoFace_url'])
            for id in file_ids:
                self.google_drive.delete_file(id)

            self.database.delete_user_data(user_id)
            text, image_url, buttons, callbacks = self.get_screen_data('deleteUserDataSuccess')
            await self.screen_manager.send_screen(update=update, context=context, screen='deleteUserDataSuccess', text=text, image_url=image_url, buttons=buttons, callbacks=callbacks)
        else:
            failure_text = "\nYou didn't input *'delete'*\nTry again!"
            text, image_url, buttons, callbacks = self.get_screen_data('deleteUserData')
            await self.screen_manager.send_screen(update=update, context=context, screen='deleteUserData', text=text+failure_text, image_url=image_url, buttons=buttons, callbacks=callbacks)
        
    async def stats(self, update: Update, context: CallbackContext):
        text, image_url, buttons, callbacks = self.get_screen_data('stats')
        row_count, first_measurement, last_measurement  = self.get_measurements_row_count(update)
        first_measurement = datetime.fromtimestamp(first_measurement).strftime("%d.%m.%Y") if row_count != 0 else 'None'
        last_measurement = datetime.fromtimestamp(last_measurement).strftime("%d.%m.%Y") if row_count != 0 else 'None'

        dynamic_text = f'''
Number Of Measurements: {row_count}
First Measurement: {first_measurement}
Latest Measurement: {last_measurement}
        '''
        await self.screen_manager.send_screen(update=update, context=context, screen='stats', text=text+dynamic_text, image_url=image_url, buttons=buttons, callbacks=callbacks)

    async def measurementSeq(self, update: Update, context: CallbackContext, is_last: bool=False):
        current_screen = context.user_data.get('current_screen').split('_')
        callback_query = update.callback_query
        if current_screen[-1] not in list(self.measurement_to_unit_names.keys()):
            await self.measurementSeqNext(update, context)
            return
        if callback_query:
            data = callback_query.data
            action = data.split('_')[-1]
            if action == 'skip':
                await self.measurementSeqNext(update, context)
                return
        
        user_id = update.effective_user.id
        col_name = self.measurement_to_unit_names[current_screen[-1]]
        col_name_splitted = col_name.split('_')
        unit = '' if len(col_name_splitted) < 2 or col_name_splitted[-1]=='url' else ' '+col_name_splitted[-1]
        last_measurement = self.database.get_last_measurement(user_id)
        measurement_key = current_screen[-1]

        if last_measurement:
            measurement_val = f"{last_measurement[col_name]}{unit}" if last_measurement[col_name] else 'no'
        else:
            measurement_val = 'no'

        dynamic_text = f"""
{measurement_key}: *{measurement_val}*
        """
            
        text, image_url, buttons, callbacks = self.get_screen_data(current_screen[-1])

        buttons = [buttons[-1] if is_last else buttons[0]]
        await self.screen_manager.send_screen(update=update, context=context, text=text+dynamic_text, image_url=image_url, buttons=buttons, callbacks=callbacks)

    async def measurementSeqNext(self, update: Update, context: CallbackContext):
        current_screen = context.user_data.get('current_screen').split('_')[-1]
        user_id = update.effective_user.id
        all_screens = self.database.get_due_measurements(user_id)

        if all_screens:
            i = all_screens.index(current_screen) + 1 if current_screen in all_screens else 0
            num_screens = len(all_screens)
            if i < num_screens:
                next_measurement = all_screens[i]
            else:
                next_measurement = all_screens[-1]

            if i >= num_screens-1:
                is_last = True
            else:
                is_last = False
        else:
            await self.load_screen(update, context, screen='noToMeasure')
            return

        context.user_data['current_screen'] = 'measurementSeq_'+next_measurement
        await self.measurementSeq(update, context, is_last)

    async def measurementSeqSetText(self, update: Update, context: CallbackContext):
        current_screen = context.user_data.get('current_screen').split('_')[-1]
        if current_screen in ['voiceFragment', 'photoBody', 'photoFace']:
            await self.incorrect_input_warning(update, "*Incorrect format*\n(Enter number only)")
            return
        
        text = update.message.text
        try:
            # Replace comma with dot for EU-style decimals
            cleaned_input = text.replace(',', '.').strip()
            value = float(cleaned_input)
            if value < 0:
                await self.incorrect_input_warning(update, "*Value should be positive*")
                return
            if 'SelfEsteem' in current_screen:
                if value > 5:
                    await self.incorrect_input_warning(update, "*Value should be between 0 and 5*")
                    return
        except (ValueError, TypeError):
            # Call your custom error function
            await self.incorrect_input_warning(update, "*Incorrect format*\n(Enter number only)")
            return
        
        user_id = update.effective_user.id
        self.database.save_measurement(user_id, **{self.measurement_to_unit_names[current_screen]: value})
        await self.measurementSeq(update, context)

    async def measurementSeqSetVoice(self, update: Update, context: CallbackContext):
        current_screen = context.user_data.get('current_screen').split('_')[-1]
        print(current_screen)
        if current_screen != 'voiceFragment':
            await self.incorrect_input_warning(update, "*Incorrect format*\n(Send audio only)")
            return

        # Get audio file ID
        if update.message.voice:
            file_id = update.message.voice.file_id
        elif update.message.audio:
            file_id = update.message.audio.file_id
        elif update.message.document and update.message.document.mime_type.startswith('audio/'):
            file_id = update.message.document.file_id
        else:
            await self.incorrect_input_warning(update, "*Incorrect format*\n(Send audio only)")
            return

        # Download the file into memory
        telegram_file = await context.bot.get_file(file_id)
        file_bytes = io.BytesIO()
        await telegram_file.download_to_memory(out=file_bytes)
        file_bytes.seek(0)

        # Convert to MP3 using pydub
        ogg_audio = AudioSegment.from_file(file_bytes, format="ogg")

        mp3_bytes = io.BytesIO()
        ogg_audio.export(mp3_bytes, format="mp3")
        mp3_bytes.seek(0)

        # Upload to Google Drive
        filename = f"{current_screen}_{str(int(time.time()))}"
        url = self.google_drive.upload_file_from_bytes(
            file_bytes=mp3_bytes,
            filename=filename,
            folder_id=self.vocals_folder,
            encode=True
        )

        # Save measurement in DB
        col_name = self.measurement_to_unit_names[current_screen]
        user_id = update.effective_user.id
        last_measurement = self.database.get_last_measurement(user_id)
        if last_measurement:
            last_url = last_measurement.get(col_name)
            if last_url:
                self.google_drive.delete_file(last_url)

        self.database.save_measurement(user_id, **{col_name: url})
        await self.measurementSeq(update, context)

    async def measurementSeqSetImage(self, update: Update, context: CallbackContext):
        current_screen = context.user_data.get('current_screen').split('_')[-1]
        if current_screen not in ['photoBody', 'photoFace']:
            await self.incorrect_input_warning(update, "*Incorrect format*\n(Send image only)")
            return
        
        image_bytes = io.BytesIO()

        if update.message.photo:
            # Pick largest photo size
            photo = update.message.photo[-1]
            file = await context.bot.get_file(photo.file_id)
            await file.download_to_memory(out=image_bytes)

        elif update.message.document and update.message.document.mime_type.startswith('image/'):
            # Image sent as document
            file = await context.bot.get_file(update.message.document.file_id)
            await file.download_to_memory(out=image_bytes)

        else:
            await self.incorrect_input_warning(update, "*Incorrect format*\n(Send image only)")
            return

        image_bytes.seek(0)

        filename = f"{current_screen}_{str(int(time.time()))}"
        url = self.google_drive.upload_file_from_bytes(
            file_bytes=image_bytes,
            filename=filename,
            folder_id=self.image_folder,
            encode=True
        )


        col_name = self.measurement_to_unit_names[current_screen]
        user_id = update.effective_user.id
        last_measurement = self.database.get_last_measurement(user_id)
        if last_measurement:
            last_url = last_measurement[col_name]
            if last_url:
                self.google_drive.delete_file(last_url)
                
        self.database.save_measurement(user_id, **{col_name: url})
        await self.measurementSeq(update, context)

    async def downloadImages(self, update: Update, context: CallbackContext):
        await self.downloadZip(update, context, 
                               col_name_list=['photoBody_url', 'photoFace_url'],
                               zip_name='images',
                               file_extension='.jpg')

    async def downloadVocals(self, update: Update, context: CallbackContext):
        await self.downloadZip(update, context, 
                               col_name_list=['voiceFragment_url'],
                               zip_name='voiceFragments',
                               file_extension='.mp3')

    async def downloadDatabase(self, update: Update, context: CallbackContext):
        await self.load_screen(update, context, screen='download')

        if context.user_data.get('is_downloading'):
            await self.load_screen(update, context, screen='downloadInProgress')
            return

        context.user_data['is_downloading'] = True

        try:

            user_id = update.effective_user.id
            measurement_df = self.database.get_measurements_df(user_id)

            zip_bytes = self.downloader.dataframe_to_zip_bytes(
                df=measurement_df,
                csv_filename="measurementData.csv",
                zip_filename=f"measurementData_{user_id}.zip"
            )

            zip_file = io.BytesIO(zip_bytes)
            zip_file.name = f"measurementData_{user_id}.zip"
            
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=zip_file
            )

            await self.load_screen(update, context, screen='downloadComplete')
            context.user_data['is_downloading'] = False

        finally:
            context.user_data['is_downloading'] = False
        

class HandlerManager:
    def __init__(self) -> None:
        self.action = ActionManager()

        with open("Data/config/config.json", 'r') as f:
            self.config = json.load(f)

        self.text_input_funcs = {
            'deleteUserData': 'deleteUserData', 
            'hrtInfoSet': 'hrtInfoSet', 
            'hrtInfoType': 'hrtInfoType', 
            'hrtInfoDose': 'hrtInfoDose', 
            'measurementSeq':'measurementSeqSetText',
            'admin': 'admin'
            }
        
        self.voice_input_funcs = {
            'measurementSeq':'measurementSeqSetVoice'
            }
        
        self.image_input_funcs = {
            'measurementSeq':'measurementSeqSetImage'
            }

    async def button_handler(self, update: Update, context: CallbackContext):
        query = update.callback_query
        await query.answer()  # Acknowledge button press

        data = query.data

        if data[:3] == 'scr':
            screen = data.split("_")[1]
            await self.action.load_screen(update=update, context=context, screen=screen)
        elif data[:3] == 'cmd':
            action = data.split("_")[1]
            await self.action.call_action(update=update, context=context, action=action)


    async def text_message_handler(self, update: Update, context: CallbackContext):
        current_screen = context.user_data.get('current_screen').split('_')[0]
        if not current_screen:
            return
        if current_screen in list(self.text_input_funcs.keys()):
            await self.action.call_action(update=update, context=context, action=self.text_input_funcs[current_screen])


    async def voice_message_handler(self, update: Update, context: CallbackContext):
        current_screen = context.user_data.get('current_screen').split('_')[0]
        if not current_screen:
            return
        if current_screen in list(self.voice_input_funcs.keys()):
            await self.action.call_action(update=update, context=context, action=self.voice_input_funcs[current_screen])


    async def image_message_handler(self, update: Update, context: CallbackContext):
        current_screen = context.user_data.get('current_screen').split('_')[0]
        if not current_screen:
            return
        if current_screen in list(self.image_input_funcs.keys()):
            await self.action.call_action(update=update, context=context, action=self.image_input_funcs[current_screen])

    async def start(self, update, context):
        await self.action.load_screen(update=update, context=context, screen='start')

    async def settings(self, update, context):
        user_id = update.effective_user.id
        if user_id == self.config["admin_id"]:
            logging.info(f"Admin [{user_id}] in control panel...")
            await self.action.admin(update=update, context=context)
        else:
            await self.action.settings(update=update, context=context)

class Scheduler:
    def __init__(self):
        self.actions = ActionManager()

    def start_scheduler(self, bot, loop=None):
        scheduler = BackgroundScheduler(timezone="Europe/Brussels")

        # Use current event loop or get a new one
        if loop is None:
            loop = asyncio.get_event_loop()

        def run_async_broadcast():
            loop.create_task(self.actions.broadcast_screen(bot, screen='broadcast'))

        # Schedule jobs
        scheduler.add_job(run_async_broadcast, 'cron', hour=8, minute=0)
        scheduler.add_job(run_async_broadcast, 'cron', hour=14, minute=0)
        scheduler.add_job(run_async_broadcast, 'cron', hour=20, minute=0)

        scheduler.start()
        
class BotManager:
    def __init__(self):
        self.handler = HandlerManager()
        self.scheduler = Scheduler()

        self.actions = ActionManager()
        
    def run(self):
        token = os.getenv('TG_TOKEN')
        persistence = PicklePersistence(filepath='Data/database/bot_data.pkl')
        app = ApplicationBuilder().token(token).persistence(persistence).build()

        self.scheduler.start_scheduler(app, loop=asyncio.get_event_loop())

        if app.persistence.user_data:
            for user_id, user_data in app.persistence.user_data.items():
                user_data['is_downloading'] = False

        app.add_handler(CommandHandler("start", self.handler.start))
        app.add_handler(CommandHandler("settings", self.handler.settings))

        app.add_handler(MessageHandler(filters.TEXT, self.handler.text_message_handler))
        app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO | filters.Document.AUDIO, self.handler.voice_message_handler))
        app.add_handler(MessageHandler(filters.PHOTO, self.handler.image_message_handler))

        app.add_handler(CallbackQueryHandler(self.handler.button_handler))

        app.run_polling()