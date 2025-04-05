import logging
import re
import nltk
from nltk.tokenize import sent_tokenize
from config import current_config as config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Download NLTK resources if not already downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

class ActionItemsService:
    """Service for extracting action items from text."""
    
    def __init__(self, model=None):
        """Initialize the action items extraction service.
        
        Args:
            model (str, optional): Model to use for extraction. Defaults to None.
        """
        self.model = model or "rule_based"  # Default to rule-based approach
        logger.info(f"Initialized action items extraction service with model: {self.model}")
        
        # Common action item indicators
        self.action_phrases = [
            "need to", "needs to", "should", "must", "will", "have to", "has to",
            "going to", "assigned to", "responsible for", "take care of", "follow up",
            "by tomorrow", "by next week", "by monday", "by tuesday", "by wednesday",
            "by thursday", "by friday", "by saturday", "by sunday", "by the end of",
            "action item", "task", "todo"
        ]
        
        # For deadline extraction
        self.date_patterns = [
            r'by\s+(\w+day)',  # by Monday, by Tuesday, etc.
            r'by\s+(tomorrow|next week|next month)',
            r'by\s+the\s+end\s+of\s+(day|week|month)',
            r'by\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})',
            r'by\s+(\d{1,2}/\d{1,2})',  # by 10/20
            r'due\s+(today|tomorrow|next week)',
            r'due\s+by\s+(\w+day)',
            r'due\s+date\s+is\s+(\w+day)',
            r'deadline\s+is\s+(\w+day|\d{1,2}/\d{1,2})',
        ]
        
        # For assignee extraction
        self.assignee_patterns = [
            r'([\w\s]+)\s+will',
            r'([\w\s]+)\s+should',
            r'([\w\s]+)\s+needs to',
            r'assigned to\s+([\w\s]+)',
            r'([\w\s]+)\s+is responsible',
            r'([\w\s]+)\s+to take care of',
        ]
    
    def extract_action_items(self, text):
        """Extract action items from text.
        
        Args:
            text (str): Text to analyze
            
        Returns:
            dict: Extracted action items with metadata
        """
        logger.info("Extracting action items from text")
        
        try:
            if not text or len(text.strip()) == 0:
                return {'error': 'No text provided for action item extraction', 'status': 'error'}
            
            # For the initial implementation, we'll use a rule-based approach
            if self.model == "rule_based":
                action_items = self._rule_based_extraction(text)
            else:
                # Default to rule-based
                action_items = self._rule_based_extraction(text)
            
            logger.info(f"Extracted {len(action_items)} action items")
            
            return {
                'items': action_items,
                'status': 'success',
                'model': self.model
            }
            
        except Exception as e:
            logger.error(f"Error extracting action items: {e}")
            return {'error': f'Error extracting action items: {e}', 'status': 'error'}
    
    def _rule_based_extraction(self, text):
        """Extract action items using rule-based approach.
        
        Args:
            text (str): Text to analyze
            
        Returns:
            list: List of extracted action items
        """
        # Clean and tokenize text
        clean_text = re.sub(r'\s+', ' ', text).strip()
        sentences = sent_tokenize(clean_text)
        
        action_items = []
        
        for sentence in sentences:
            # Check if the sentence contains an action item indicator
            if any(phrase in sentence.lower() for phrase in self.action_phrases):
                # Extract the basic task
                task = sentence
                
                # Try to extract assignee
                assignee = self._extract_assignee(sentence)
                
                # Try to extract deadline
                deadline = self._extract_deadline(sentence)
                
                # Add to action items list
                action_items.append({
                    'task': task,
                    'assignee': assignee,
                    'deadline': deadline
                })
        
        return action_items
    
    def _extract_deadline(self, sentence):
        """Extract deadline from a sentence.
        
        Args:
            sentence (str): Sentence to analyze
            
        Returns:
            str: Extracted deadline or None
        """
        sentence = sentence.lower()
        
        for pattern in self.date_patterns:
            match = re.search(pattern, sentence)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_assignee(self, sentence):
        """Extract assignee from a sentence.
        
        Args:
            sentence (str): Sentence to analyze
            
        Returns:
            str: Extracted assignee or None
        """
        for pattern in self.assignee_patterns:
            match = re.search(pattern, sentence)
            if match:
                assignee = match.group(1).strip()
                # Filter out common false positives
                if assignee.lower() not in ['we', 'i', 'you', 'they', 'he', 'she', 'it']:
                    return assignee
        
        return None

# Create a default instance
action_items_service = ActionItemsService()