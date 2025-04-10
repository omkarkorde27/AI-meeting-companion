import os
import logging
import speech_recognition as sr
from pydub import AudioSegment
import tempfile
import subprocess
import json
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
        
        try:
            # Always convert to MP3 format for better Whisper compatibility
            logger.info(f"Converting audio to MP3 format for processing")
            try:
                # First attempt: Use pydub
                audio = AudioSegment.from_file(file_path)
                
                # Create a temporary MP3 file
                with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                    temp_path = temp_file.name
                
                audio.export(temp_path, format='mp3')
                
            except Exception as e:
                logger.warning(f"Pydub conversion failed: {e}. Trying ffmpeg directly.")
                
                # Second attempt: Use ffmpeg directly
                try:
                    # Create a temporary MP3 file
                    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as temp_file:
                        temp_path = temp_file.name
                    
                    # Run ffmpeg to convert the file
                    ffmpeg_cmd = [
                        'ffmpeg', '-i', file_path, 
                        '-ac', '1',  # Convert to mono
                        '-ar', '16000',  # 16kHz sample rate
                        '-c:a', 'libmp3lame',  # MP3 codec
                        '-q:a', '4',  # Quality setting
                        temp_path
                    ]
                    
                    result = subprocess.run(
                        ffmpeg_cmd, 
                        capture_output=True, 
                        text=True
                    )
                    
                    if result.returncode != 0:
                        logger.error(f"FFmpeg conversion failed: {result.stderr}")
                        # If conversion fails, try using the original file
                        temp_path = file_path
                    
                except Exception as ffmpeg_error:
                    logger.error(f"FFmpeg direct conversion failed: {ffmpeg_error}")
                    # If all conversions fail, use the original file
                    temp_path = file_path

            # Verify the file exists
            if not os.path.exists(temp_path):
                logger.error(f"Converted file not found: {temp_path}")
                return {'error': 'Converted file not found', 'status': 'error'}
                
            # Check file size - Whisper needs at least some content
            file_size = os.path.getsize(temp_path)
            if file_size < 100:  # Very small files are likely empty/corrupt
                logger.warning(f"File too small ({file_size} bytes), possibly empty audio")
                return {'error': 'Audio file too small or empty', 'status': 'error'}

            whisper_model = self._get_whisper_model()
            
            # Perform transcription
            with open(temp_path, "rb") as audio_file:
                try:
                    response = self.client.audio.transcriptions.create(
                        model=whisper_model,
                        file=audio_file,
                        response_format="text"
                    )
                    
                    logger.info("Transcription completed successfully")
                    
                    # Clean up temporary file if created
                    if temp_path != file_path and os.path.exists(temp_path):
                        os.unlink(temp_path)
                    
                    # Make sure we have text content
                    text = response if response else ""
                    
                    return {
                        'text': text,
                        'status': 'success',
                        'model': whisper_model
                    }
                except Exception as transcription_error:
                    logger.error(f"Error in Whisper API call: {transcription_error}")
                    
                    # Try one more fallback - convert to WAV format
                    try:
                        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as wav_temp:
                            wav_path = wav_temp.name
                        
                        # Run ffmpeg to convert to WAV
                        ffmpeg_cmd = [
                            'ffmpeg', '-i', temp_path if temp_path != file_path else file_path,
                            '-ac', '1',  # Convert to mono
                            '-ar', '16000',  # 16kHz sample rate
                            wav_path
                        ]
                        
                        result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
                        
                        if result.returncode == 0:
                            # Try Whisper API again with WAV
                            with open(wav_path, "rb") as wav_file:
                                response = self.client.audio.transcriptions.create(
                                    model=whisper_model,
                                    file=wav_file,
                                    response_format="text"
                                )
                                
                                logger.info("Transcription with WAV completed successfully")
                                
                                # Clean up temporary files
                                if temp_path != file_path and os.path.exists(temp_path):
                                    os.unlink(temp_path)
                                if os.path.exists(wav_path):
                                    os.unlink(wav_path)
                                
                                return {
                                    'text': response if response else "",
                                    'status': 'success',
                                    'model': whisper_model
                                }
                        else:
                            logger.error(f"WAV conversion failed: {result.stderr}")
                            raise Exception(f"WAV conversion failed: {result.stderr}")
                    
                    except Exception as wav_error:
                        logger.error(f"WAV fallback failed: {wav_error}")
                        # Clean up temporary files
                        if temp_path != file_path and os.path.exists(temp_path):
                            os.unlink(temp_path)
                        if 'wav_path' in locals() and os.path.exists(wav_path):
                            os.unlink(wav_path)
                        
                        # Re-raise the original error
                        raise transcription_error
                
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            
            # Clean up any temporary files
            if 'temp_path' in locals() and temp_path != file_path and os.path.exists(temp_path):
                os.unlink(temp_path)
            if 'wav_path' in locals() and os.path.exists(wav_path):
                os.unlink(wav_path)
                
            return {'error': f'Error transcribing audio: {e}', 'status': 'error'}
    
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