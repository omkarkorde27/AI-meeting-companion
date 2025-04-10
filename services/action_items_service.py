import logging
import re
import nltk
from nltk.tokenize import sent_tokenize
from config import current_config as config
from typing import List, Dict, Optional, Any
from enum import Enum
import json
import os

# Import OpenAI client for the extraction
try:
    import instructor
    from openai import OpenAI
    from pydantic import BaseModel, Field
    INSTRUCTOR_AVAILABLE = True
except ImportError:
    INSTRUCTOR_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Download NLTK resources if not already downloaded
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

# Define data models for structured extraction
if INSTRUCTOR_AVAILABLE:
    class TaskPriority(str, Enum):
        LOW = "low"
        MEDIUM = "medium" 
        HIGH = "high"
        CRITICAL = "critical"
        UNDEFINED = "undefined"

    class TaskStatus(str, Enum):
        NOT_STARTED = "not_started"
        IN_PROGRESS = "in_progress"
        COMPLETED = "completed"
        BLOCKED = "blocked"
        UNDEFINED = "undefined"

    class Speaker(BaseModel):
        """Information about a meeting participant"""
        name: str = Field(description="Speaker's name or identifier")
        role: Optional[str] = Field(None, description="Speaker's role or department if mentioned")
        
    class ActionItem(BaseModel):
        """Represents a single action item extracted from meeting transcript"""
        task_description: str = Field(description="Clear description of what needs to be done")
        assignee: Optional[str] = Field(None, description="Person or team responsible for the task")
        assigner: Optional[str] = Field(None, description="Person who assigned or requested the task")
        deadline: Optional[str] = Field(None, description="When the task should be completed (date or relative time)")
        priority: TaskPriority = Field(TaskPriority.UNDEFINED, description="Priority level of the task")
        status: TaskStatus = Field(TaskStatus.NOT_STARTED, description="Current status of the task")
        timestamp: Optional[str] = Field(None, description="Approximate time in the meeting when this was mentioned")
        context: Optional[str] = Field(None, description="Additional context or notes about the task")
        confidence: float = Field(ge=0, le=1, description="Confidence score for this extraction")
        transcript_snippet: Optional[str] = Field(None, description="The exact portion of the transcript where this task was mentioned")

    class ActionItemExtraction(BaseModel):
        """Collection of action items extracted from a meeting transcript"""
        meeting_title: Optional[str] = Field(None, description="Title or subject of the meeting if mentioned")
        meeting_date: Optional[str] = Field(None, description="Date when the meeting occurred")
        participants: List[Speaker] = Field(default_factory=list, description="List of identified speakers in the meeting")
        action_items: List[ActionItem] = Field(description="List of action items extracted from the transcript")
        decisions: List[str] = Field(
            default_factory=list, 
            description="Key decisions made during the meeting"
        )
        unresolved_mentions: List[str] = Field(
            default_factory=list,
            description="Potential action items that couldn't be clearly identified"
        )
        extraction_summary: str = Field(description="Brief summary of the action items extracted")


