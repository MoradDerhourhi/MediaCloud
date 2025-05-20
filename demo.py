# Media Cloud Project - Python Flask + MongoDB Backend
# Features: Scan, Index, Facial Recognition, Image Analysis, OCR, Thumbnails, API Upload

from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from pymongo import MongoClient
import os
import uuid
import pytesseract
from PIL import Image
import face_recognition
import shutil
from datetime import datetime
import cv2

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
THUMB_FOLDER = 'thumbnails'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp4'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['THUMB_FOLDER'] = THUMB_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(THUMB_FOLDER, exist_ok=True)

client = MongoClient('mongodb://localhost:27017/')
db = client['mediacloud']
media_collection = db['media']

# Utilities

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def generate_thumbnail(image_path, thumb_path):
    try:
        img = Image.open(image_path)
        img.thumbnail((200, 200))
        img.save(thumb_path)
        return True
    except Exception as e:
        print("Thumbnail error:", e)
        return False

def extract_text(image_path):
    try:
        text = pytesseract.image_to_string(Image.open(image_path))
        return text.strip()
    except:
        return ''

def detect_faces(image_path):
    try:
        image = face_recognition.load_image_file(image_path)
        face_locations = face_recognition.face_locations(image)
        encodings = face_recognition.face_encodings(image, face_locations)
        return len(encodings)
    except:
        return 0

# Routes
@app.route('/')
def index():
    return '''
    <h1>Media Cloud API</h1>
    <form action="/upload" method="post" enctype="multipart/form-data">
      <input type="file" name="file">
      <input type="submit" value="Upload">
    </form>
    <a href="/media">Voir les fichiers</a>
    '''

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        file_id = str(uuid.uuid4())
        ext = filename.rsplit('.', 1)[1].lower()
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{file_id}.{ext}")
        file.save(filepath)

        # Metadata
        thumb_path = os.path.join(app.config['THUMB_FOLDER'], f"{file_id}.jpg")
        generate_thumbnail(filepath, thumb_path)

        faces_count = detect_faces(filepath)
        text = extract_text(filepath) if ext in ['jpg', 'jpeg', 'png'] else ''

        document = {
            'id': file_id,
            'filename': filename,
            'ext': ext,
            'path': filepath,
            'thumb': thumb_path,
            'faces_detected': faces_count,
            'ocr_text': text,
            'created_at': datetime.utcnow()
        }
        media_collection.insert_one(document)
        return jsonify({'message': 'Uploaded', 'id': file_id})
    return jsonify({'error': 'Invalid file'})

@app.route('/media/<file_id>', methods=['GET'])
def get_media(file_id):
    doc = media_collection.find_one({'id': file_id})
    if not doc:
        return jsonify({'error': 'Not found'}), 404
    return jsonify({k: str(v) for k, v in doc.items() if k != '_id'})

@app.route('/thumbnail/<file_id>', methods=['GET'])
def get_thumbnail(file_id):
    path = os.path.join(app.config['THUMB_FOLDER'], f"{file_id}.jpg")
    if os.path.exists(path):
        return send_from_directory(app.config['THUMB_FOLDER'], f"{file_id}.jpg")
    return jsonify({'error': 'Thumbnail not found'}), 404

@app.route('/media', methods=['GET'])
def list_media():
    docs = media_collection.find().sort("created_at", -1).limit(50)
    html = "<h1>Fichiers indexés</h1><ul>"
    for doc in docs:
        html += f"<li><a href='/media/{doc['id']}'>{doc['filename']}</a> - <img src='/thumbnail/{doc['id']}' width='50'></li>"
    html += "</ul><a href='/'>Retour</a>"
    return html

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
