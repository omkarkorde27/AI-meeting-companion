from flask import Flask, render_template, request, jsonify, session
from flask_socketio import SocketIO, emit
import os
import base64
import json
import uuid
from dotenv import load_dotenv
import threading
import nltk
nltk.download('punkt_tab')

# Import services
from services.transcription_service import transcription_service
from services.summarization_service import summarization_service
from services.action_items_service import action_items_service
from services.sentiment_service import sentiment_service
from config import current_config as config

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(config)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

# Global storage for ongoing sessions
sessions = {}

# Routes
@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Render the dashboard page."""
    return render_template('dashboard.html')

# API endpoints
@app.route('/api/upload', methods=['POST'])
def upload_audio():
    """Handle audio file uploads."""
    print("Upload request received")
    print(f"Request files: {request.files}")
    
    if 'file' not in request.files:
        print("Error: No file part in the request")
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    print(f"File received: {file.filename}")
    
    if file.filename == '':
        print("Error: Empty filename")
        return jsonify({'error': 'No selected file'}), 400
    
    # Check if the file extension is allowed
    extension = os.path.splitext(file.filename)[1].lower()[1:]
    if extension not in app.config['ALLOWED_EXTENSIONS']:
        print(f"Error: File type not allowed - {extension}")
        return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(app.config["ALLOWED_EXTENSIONS"])}'})
    
    # Save the file with original filename (without unique prefix)
    # This matches the filename that appears in the URL
    filename = file.filename
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    # Ensure the upload directory exists
    upload_dir = app.config['UPLOAD_FOLDER']
    print(f"Making sure upload directory exists: {upload_dir}")
    os.makedirs(upload_dir, exist_ok=True)
    
    # Save the file
    print(f"Saving file to: {filepath}")
    file.save(filepath)
    
    # Verify file was saved successfully
    if os.path.exists(filepath):
        print(f"File saved successfully at {filepath}")
    else:
        print(f"ERROR: File not saved at {filepath}")
        return jsonify({'error': 'Failed to save file'}), 500
    
    # Create a new session for this file
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        'filepath': filepath,
        'filename': filename,
        'status': 'processing',
        'transcript': '',
        'summary': None,
        'action_items': None,
        'sentiment': None
    }
    
    # Start processing in a background thread to avoid blocking
    processing_thread = threading.Thread(
        target=process_audio_file,
        args=(session_id, filepath)
    )
    processing_thread.daemon = True
    processing_thread.start()
    
    return jsonify({
        'message': 'File uploaded successfully',
        'filename': filename,
        'session_id': session_id
    })
    
    # Check if the file extension is allowed
    extension = os.path.splitext(file.filename)[1].lower()[1:]
    if extension not in app.config['ALLOWED_EXTENSIONS']:
        return jsonify({'error': f'File type not allowed. Allowed types: {", ".join(app.config["ALLOWED_EXTENSIONS"])}'})
    
    # Generate a unique filename to avoid conflicts
    unique_filename = f"{uuid.uuid4()}_{file.filename}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    
    # Ensure the upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Save the file
    file.save(filepath)
    
    # Create a new session for this file
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        'filepath': filepath,
        'filename': file.filename,
        'unique_filename': unique_filename,
        'status': 'processing',
        'transcript': '',
        'summary': None,
        'action_items': None,
        'sentiment': None
    }
    
    # Start processing in a background thread to avoid blocking
    processing_thread = threading.Thread(
        target=process_audio_file,
        args=(session_id, filepath)
    )
    processing_thread.daemon = True
    processing_thread.start()
    
    return jsonify({
        'message': 'File uploaded successfully',
        'filename': file.filename,
        'session_id': session_id
    })

@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get list of active sessions."""
    session_list = []
    for session_id, session_data in sessions.items():
        session_list.append({
            'id': session_id,
            'filename': session_data.get('filename', ''),
            'status': session_data.get('status', '')
        })
    return jsonify(session_list)

@app.route('/api/status/<session_id>', methods=['GET'])
def get_status(session_id):
    """Get the status of a processing session."""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    return jsonify({
        'status': sessions[session_id]['status'],
        'progress': sessions[session_id].get('progress', 0)
    })

@app.route('/api/results/<session_id>', methods=['GET'])
def get_results(session_id):
    """Get the results of a processing session."""
    if session_id not in sessions:
        return jsonify({'error': 'Session not found'}), 404
    
    session_data = sessions[session_id]
    
    # If still processing, return progress info
    if session_data['status'] == 'processing':
        return jsonify({
            'status': 'processing',
            'progress': session_data.get('progress', 0)
        })
    
    # Return the full results
    return jsonify({
        'status': session_data['status'],
        'transcript': session_data.get('transcript', ''),
        'summary': session_data.get('summary'),
        'action_items': session_data.get('action_items'),
        'sentiment': session_data.get('sentiment')
    })