class ActionItemsService:
    """Service for extracting action items from text."""
    
    def __init__(self, model=None):
        """Initialize the action items extraction service.
        
        Args:
            model (str, optional): Model to use for extraction. Defaults to None.
        """
        self.model = model or "ai_powered"  # Default to AI-powered approach if available
        
        # Initialize OpenAI client with instructor if available
        self.openai_client = None
        self.use_instructor = False
        
        # Check if we have OpenAI API key and instructor available
        if INSTRUCTOR_AVAILABLE and config.OPENAI_API_KEY:
            try:
                self.openai_client = instructor.patch(OpenAI(api_key=config.OPENAI_API_KEY))
                self.use_instructor = True
                logger.info("Using OpenAI with instructor for enhanced action item extraction")
            except Exception as e:
                logger.error(f"Error initializing OpenAI client: {e}")
                self.model = "rule_based"
        else:
            logger.info("OpenAI or instructor not available, using rule-based extraction")
            self.model = "rule_based"
            
        # System prompt for AI-powered extraction
        self.system_prompt = """
        You are an AI assistant specialized in extracting action items, tasks, and responsibilities from meeting transcripts.

        Your primary goal is to identify:
        1. All meeting participants and their roles when possible
        2. Tasks and action items committed to or assigned during the meeting
        3. Who assigned each task and who is responsible for completing it
        4. When tasks need to be completed (deadlines)
        5. Key decisions made during the meeting

        Guidelines for transcript analysis:
        - Pay special attention to verbal commitments ("I'll handle that", "I can do that by Friday")
        - Notice when tasks are assigned to others ("John, can you take care of this?", "Sarah should prepare the report")
        - Be aware of language that indicates consensus on future actions ("So we agree that...")
        - Capture both explicit deadlines ("by next Tuesday") and implicit ones ("before the next meeting")
        - Include the transcript snippet where the action item was mentioned
        - Identify speakers correctly, even when the transcript format varies
        - Distinguish between general discussion and actual commitments
        - Note when meeting participants mention previous incomplete action items
        - Pay close attention to meeting wrap-up sections where tasks are often summarized

        For the timestamp field, include the time marker from the transcript if available, or note the approximate position (beginning, middle, end of meeting).

        For ambiguous mentions that might be action items but lack clarity on who/what/when, include these in the unresolved_mentions list.

        For decisions, capture clear conclusions the group reached that don't require specific actions but represent important outcomes.

        Analyze the following meeting transcript and extract all action items in the specified structured format.
        """
        
        logger.info(f"Initialized action items extraction service with model: {self.model}")
        
        # Common action item indicators for rule-based approach
        self.action_phrases = [
            "need to", "needs to", "should", "must", "will", "have to", "has to",
            "going to", "assigned to", "responsible for", "take care of", "follow up",
            "by tomorrow", "by next week", "by monday", "by tuesday", "by wednesday",
            "by thursday", "by friday", "by saturday", "by sunday", "by the end of",
            "action item", "task", "todo", "to-do", "to do", "due", "deadline",
            "I'll", "I will", "you'll", "we'll", "they'll", "let's", "can you",
            "could you", "please", "make sure", "ensure", "create", "prepare", "review"
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
            r'next\s+(\w+day)',
            r'this\s+(\w+day)',
            r'(today|tomorrow)',
            r'(\d{1,2})\s*(st|nd|rd|th)\s+of\s+(January|February|March|April|May|June|July|August|September|October|November|December)',
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})',
            r'EOD',
            r'COB',
            r'end of (day|week|month)',
        ]
        
        # For assignee extraction
        self.assignee_patterns = [
            r'([\w\s]+)\s+will',
            r'([\w\s]+)\s+should',
            r'([\w\s]+)\s+needs to',
            r'assigned to\s+([\w\s]+)',
            r'([\w\s]+)\s+is responsible',
            r'([\w\s]+)\s+to take care of',
            r'([\w\s]+)\s+is going to',
            r'([\w\s]+)\s+has to',
            r'([\w\s]+)\s+needs to',
            r'([\w\s]+),\s+can you',
            r'([\w\s]+)\s+agreed to',
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
            
            # Preprocess the transcript
            transcript_data = self._preprocess_transcript(text)
            
            # Choose extraction method based on available capabilities
            if self.use_instructor and self.model == "ai_powered":
                action_items_data = self._ai_powered_extraction(text, transcript_data)
            else:
                # Fallback to rule-based
                action_items_data = self._rule_based_extraction(text)
            
            # Format for the application's expected output
            formatted_items = []
            for item in action_items_data.get('action_items', []):
                formatted_item = {
                    'task': item.get('task_description', ''),
                    'assignee': item.get('assignee'),
                    'deadline': item.get('deadline'),
                    'priority': item.get('priority', 'undefined'),
                    'status': item.get('status', 'not_started'),
                    'context': item.get('context')
                }
                formatted_items.append(formatted_item)
            
            logger.info(f"Extracted {len(formatted_items)} action items")
            
            return {
                'items': formatted_items,
                'status': 'success',
                'model': self.model,
                'meeting_title': action_items_data.get('meeting_title'),
                'meeting_date': action_items_data.get('meeting_date'),
                'decisions': action_items_data.get('decisions', []),
                'participants': action_items_data.get('participants', [])
            }
            
        except Exception as e:
            logger.error(f"Error extracting action items: {e}")
            return {'error': f'Error extracting action items: {e}', 'status': 'error'}
    
    def _preprocess_transcript(self, transcript_text):
        """
        Preprocess a transcript to identify speakers and structure the content.
        This function handles different transcription formats.
        """
        # Detect if the transcript has timestamps and speaker information
        lines = transcript_text.strip().split('\n')
        transcript_data = {
            "processed_text": transcript_text,
            "has_timestamps": False,
            "has_speakers": False,
            "speaker_names": []
        }
        
        # Check for typical Zoom transcript format patterns
        speaker_set = set()
        for line in lines:
            # Common Zoom transcript format: "10:15:30 Speaker Name: Text here"
            if ':' in line:
                parts = line.split(':', 2)
                if len(parts) >= 3:
                    potential_speaker = parts[1].strip()
                    if len(potential_speaker) > 0 and len(potential_speaker) < 30:  # Reasonable name length
                        speaker_set.add(potential_speaker)
                        transcript_data["has_speakers"] = True
                    
                    # Check if first part could be a timestamp
                    if ':' in parts[0] and any(c.isdigit() for c in parts[0]):
                        transcript_data["has_timestamps"] = True
        
        transcript_data["speaker_names"] = list(speaker_set)
        return transcript_data
    
    def _ai_powered_extraction(self, text, transcript_data):
        """Extract action items using AI-powered approach with structured output.
        
        Args:
            text (str): Text to analyze
            transcript_data (dict): Preprocessed transcript information
            
        Returns:
            dict: Dict representation of extracted action items
        """
        try:
            # Use transcript metadata to guide the extraction
            transcript_info = {
                "has_speakers": transcript_data["has_speakers"],
                "has_timestamps": transcript_data["has_timestamps"],
                "detected_speakers": transcript_data["speaker_names"]
            }
            
            # Use OpenAI with instructor for structured output
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Use an appropriate model that's available
                response_model=ActionItemExtraction,
                temperature=0,
                max_retries=2,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": f"Transcript metadata: {json.dumps(transcript_info)}\n\n{text}"}
                ]
            )
            
            # Convert to dict for processing
            return response.model_dump()
            
        except Exception as e:
            logger.error(f"Error in AI-powered extraction: {e}")
            # Fallback to rule-based extraction
            return self._rule_based_extraction(text)
    
    def _rule_based_extraction(self, text):
        """Extract action items using rule-based approach.
        
        Args:
            text (str): Text to analyze
            
        Returns:
            dict: Dictionary with action items and related information
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
                    'task_description': task,
                    'assignee': assignee,
                    'deadline': deadline,
                    'priority': TaskPriority.UNDEFINED.value if INSTRUCTOR_AVAILABLE else "undefined",
                    'status': TaskStatus.NOT_STARTED.value if INSTRUCTOR_AVAILABLE else "not_started",
                    'confidence': 0.7,  # Medium confidence for rule-based extraction
                    'transcript_snippet': task
                })
        
        # Create result dict with similar structure to AI-powered result
        return {
            'action_items': action_items,
            'meeting_title': None,
            'meeting_date': None,
            'decisions': [],
            'participants': [],
            'extraction_summary': f"Extracted {len(action_items)} action items using rule-based approach."
        }
    
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
                # Return the first capturing group or combine groups for dates
                if len(match.groups()) > 1 and "January|February|March|April|May|June|July|August|September|October|November|December" in pattern:
                    # For patterns with month and date
                    return f"{match.group(1)} {match.group(2)}"
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