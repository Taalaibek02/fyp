from flask import Flask, request, jsonify, flash, redirect, url_for, render_template
from flask_uploads import UploadSet, configure_uploads, IMAGES
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from sqlalchemy.orm.exc import NoResultFound
import os
import json
import cv2
from ultralytics import YOLO
from elasticsearch import Elasticsearch
from ssl import create_default_context

app = Flask(__name__)

# Configure the image uploading via Flask-Uploads
app.config['UPLOADED_PHOTOS_DEST'] = 'uploads'
photos = UploadSet('photos', IMAGES)
configure_uploads(app, photos)

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

# Configure the database via Flask-SQLAlchemy
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
db = SQLAlchemy(app)

certificate_path = "C:\\Users\\tulukbeku2\\fyp\\http_ca.crt"

# Create a default SSL context that uses your self-signed certificate
context = create_default_context(cafile=certificate_path)


es = Elasticsearch(
    "https://localhost:9200",
    ssl_context=context,
    http_auth=('elastic', 'xF6UCYuwgj6b3LIyj5f7')
    )
if not es.indices.exists(index="events"):
    es.indices.create(index="events")



def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS



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

# Define the API endpoints
@app.route('/create_event', methods=['POST'])
def create_event():
    event_name = request.form.get('name')
    if event_name:
        event = Event(name=event_name)
        db.session.add(event)
        db.session.commit()
        index_event(event)
        return jsonify({'message': 'Event created successfully'}), 201
    else:
        return jsonify({'message': 'Event name is required'}), 400
    

@app.route('/events', methods=['GET'])
def get_events():
    # Retrieve all events from the database
    events = Event.query.all()
    # Render the HTML template with the events data
    return render_template('listing.html', events=events)
    

@app.route('/search_events', methods=['GET'])
def search_events():
    query = request.args.get('query', '')
    if query:
        # Perform a search query in Elasticsearch across the 'name' and 'tags' fields
        try:
            # Elasticsearch operation here
            response = es.search(
            index='events',
            query={
                'multi_match': {
                    'query': query,
                    'fields': ['name', 'tags']
                }
            }
        )
        except elasticsearch.NotFoundError as e:
            print(f"Resource not found: {e.info}")
        except elasticsearch.ElasticsearchException as e:
            print(f"An Elasticsearch error occurred: {e}")
        
        # Extract event IDs from the Elasticsearch response
        event_ids = [hit['_id'] for hit in response['hits']['hits']]
        # Retrieve those events from the SQL database
        events = Event.query.filter(Event.id.in_(event_ids)).all()
        # Render the HTML template with the search results
        events_data = [{
            'id': event.id,
            'name': event.name,
            'tags': event.tags,
            'rating': event.rating
        } for event in events]
        return jsonify(events_data)
    else:
        return jsonify({'message': 'Search query is required'}), 400


@app.route('/upload_photo/<int:event_id>', methods=['POST'])
def upload_photo(event_id):
    if 'photo' in request.files:
        filename = photos.save(request.files['photo'])
        # Process the photo and detect tags
        tags = detect_tags(os.path.join(app.config['UPLOADED_PHOTOS_DEST'], filename))
        # Save the photo and tags in the database
        photo = Photo(filename=filename, event_id=event_id, tags=json.dumps(tags))
        db.session.add(photo)
        db.session.commit()
        event = Event.query.get(event_id)
        if event:
            index_event(event)
            return jsonify({'message': 'Photo uploaded and analyzed successfully'}), 201
        else:
            return jsonify({'message': 'Event not found'}), 404
        
    else:
        return jsonify({'message': 'No photo uploaded'}), 400
    

def detect_tags(image_path):
    event_name = "event_identifier" 

   # Initialize a dictionary to hold the results
    event_results = {}
    results = {}

    # Load the cascades for smile detection
    faceCascade = cv2.CascadeClassifier('smile_detection-master/haarcascade_frontalface_default.xml')
    smileCascade = cv2.CascadeClassifier('smile_detection-master/haarcascade_smile.xml')

    # Load an image from file
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Detect faces in the image
    faces = faceCascade.detectMultiScale(
        gray,
        scaleFactor=1.3,
        minNeighbors=5,
        minSize=(30, 30)
    )

    # Smile detection
    total_faces = len(faces)
    smiling_faces = 0

    # Detect smiles within the faces
    for (x, y, w, h) in faces:
        roi_gray = gray[y:y + h, x:x + w]
        smile = smileCascade.detectMultiScale(
            roi_gray,
            scaleFactor=1.4,
            minNeighbors=10,
            minSize=(15, 15),
        )
        if len(smile) > 1:
            smiling_faces += 1
    # Calculate the smile ratio
    smile_ratio = smiling_faces / total_faces if total_faces > 0 else 0

    # Object detection
    model_paths = [
        'YOLOv8/runs/detect/train16/weights/best.pt',
        'YOLOv8/runs/detect/train15/weights/best.pt',
        'YOLOv8/runs/detect/train14/weights/best.pt'
    ]

    # Initialize YOLO models
    models = [YOLO(path) for path in model_paths]

    detected_objects = []
    all_detected_tags = set()
    person_count = 0

    # Run object detection for each model
    for i, model in enumerate(models):
        if model_paths[i] == 'YOLOv8/runs/detect/train14/weights/best.pt':
            confidence = 0.9
        else:
            confidence = 0.6

        result = model(source=img, conf=confidence, imgsz=640, save=True)
        all_class_ids = []
        for r in result:

            all_class_ids.extend(r.boxes.cls.tolist())
            if model_paths[i] == 'YOLOv8/runs/detect/train16/weights/best.pt':
                person_count = all_class_ids.count(0.0)



        detected_tags = [model.names[int(cls_id)] for cls_id in all_class_ids]
        all_detected_tags.update(detected_tags)
        results[f'model_{i+1}'] = detected_tags

    person_tag = 'group' if person_count > 2 else 'solo'
    all_detected_tags.add(person_tag)

    # Store the combined results in the dictionary
    event_results[event_name] = {
        'image_path': image_path,
        'total_faces': total_faces,
        'smiling_faces': smiling_faces,
        'smile_ratio': smile_ratio,
        'detected_objects': list(all_detected_tags)
    }

    return event_results

@app.route('/upload_form/<int:event_id>', methods=['GET'])
def upload_form(event_id):
    # Render the upload form template for the specific event_id
    return render_template('upload_form.html', event_id=event_id)

@app.route('/upload', methods=['POST'])
def upload_file():
    # Check if the post request has the file part
    if 'file' not in request.files:
        flash('No file part')
        return redirect(request.url)
    file = request.files['file']
    
    # If the user does not select a file, the browser submits an
    # empty file without a filename.
    if file.filename == '':
        flash('No selected file')
        return redirect(request.url)
    
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        return f'File {filename} uploaded successfully'
    else:
        return 'File type not allowed'

@app.route('/')
def index():
    return 'Welcome to the Event Management API!'

# Start the Flask application
if __name__ == '__main__':
    app.run(debug=True)

