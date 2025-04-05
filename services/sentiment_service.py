import logging
import re
import nltk
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk.tokenize import sent_tokenize
from config import current_config as config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Download NLTK resources if not already downloaded
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('sentiment/vader_lexicon.zip')
except LookupError:
    nltk.download('punkt')
    nltk.download('vader_lexicon')

class SentimentService:
    """Service for analyzing sentiment in text."""
    
    def __init__(self, model=None):
        """Initialize the sentiment analysis service.
        
        Args:
            model (str, optional): Model to use for sentiment analysis. Defaults to None.
        """
        self.model = model or config.SENTIMENT_MODEL
        self.analyzer = SentimentIntensityAnalyzer()
        logger.info(f"Initialized sentiment analysis service with model: {self.model}")
    
    def analyze_sentiment(self, text, by_speaker=None):
        """Analyze sentiment in text.
        
        Args:
            text (str): Text to analyze
            by_speaker (dict, optional): Text segments by speaker. Defaults to None.
            
        Returns:
            dict: Sentiment analysis results
        """
        logger.info("Analyzing sentiment in text")
        
        try:
            if not text or len(text.strip()) == 0:
                return {'error': 'No text provided for sentiment analysis', 'status': 'error'}
            
            # If we have speaker-separated text, analyze sentiment by speaker
            if by_speaker:
                results = self._analyze_by_speaker(by_speaker)
            else:
                # Analyze sentiment for the whole text and by segments
                results = self._analyze_text(text)
            
            logger.info("Sentiment analysis completed successfully")
            
            return {
                'sentiments': results,
                'status': 'success',
                'model': self.model
            }
            
        except Exception as e:
            logger.error(f"Error analyzing sentiment: {e}")
            return {'error': f'Error analyzing sentiment: {e}', 'status': 'error'}
    
    def _analyze_text(self, text):
        """Analyze sentiment in the entire text and by segments.
        
        Args:
            text (str): Text to analyze
            
        Returns:
            list: Sentiment analysis results by segment
        """
        # Clean text
        clean_text = re.sub(r'\s+', ' ', text).strip()
        
        # Get overall sentiment
        overall_sentiment = self.analyzer.polarity_scores(clean_text)
        
        # Split text into segments (sentences or paragraphs)
        sentences = sent_tokenize(clean_text)
        
        # Analyze sentiment for each segment
        results = []
        
        # Add overall sentiment
        results.append({
            'segment': 'overall',
            'text': clean_text[:100] + ('...' if len(clean_text) > 100 else ''),
            'score': overall_sentiment['compound'],
            'positive': overall_sentiment['pos'],
            'neutral': overall_sentiment['neu'],
            'negative': overall_sentiment['neg']
        })
        
        # Add sentiment for each segment
        for i, sentence in enumerate(sentences):
            if len(sentence.split()) < 3:  # Skip very short sentences
                continue
                
            sentiment = self.analyzer.polarity_scores(sentence)
            
            results.append({
                'segment': f'segment_{i+1}',
                'text': sentence,
                'score': sentiment['compound'],
                'positive': sentiment['pos'],
                'neutral': sentiment['neu'],
                'negative': sentiment['neg']
            })
        
        return results
    
    def _analyze_by_speaker(self, by_speaker):
        """Analyze sentiment by speaker.
        
        Args:
            by_speaker (dict): Text segments by speaker
            
        Returns:
            list: Sentiment analysis results by speaker
        """
        results = []
        
        for speaker, segments in by_speaker.items():
            # Combine all segments for this speaker
            speaker_text = ' '.join(segments)
            
            # Get overall sentiment for this speaker
            speaker_sentiment = self.analyzer.polarity_scores(speaker_text)
            
            # Add to results
            results.append({
                'speaker': speaker,
                'text': speaker_text[:100] + ('...' if len(speaker_text) > 100 else ''),
                'score': speaker_sentiment['compound'],
                'positive': speaker_sentiment['pos'],
                'neutral': speaker_sentiment['neu'],
                'negative': speaker_sentiment['neg']
            })
            
            # Analyze individual segments for this speaker
            for i, segment in enumerate(segments):
                if len(segment.split()) < 3:  # Skip very short segments
                    continue
                    
                segment_sentiment = self.analyzer.polarity_scores(segment)
                
                results.append({
                    'speaker': speaker,
                    'segment': f'{speaker}_segment_{i+1}',
                    'text': segment,
                    'score': segment_sentiment['compound'],
                    'positive': segment_sentiment['pos'],
                    'neutral': segment_sentiment['neu'],
                    'negative': segment_sentiment['neg']
                })
        
        return results

# Create a default instance
sentiment_service = SentimentService()