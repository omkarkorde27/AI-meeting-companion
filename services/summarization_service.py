import logging
import re
import nltk
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.cluster.util import cosine_distance
import numpy as np
import networkx as nx
from config import current_config as config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Download NLTK resources if not already downloaded
try:
    nltk.data.find('tokenizers/punkt')
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

class SummarizationService:
    """Service for generating summaries from text."""
    
    def __init__(self, model=None):
        """Initialize the summarization service.
        
        Args:
            model (str, optional): Model to use for summarization. Defaults to None.
        """
        self.model = model or config.SUMMARIZATION_MODEL
        logger.info(f"Initialized summarization service with model: {self.model}")
    
    def summarize(self, text, max_sentences=5):
        """Generate a summary from text.
        
        Args:
            text (str): Text to summarize
            max_sentences (int, optional): Maximum number of sentences in summary. Defaults to 5.
            
        Returns:
            dict: Summary result with text and metadata
        """
        logger.info(f"Generating summary with max {max_sentences} sentences")
        
        try:
            if not text or len(text.strip()) == 0:
                return {'error': 'No text provided for summarization', 'status': 'error'}
            
            # For the initial implementation, we'll use a text rank algorithm
            # In a production environment, you might want to use a more sophisticated model
            
            if self.model == 'text_rank':
                summary = self._text_rank_summarize(text, max_sentences)
            else:
                # Default to text rank
                summary = self._text_rank_summarize(text, max_sentences)
            
            # Generate TL;DR (shorter summary)
            tldr = self._generate_tldr(text)
            
            # Extract key points as bullet points
            key_points = self._extract_key_points(text)
            
            logger.info("Summary generation completed successfully")
            
            return {
                'summary': summary,
                'tldr': tldr,
                'key_points': key_points,
                'status': 'success',
                'model': self.model
            }
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {'error': f'Error generating summary: {e}', 'status': 'error'}
    
    def _text_rank_summarize(self, text, max_sentences=5):
        """Summarize text using TextRank algorithm.
        
        Args:
            text (str): Text to summarize
            max_sentences (int, optional): Maximum number of sentences. Defaults to 5.
            
        Returns:
            str: Summarized text
        """
        # Clean and tokenize text
        clean_text = re.sub(r'\s+', ' ', text).strip()
        sentences = sent_tokenize(clean_text)
        
        # If we have fewer sentences than requested, return the original text
        if len(sentences) <= max_sentences:
            return text
        
        # Create similarity matrix
        stop_words = set(stopwords.words('english'))
        similarity_matrix = self._build_similarity_matrix(sentences, stop_words)
        
        # Apply PageRank algorithm to find important sentences
        nx_graph = nx.from_numpy_array(similarity_matrix)
        scores = nx.pagerank(nx_graph)
        
        # Sort sentences by score and select top ones
        ranked_sentences = sorted([(scores[i], sentences[i]) for i in range(len(sentences))], 
                                  reverse=True)
        
        # Get top sentences and arrange them in original order
        top_sentence_indices = [sentences.index(ranked_sentences[i][1]) for i in range(min(max_sentences, len(ranked_sentences)))]
        top_sentence_indices.sort()
        
        # Combine sentences into a summary
        summary = ' '.join([sentences[i] for i in top_sentence_indices])
        
        return summary
    
    def _build_similarity_matrix(self, sentences, stop_words):
        """Build a similarity matrix for sentences.
        
        Args:
            sentences (list): List of sentences
            stop_words (set): Set of stop words to ignore
            
        Returns:
            numpy.ndarray: Similarity matrix
        """
        # Create an empty similarity matrix
        similarity_matrix = np.zeros((len(sentences), len(sentences)))
        
        for i in range(len(sentences)):
            for j in range(len(sentences)):
                if i != j:
                    similarity_matrix[i][j] = self._sentence_similarity(
                        sentences[i], sentences[j], stop_words)
                    
        return similarity_matrix
    
    def _sentence_similarity(self, sent1, sent2, stop_words):
        """Calculate the cosine similarity between two sentences.
        
        Args:
            sent1 (str): First sentence
            sent2 (str): Second sentence
            stop_words (set): Set of stop words to ignore
            
        Returns:
            float: Similarity score
        """
        words1 = [word.lower() for word in sent1.split() if word.lower() not in stop_words]
        words2 = [word.lower() for word in sent2.split() if word.lower() not in stop_words]
        
        # Create a set of all unique words
        all_words = list(set(words1 + words2))
        
        # Create word vectors
        vector1 = [1 if word in words1 else 0 for word in all_words]
        vector2 = [1 if word in words2 else 0 for word in all_words]
        
        # Calculate cosine similarity
        if sum(vector1) > 0 and sum(vector2) > 0:
            return 1 - cosine_distance(vector1, vector2)
        else:
            return 0
    
    def _generate_tldr(self, text, max_words=30):
        """Generate a very short TL;DR summary.
        
        Args:
            text (str): Text to summarize
            max_words (int, optional): Maximum words in TL;DR. Defaults to 30.
            
        Returns:
            str: TL;DR summary
        """
        # Clean text
        clean_text = re.sub(r'\s+', ' ', text).strip()
        sentences = sent_tokenize(clean_text)
        
        # If very short text, return the first sentence
        if len(sentences) <= 1:
            words = sentences[0].split()
            if len(words) <= max_words:
                return sentences[0]
            else:
                return ' '.join(words[:max_words]) + '...'
        
        # Apply TextRank to get the most important sentence
        stop_words = set(stopwords.words('english'))
        similarity_matrix = self._build_similarity_matrix(sentences, stop_words)
        nx_graph = nx.from_numpy_array(similarity_matrix)
        scores = nx.pagerank(nx_graph)
        
        # Get the most important sentence
        most_important = sorted([(scores[i], sentences[i]) for i in range(len(sentences))], 
                               reverse=True)[0][1]
        
        # Limit to max_words
        words = most_important.split()
        if len(words) <= max_words:
            return most_important
        else:
            return ' '.join(words[:max_words]) + '...'
    
    def _extract_key_points(self, text, max_points=5):
        """Extract key points as bullet points.
        
        Args:
            text (str): Text to analyze
            max_points (int, optional): Maximum number of key points. Defaults to 5.
            
        Returns:
            list: List of key points
        """
        # Use the same TextRank approach but return individual sentences
        clean_text = re.sub(r'\s+', ' ', text).strip()
        sentences = sent_tokenize(clean_text)
        
        if len(sentences) <= max_points:
            return sentences
        
        stop_words = set(stopwords.words('english'))
        similarity_matrix = self._build_similarity_matrix(sentences, stop_words)
        nx_graph = nx.from_numpy_array(similarity_matrix)
        scores = nx.pagerank(nx_graph)
        
        # Get top sentences
        ranked_sentences = sorted([(scores[i], sentences[i]) for i in range(len(sentences))], 
                                 reverse=True)
        
        key_points = [ranked_sentences[i][1] for i in range(min(max_points, len(ranked_sentences)))]
        
        return key_points

# Create a default instance
summarization_service = SummarizationService()