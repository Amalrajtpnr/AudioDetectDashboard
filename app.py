from flask import Flask, render_template, request, redirect, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from mutagen.mp3 import MP3
from pydub import AudioSegment

app = Flask(__name__)
app.config['UPLOAD_DIRECTORY'] = 'uploads/'
app.config['MAX_CONTENT_LENGTH'] = 30 * 1024 * 1024  # 30MB
app.config['ALLOWED_EXTENSIONS'] = ['.jpg', '.jpeg', '.png', '.gif', '.mp3']
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///uploads.db'
db = SQLAlchemy(app)

# Calculate total duration of audio files
def calculate_total_duration(files):
    total_duration = 0
    for file in files:
        if file.extension == '.mp3':
            audio = AudioSegment.from_mp3(os.path.join(app.config['UPLOAD_DIRECTORY'], file.filename))
            total_duration += len(audio) / 1000  # Convert to seconds
    return total_duration

class UploadedFile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    size = db.Column(db.Integer, nullable=False)
    extension = db.Column(db.String(10), nullable=False)
    duration = db.Column(db.Float, nullable=False)

with app.app_context():
    db.create_all()

def get_audio_duration(filepath):
    audio = MP3(filepath)
    return audio.info.length

@app.route('/')
def main():
    files = UploadedFile.query.all()

    total_duration = 0  # Initialize total duration

    for file in files:
        if file.extension == '.mp3':
            total_duration += file.duration  # Add audio file duration

    return render_template('index.html', files=files, total_duration=total_duration)


@app.route('/upload', methods=['POST'])
def upload():
    try:
        file = request.files['file']
        extension = os.path.splitext(file.filename)[1].lower()

        if file:
            if extension not in app.config['ALLOWED_EXTENSIONS']:
                return 'File type is not allowed'

            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_DIRECTORY'], filename)
            file.save(filepath)

            if extension == '.mp3':
                duration = get_audio_duration(filepath)
            else:
                duration = 0.0

            file_size = os.path.getsize(filepath)

            new_file = UploadedFile(
                filename=filename,
                size=file_size,
                extension=extension,
                duration=duration
            )
            db.session.add(new_file)
            db.session.commit()
    except RequestEntityTooLarge:
        return "File is larger than 30MB"

    return redirect('/')

@app.route('/delete/<int:file_id>', methods=['POST'])
def delete_file(file_id):
    file_to_delete = UploadedFile.query.get_or_404(file_id)

    # Delete the file from the filesystem
    file_path = os.path.join(app.config['UPLOAD_DIRECTORY'], file_to_delete.filename)
    if os.path.exists(file_path):
        os.remove(file_path)

    # Delete the record from the database
    db.session.delete(file_to_delete)
    db.session.commit()

    return redirect('/')

@app.route('/serve-file/<filename>', methods=['GET'])
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_DIRECTORY'], filename)

if __name__ == '__main__':
    app.run(debug=True)
