from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, ConversationHandler, CallbackContext
import requests
from elasticsearch import Elasticsearch
from ssl import create_default_context
import json
import logging

PHOTO = range(1)  # Define conversation state

enrolled_event_ids = []

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
db = SQLAlchemy(app)

certificate_path = "C:\\Users\\tulukbeku2\\fyp\\http_ca.crt"
context = create_default_context(cafile=certificate_path)
es = Elasticsearch(
    "https://localhost:9200",
    ssl_context=context,
    http_auth=('elastic', 'xF6UCYuwgj6b3LIyj5f7')
)
if not es.indices.exists(index="events"):
    es.indices.create(index="events")

def index_event(event):
    if not es.indices.exists(index="events"):
        es.indices.create(index="events")
        
    event_data = {
        'name': event.name,
        'tags': event.tags
    }
    response = es.index(index='events', id=str(event.id), body=event_data)
    return response

# Create database models
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    photos = db.relationship('Photo', backref='event', lazy=True)

    @property
    def tags(self):
        # This will accumulate all unique tags from the event's photos.
        all_tags = set()
        for photo in self.photos:
            photo_tags = json.loads(photo.tags)  # Assuming photo.tags is a JSON string of tags.
            for tag_list in photo_tags.values():  # Assuming each value in photo_tags is a list of tags.
                all_tags.update(tag_list.get('detected_objects',[]))
       
        return list(all_tags)
    
    @property
    def rating(self):
        total_smile_ratio = 0.0
        count = 0.0
        for photo in self.photos:
            photo_tags = json.loads(photo.tags)  # Assuming photo.tags is a JSON string of tags.
            # Check if 'smiling_ratio' is in the tags and is a number.
            for smiles_list in photo_tags.values():
                if 'smile_ratio' in smiles_list and isinstance(smiles_list['smile_ratio'], (int, float)):
                    total_smile_ratio += smiles_list['smile_ratio']
                    count += 1
        # Calculate the average if at least one photo has a smiling ratio; otherwise, return None.
        return float(total_smile_ratio / count) if count > 0 else None

    
class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(120), unique=True, nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey('event.id'), nullable=False)
    tags = db.Column(db.Text, nullable=True)  # JSON string of tags

# Initialize the database
with app.app_context():
    db.create_all()
    events = Event.query.all()
    for event in events:
        index_event(event)

# Telegram bot token from @BotFather
TELEGRAM_TOKEN = '6466983076:AAET-NZ1gtsoTSluSfEvA_w7xBXcWl95F2A'

# Set up logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Create the EventHandler and pass it your bot's token.
updater = Updater(token=TELEGRAM_TOKEN)

# Get the dispatcher to register handlers
dispatcher = updater.dispatcher

# Define a few command handlers. These usually take the two arguments update and context.
def start(update: Update, context: CallbackContext):
    update.message.reply_text('Hi! I am your event bot. Please secect your mode: /user to browse events or /host to add events.')

def user(update: Update, context: CallbackContext):
    update.message.reply_text('Welcome to User mode. Send /list_events to view all events or /list_enrolled_events to view your enrolled events.')

def host(update: Update, context: CallbackContext):
    update.message.reply_text('Welcome to Host mode. Send /create_event with the name to add your custom event.')


def create_event(update, context):
    # Assuming the user sends the event name as the first argument after the command
    # e.g., "/create_event Birthday Party"
    args = context.args
    if len(args) > 0:
        event_name = ' '.join(args)
        with app.app_context():  # This line creates an application context
            event = Event(name=event_name)
            db.session.add(event)
            db.session.commit()
            index_event(event)
        update.message.reply_text('Event created successfully')
    else:
        update.message.reply_text('Event name is required')



# Handler for listing events
def list_events(update: Update, context: CallbackContext):
    with app.app_context():
        events = Event.query.all()
        keyboard = [
            [InlineKeyboardButton(event.name, callback_data='event_details_{}'.format(event.id))]
            for event in events
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text('Choose an event:', reply_markup=reply_markup)

# Callback query handler to process inline keyboard options
def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    data = query.data
    
    if data.startswith('event_details_'):
        event_id = data.split('_')[2]
        with app.app_context():
            event = Event.query.get(event_id)
            if event:
                if event_id not in enrolled_event_ids:
                    # User is not enrolled, show 'Enroll' button
                    reply_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Enroll", callback_data='enroll_{}'.format(event_id))]
                    ])
                else:
                    # User is enrolled, show 'Cancel Enrollment' and 'Take Photo' buttons
                    reply_markup = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Cancel Enrollment", callback_data='cancel_enrollment_{}'.format(event_id))],
                        [InlineKeyboardButton("Take Photo", callback_data='take_photo_{}'.format(event_id))]  # Placeholder for future implementation
                    ])
                query.edit_message_text(
                    text=f"Event ID: {event.id}\nTitle: {event.name}\nTags: {', '.join(event.tags)}",  # Assuming event has a description field
                    reply_markup=reply_markup
                )
    elif data.startswith('enroll_'):
        enroll(query, context)
    elif data.startswith('cancel_enrollment_'):
        cancel_enrollment(query, context)

