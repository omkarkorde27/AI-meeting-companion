import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    """Base configuration."""
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-for-testing')
    DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', 't', '1', 'yes')
    
    # File upload settings
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'uploads')
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default
    ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'webm', 'mp4', 'm4a'}
    
    # API Keys and services
    # Replace with your actual API keys when deploying
    # AI service API keys (examples)
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    HUGGINGFACE_API_KEY = os.getenv('HUGGINGFACE_API_KEY')
    
    # Model settings
    TRANSCRIPTION_MODEL = os.getenv('TRANSCRIPTION_MODEL', 'default')
    SUMMARIZATION_MODEL = os.getenv('SUMMARIZATION_MODEL', 'default')
    SENTIMENT_MODEL = os.getenv('SENTIMENT_MODEL', 'default')

    @staticmethod
    def init_app(app):
        """Initialize the application with this configuration."""
        # Create upload folder if it doesn't exist
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        
        # Set Flask config from this class
        app.config.from_object(Config)


class DevelopmentConfig(Config):
    """Development environment configuration."""
    DEBUG = True


class ProductionConfig(Config):
    """Production environment configuration."""
    DEBUG = False
    
    # In production, ensure SECRET_KEY is set in environment variables
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Additional production-specific initialization
        assert os.getenv('SECRET_KEY'), "SECRET_KEY environment variable is required in production"


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

# Get current configuration
current_config = config[os.getenv('FLASK_ENV', 'default')]