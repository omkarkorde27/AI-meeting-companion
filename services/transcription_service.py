import os
import logging
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
from config import current_config as config
from openai import OpenAI

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranscriptionService:
    """Service for transcribing audio to text using OpenAI's Whisper"""
    
    def __init__(self, model=None):
        """Initialize the transcription service.
        
        Args:
            model (str, optional): Model to use for transcription. Defaults to None.
        """
        self.model = model or config.TRANSCRIPTION_MODEL
        self.client = OpenAI(api_key=config.OPENAI_API_KEY)
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
            # Convert non-supported files to MP3 format which is well supported by Whisper
            if file_ext not in ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm']:
                logger.info(f"Converting {file_ext} to MP3 for processing")
                audio = AudioSegment.from_file(file_path)
                
                # Create a temporary MP3 file
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                audio.export(temp_path, format='mp3')
                audio_path = temp_path
            else:
                audio_path = file_path

            whisper_model = self._get_whisper_model()
            
            # Perform transcription
            with open(audio_path, "rb") as audio_file:
                response = self.client.audio.transcriptions.create(
                    model=whisper_model,
                    file=audio_file,
                    response_format="text"
                )
                
                logger.info("Transcription completed successfully")
                
                # Clean up temporary file if created
                if file_ext not in ['.mp3', '.mp4', '.mpeg', '.mpga', '.m4a', '.wav', '.webm'] and 'temp_path' in locals():
                    os.unlink(temp_path)
                
                return {
                    'text': response,
                    'status': 'success',
                    'model': whisper_model
                }
                
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
            with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
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

    def _get_whisper_model(self):
        """Get the appropriate Whisper model based on configuration.
        
        Returns:
            str: Whisper model name
        """
        # Map configuration model settings to Whisper model names
        model_mapping = {
            'whisper-small': 'whisper-1',   # Use the latest Whisper model
            'whisper-medium': 'whisper-1',  # OpenAI API currently only exposes one model
            'whisper-large': 'whisper-1',   # but we keep the mapping for future options
            'default': 'whisper-1'
        }

        return model_mapping.get(self.model, 'whisper-1')
# Create a default instance
transcription_service = TranscriptionService()