# Function to enroll the user in an event
def enroll(query, context: CallbackContext):
    event_id = query.data.split('_')[1]
    
    # Enroll the user in the event
    if event_id not in enrolled_event_ids:
        enrolled_event_ids.append(event_id)
        
        # After enrollment, show success message with 'Cancel Enrollment' and 'Take Photo' buttons
        reply_markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("Cancel Enrollment", callback_data='cancel_enrollment_{}'.format(event_id))],
            [InlineKeyboardButton("Take Photo", callback_data='take_photo_{}'.format(event_id))] 
        ])
        query.edit_message_text(text="You have been enrolled.", reply_markup=reply_markup)
    else:
        query.edit_message_text(text="You are already enrolled in this event.")


# Function to cancel the user's enrollment in an event
def cancel_enrollment(query, context: CallbackContext):
    event_id = query.data.split('_')[2]
    
    # Cancel the user's enrollment in the event
    if event_id in enrolled_event_ids:
        enrolled_event_ids.remove(event_id)
        query.edit_message_text(text="Your enrollment has been canceled.")
        # After cancelation, return to the list of events
        list_events(query, context)
    else:
        query.edit_message_text(text="You are not enrolled in this event.")


def list_enrolled_events(update: Update, context: CallbackContext):
    """Send a message listing all the events the user is enrolled in."""
    if not enrolled_event_ids:
        update.message.reply_text("You are not enrolled in any events.")
        return
    
    message_text = "You are enrolled in the following events:\n"
    with app.app_context():
        keyboard = []
        for event_id in enrolled_event_ids:
            event = Event.query.get(event_id)
            if event:
                button = [InlineKeyboardButton(event.name, callback_data=f"event_details_{event.id}")]
                keyboard.append(button)
            else:
                update.message.reply_text(f"Event ID {event_id} not found.")
                enrolled_event_ids.remove(event_id)

        if keyboard:  # Only if there are events to show
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text('You are enrolled in the following events:', reply_markup=reply_markup)
        else:
            update.message.reply_text("You are not enrolled in any events.")

# Handler for photo upload
def photo_upload(update: Update, context: CallbackContext):
    user = update.message.from_user
    photo_file = update.message.photo[-1].get_file()
    event_id = context.user_data.get('event_id')
    update.message.reply_text('Photo uploaded and analyzed successfully')
    return ConversationHandler.END

# Handler for canceling the conversation
def cancel(update: Update, context: CallbackContext):
    update.message.reply_text('Operation canceled.')
    return ConversationHandler.END

def search(update: Update, context: CallbackContext):
    query = ' '.join(context.args)
    if not query:
        update.message.reply_text("Please provide a search query after the command.")
        return
    
    try:
        response = requests.get(f"http://127.0.0.1:5000/search_events?query={query}")
        
        if response.status_code == 200:
            events = response.json()
            if events:
                # Sort the events by rating just in case they aren't already sorted
                events.sort(key=lambda x: x.get('rating', 0) or 0, reverse=True)
                
                keyboard = [
                    [InlineKeyboardButton(f"{event['name']} (Rating: {format_rating(event.get('rating'))})", callback_data=f"event_details_{event['id']}")]
                    for event in events
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                update.message.reply_text('Search Results:', reply_markup=reply_markup)
            else:
                update.message.reply_text("No events found matching your query.")
        else:
            update.message.reply_text("There was an error processing your search. Please try again.")
    except requests.exceptions.RequestException as e:
        update.message.reply_text(str(e))


def format_rating(rating):
    """
    Format the rating to show two decimal places, converting None to 0.00.
    """
    if rating is None:
        return "0.00"
    else:
        return f"{float(rating):0.2f}"


conv_handler = ConversationHandler(
    entry_points=[CommandHandler('list_events', list_events)],
    states={
        PHOTO: [MessageHandler(Filters.photo, photo_upload)]
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)



# Handler for the "Take Photo" button
def prompt_photo(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    event_id = query.data.split('_')[2]
    context.user_data['current_event_id'] = event_id  # Store the event_id to use later
    query.edit_message_text(text="Please upload a photo.")
    return PHOTO

# Handler to process the photo upload
def photo_handler(update: Update, context: CallbackContext):
    user = update.message.from_user
    photo_file = update.message.photo[-1].get_file()
    event_id = context.user_data.get('current_event_id')

    # Get the file as a byte stream
    photo_stream = requests.get(photo_file.file_path, stream=True).raw

    # Send the photo to the Flask app
    response = requests.post(
        f'http://127.0.0.1:5000/upload_photo/{event_id}',
        files={'photo': ('photo.jpg', photo_stream)}
    )

    if response.status_code == 201:
        update.message.reply_text('Photo uploaded and analyzed successfully!')
    else:
        update.message.reply_text('Failed to upload photo.')

    return ConversationHandler.END


# Conversation handler to manage photo upload
photo_conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(prompt_photo, pattern='^take_photo_')],
    states={PHOTO: [MessageHandler(Filters.photo, photo_handler)]},
    fallbacks=[],
)

# Add photo_conversation_handler to your Application/Dispatcher
dispatcher.add_handler(photo_conversation_handler)


dispatcher.add_handler(conv_handler)
dispatcher.add_handler(CallbackQueryHandler(button))

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("user", user))
dispatcher.add_handler(CommandHandler("host", host))
dispatcher.add_handler(CommandHandler("create_event", create_event))
dispatcher.add_handler(CommandHandler('list_events', list_events))
dispatcher.add_handler(CommandHandler('search', search))
dispatcher.add_handler(CommandHandler('list_enrolled_events', list_enrolled_events))

# Start the Bot
updater.start_polling()

# Start Flask app
if __name__ == '__main__':
    app.run()