# Socket.IO events
@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print('Client disconnected')

@socketio.on('start_stream')
def handle_start_stream(data):
    """Handle the start of audio streaming."""
    print('Streaming started')
    
    # Create a new session for this streaming session
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        'status': 'streaming',
        'transcript': '',
        'audio_chunks': [],
        'summary': None,
        'action_items': None,
        'sentiment': None
    }
    
    # Send the session ID back to the client
    emit('session_created', {'session_id': session_id})

@socketio.on('audio_chunk')
def handle_audio_chunk(data):
    """Process incoming audio chunk during streaming."""
    if 'session_id' not in data:
        emit('error', {'message': 'No session ID provided'})
        return
    
    session_id = data['session_id']
    if session_id not in sessions:
        emit('error', {'message': 'Invalid session ID'})
        return
    
    # Decode the base64 audio data
    try:
        audio_data = base64.b64decode(data['audio'])
        
        # Store the audio chunk
        sessions[session_id]['audio_chunks'].append(audio_data)
        
        # Process the audio chunk for transcription
        result = transcription_service.transcribe_chunk(audio_data)
        
        if result['status'] == 'success':
            # Update the transcript
            sessions[session_id]['transcript'] += ' ' + result['text']
            
            # Send the transcription update to the client
            emit('transcription_update', {
                'text': result['text'],
                'final': False
            })
        else:
            # Send an error message
            emit('error', {'message': result.get('error', 'Error processing audio chunk')})
    
    except Exception as e:
        print(f"Error processing audio chunk: {e}")
        emit('error', {'message': f'Error processing audio chunk: {e}'})

@socketio.on('stop_stream')
def handle_stop_stream(data):
    """Handle the end of audio streaming."""
    if 'session_id' not in data:
        emit('error', {'message': 'No session ID provided'})
        return
    
    session_id = data['session_id']
    if session_id not in sessions:
        emit('error', {'message': 'Invalid session ID'})
        return
    
    # Update session status
    sessions[session_id]['status'] = 'processing'
    
    # Start processing in a background thread
    processing_thread = threading.Thread(
        target=process_stream_results,
        args=(session_id,)
    )
    processing_thread.daemon = True
    processing_thread.start()
    
    # Notify client that processing has started
    emit('processing_started', {'session_id': session_id})

