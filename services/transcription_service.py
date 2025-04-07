import os
import logging
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
from config import current_config as config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranscriptionService:
    """Service for transcribing audio to text."""
    
    def __init__(self, model=None):
        """Initialize the transcription service.
        
        Args:
            model (str, optional): Model to use for transcription. Defaults to None.
        """
        self.model = model or config.TRANSCRIPTION_MODEL
        self.recognizer = sr.Recognizer()
        logger.info(f"Initialized transcription service with model: {self.model}")
    
    def transcribe_file(self, file_path):
        """Transcribe an audio file.
        
        Args:
            file_path (str): Path to the audio file
            
        Returns:
            dict: Transcription result with text and metadata
        """
        logger.info(f"Transcribing file: {file_path}")
        print(f"DEBUG: Attempting to transcribe file: {file_path}")
        
        # Check if file exists
        if not os.path.exists(file_path):
            logger.error(f"File not found: {file_path}")
            print(f"ERROR: File not found at {file_path}")
            return {'error': 'File not found', 'status': 'error'}
        
        # Determine the file extension
        file_ext = os.path.splitext(file_path)[1].lower()
        
        try:
            # Convert non-WAV files to WAV
            if file_ext != '.wav':
                logger.info(f"Converting {file_ext} to WAV for processing")
                audio = AudioSegment.from_file(file_path)
                
                # Create a temporary WAV file
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                audio.export(temp_path, format='wav')
                audio_path = temp_path
            else:
                audio_path = file_path
            
            # Perform transcription
            with sr.AudioFile(audio_path) as source:
                audio_data = self.recognizer.record(source)
                
                # Choose the recognition method based on the model
                if self.model == 'google':
                    text = self.recognizer.recognize_google(audio_data)
                elif self.model == 'sphinx':
                    text = self.recognizer.recognize_sphinx(audio_data)
                else:
                    # Default to Google's API
                    text = self.recognizer.recognize_sphinx(audio_data)
                
                logger.info("Transcription completed successfully")
                
                # Clean up temporary file if created
                if file_ext != '.wav' and 'temp_path' in locals():
                    os.unlink(temp_path)
                
                return {
                    'text': text,
                    'status': 'success',
                    'model': self.model
                }
                
        except sr.UnknownValueError:
            logger.error("Speech recognition could not understand audio")
            return {'error': 'Speech recognition could not understand audio', 'status': 'error'}
            
        except sr.RequestError as e:
            logger.error(f"Could not request results from service: {e}")
            return {'error': f'Could not request results from service: {e}', 'status': 'error'}
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return {'error': f'Error transcribing audio: {e}', 'status': 'error'}
    
    def transcribe_chunk(self, audio_chunk):
        """Transcribe a chunk of audio data.
        
        Args:
            audio_chunk (bytes): Audio data chunk
            
        Returns:
            dict: Transcription result with text and metadata
        """
        # This method would be used for real-time transcription
        # For the basic implementation, we'll create a placeholder
        # In a real implementation, you would use a streaming API
        
        logger.info("Processing audio chunk")
        
        try:
            # Save chunk to temporary file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                temp_file.write(audio_chunk)
                temp_path = temp_file.name
            
            # Transcribe the temporary file
            result = self.transcribe_file(temp_path)
            
            # Clean up
            os.unlink(temp_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Error transcribing audio chunk: {e}")
            return {'error': f'Error transcribing audio chunk: {e}', 'status': 'error'}

# Create a default instance
transcription_service = TranscriptionService()