@socketio.on('process_file')
def handle_process_file(data):
    """Handle a request to process an uploaded file."""
    print(f"Process file request received: {data}")
    
    if 'filename' not in data:
        print("Error: No filename provided in the request")
        emit('error', {'message': 'No filename provided'})
        return
    
    filename = data['filename']
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    print(f"Looking for file at: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"Error: File not found at {filepath}")
        emit('error', {'message': f'File not found at {filepath}'})
        return
        
    print(f"File found, proceeding with processing: {filepath}")
    
    # Create a new session for this file
    session_id = str(uuid.uuid4())
    sessions[session_id] = {
        'filepath': filepath,
        'filename': filename,
        'status': 'processing',
        'transcript': '',
        'summary': None,
        'action_items': None,
        'sentiment': None
    }
    
    # Start processing in a background thread
    processing_thread = threading.Thread(
        target=process_audio_file,
        args=(session_id, filepath)
    )
    processing_thread.daemon = True
    processing_thread.start()
    
    # Send the session ID back to the client
    emit('session_created', {'session_id': session_id})

# Processing functions
def process_audio_file(session_id, filepath):
    """Process an uploaded audio file.
    
    Args:
        session_id (str): Session ID
        filepath (str): Path to the audio file
    """
    print(f"Starting to process file: {filepath} for session: {session_id}")
    try:
        # Debug: Check if file exists
        if not os.path.exists(filepath):
            print(f"ERROR: File not found at {filepath}")
            return
        # Update session status
        sessions[session_id]['status'] = 'transcribing'
        sessions[session_id]['progress'] = 10
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'transcribing',
            'progress': 10
        })
        
        # Transcribe the audio file
        transcription_result = transcription_service.transcribe_file(filepath)
        
        if transcription_result['status'] != 'success':
            sessions[session_id]['status'] = 'error'
            sessions[session_id]['error'] = transcription_result.get('error', 'Transcription failed')
            socketio.emit('status_update', {
                'session_id': session_id,
                'status': 'error',
                'error': sessions[session_id]['error']
            })
            return
        
        # Store the transcript
        transcript = transcription_result['text']
        sessions[session_id]['transcript'] = transcript
        sessions[session_id]['progress'] = 40
        # In process_audio_file function
        print(f"Emitting transcription_complete with text: {transcript[:100]}...")
        socketio.emit('transcription_complete', {
            'session_id': session_id,
            'text': transcript
        })
        print("Emission complete")
        
        # Generate summary
        sessions[session_id]['status'] = 'summarizing'
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'summarizing',
            'progress': 50
        })
        
        summary_result = summarization_service.summarize(transcript)
        
        if summary_result['status'] == 'success':
            sessions[session_id]['summary'] = summary_result
            sessions[session_id]['progress'] = 60
            socketio.emit('summary_update', {
                'session_id': session_id,
                'summary': summary_result
            })
        
        # Extract action items
        sessions[session_id]['status'] = 'extracting_actions'
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'extracting_actions',
            'progress': 70
        })
        
        action_items_result = action_items_service.extract_action_items(transcript)
        
        if action_items_result['status'] == 'success':
            sessions[session_id]['action_items'] = action_items_result
            sessions[session_id]['progress'] = 80
            socketio.emit('action_items_update', {
                'session_id': session_id,
                'action_items': action_items_result
            })
        
        # Analyze sentiment
        sessions[session_id]['status'] = 'analyzing_sentiment'
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'analyzing_sentiment',
            'progress': 90
        })
        
        sentiment_result = sentiment_service.analyze_sentiment(transcript)
        
        if sentiment_result['status'] == 'success':
            sessions[session_id]['sentiment'] = sentiment_result
            sessions[session_id]['progress'] = 100
            socketio.emit('sentiment_update', {
                'session_id': session_id,
                'sentiment': sentiment_result
            })
        
        # Update session status
        sessions[session_id]['status'] = 'completed'
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'completed',
            'progress': 100
        })
        
    except Exception as e:
        print(f"Error processing audio file: {e}")
        sessions[session_id]['status'] = 'error'
        sessions[session_id]['error'] = str(e)
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'error',
            'error': str(e)
        })

def process_stream_results(session_id):
    """Process the results of a streaming session.
    
    Args:
        session_id (str): Session ID
    """
    try:
        if session_id not in sessions:
            return
        
        # Get the transcript from the session
        transcript = sessions[session_id]['transcript']
        
        if not transcript:
            sessions[session_id]['status'] = 'error'
            sessions[session_id]['error'] = 'No transcript generated'
            socketio.emit('status_update', {
                'session_id': session_id,
                'status': 'error',
                'error': 'No transcript generated'
            })
            return
        
        # Generate summary
        sessions[session_id]['status'] = 'summarizing'
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'summarizing',
            'progress': 50
        })
        
        summary_result = summarization_service.summarize(transcript)
        
        if summary_result['status'] == 'success':
            sessions[session_id]['summary'] = summary_result
            socketio.emit('summary_update', {
                'session_id': session_id,
                'summary': summary_result
            })
        
        # Extract action items
        sessions[session_id]['status'] = 'extracting_actions'
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'extracting_actions',
            'progress': 70
        })
        
        action_items_result = action_items_service.extract_action_items(transcript)
        
        if action_items_result['status'] == 'success':
            sessions[session_id]['action_items'] = action_items_result
            socketio.emit('action_items_update', {
                'session_id': session_id,
                'action_items': action_items_result
            })
        
        # Analyze sentiment
        sessions[session_id]['status'] = 'analyzing_sentiment'
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'analyzing_sentiment',
            'progress': 90
        })
        
        sentiment_result = sentiment_service.analyze_sentiment(transcript)
        
        if sentiment_result['status'] == 'success':
            sessions[session_id]['sentiment'] = sentiment_result
            socketio.emit('sentiment_update', {
                'session_id': session_id,
                'sentiment': sentiment_result
            })
        
        # Update session status
        sessions[session_id]['status'] = 'completed'
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'completed',
            'progress': 100
        })
        
    except Exception as e:
        print(f"Error processing stream results: {e}")
        sessions[session_id]['status'] = 'error'
        sessions[session_id]['error'] = str(e)
        socketio.emit('status_update', {
            'session_id': session_id,
            'status': 'error',
            'error': str(e)
        })

if __name__ == '__main__':
    # Ensure upload directory exists
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Run the application
    socketio.run(app, debug=app.config['DEBUG'])