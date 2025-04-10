import logging
import re
import nltk
from nltk.tokenize import sent_tokenize
from nltk.corpus import stopwords
from nltk.cluster.util import cosine_distance
import numpy as np
import networkx as nx
from config import current_config as config
from typing import List, Dict, Optional, Any, Union
import json
import os

# Import OpenAI client for advanced summarization
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
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('punkt')
    nltk.download('stopwords')

# Define data models for structured summarization
if INSTRUCTOR_AVAILABLE:
    class Topic(BaseModel):
        """Represents a discussion topic identified in the meeting"""
        title: str = Field(description="Short descriptive title for the topic")
        start_time: Optional[str] = Field(None, description="When this topic started being discussed (timestamp if available)")
        end_time: Optional[str] = Field(None, description="When discussion on this topic ended (timestamp if available)")
        speakers: List[str] = Field(default_factory=list, description="People who spoke on this topic")
        summary: str = Field(description="Comprehensive summary of the discussion on this topic")
        key_points: List[str] = Field(description="List of key points discussed within this topic")

    class Decision(BaseModel):
        """Represents a decision made during the meeting"""
        decision: str = Field(description="The decision that was made")
        context: Optional[str] = Field(None, description="Context or reasoning behind the decision")
        related_topic: Optional[str] = Field(None, description="Topic this decision is related to")
        decision_makers: List[str] = Field(default_factory=list, description="People involved in making this decision")

    class MeetingSummary(BaseModel):
        """Complete structured summary of a meeting"""
        meeting_title: Optional[str] = Field(None, description="Title or subject of the meeting if mentioned")
        meeting_date: Optional[str] = Field(None, description="Date when the meeting occurred")
        meeting_duration: Optional[str] = Field(None, description="Duration of the meeting if determinable")
        participants: List[str] = Field(default_factory=list, description="All participants in the meeting")
        tldr: str = Field(description="Ultra-concise 1-2 sentence summary of the entire meeting")
        key_points: List[str] = Field(description="5-10 key points covering the most important aspects of the meeting")
        topics: List[Topic] = Field(description="Detailed breakdown of topics discussed")
        decisions: List[Decision] = Field(default_factory=list, description="Decisions made during the meeting")
        next_steps: List[str] = Field(default_factory=list, description="General next steps mentioned, separate from specific action items")
        notable_quotes: List[str] = Field(default_factory=list, description="Important or representative quotes from the meeting")
        overall_sentiment: Optional[str] = Field(None, description="General sentiment or tone of the meeting")
        minutes: str = Field(description="Comprehensive meeting minutes in a structured, readable format")

class SummarizationService:
    """Enhanced service for generating multi-level summaries from meeting transcripts."""
    
    def __init__(self, model=None):
        """Initialize the summarization service.
        
        Args:
            model (str, optional): Model to use for summarization. Defaults to None.
        """
        self.model = model or config.SUMMARIZATION_MODEL
        
        # Initialize OpenAI client with instructor if available
        self.openai_client = None
        self.use_instructor = False
        
        # Check if we have OpenAI API key and instructor available
        if INSTRUCTOR_AVAILABLE and config.OPENAI_API_KEY:
            try:
                self.openai_client = instructor.patch(OpenAI(api_key=config.OPENAI_API_KEY))
                self.use_instructor = True
                logger.info("Using OpenAI with instructor for enhanced summarization")
                
                # If we have OpenAI available, prefer AI-powered summarization
                if self.model == "text_rank" or self.model == "default":
                    self.model = "ai_powered"
            except Exception as e:
                logger.error(f"Error initializing OpenAI client: {e}")
                # Fall back to text_rank
                self.model = "text_rank" 
        
        logger.info(f"Initialized summarization service with model: {self.model}")
        
        # System prompt for AI-powered summarization
        self.system_prompt = """
        You are an AI assistant specialized in summarizing meeting transcripts at multiple levels of detail.

        For each meeting transcript, you will provide:

        1. TLDR (Too Long; Didn't Read): An ultra-concise 1-2 sentence summary capturing the essence of the meeting.
        
        2. Key Points: 5-10 bullet points covering the most important information discussed. These should be:
           - Comprehensive enough to understand the main ideas without reading the full transcript
           - Organized in a logical flow that follows the meeting structure
           - Focused on substantive content rather than procedural aspects
        
        3. Topic Segmentation: Identify distinct topics discussed during the meeting, with:
           - Clear titles for each topic section
           - Timestamps or position markers when they began/ended (if available)
           - Participants who contributed to each topic
           - Comprehensive summaries of the discussion for each topic
           - Key points specific to each topic
        
        4. Decisions: Capture formal and informal decisions made during the meeting
        
        5. Next Steps: General follow-up items mentioned that aren't specific action items assigned to individuals
        
        6. Notable Quotes: Any particularly important, insightful, or representative quotes
        
        7. Meeting Minutes: A comprehensive, well-structured account of the meeting in a traditional minutes format

        Guidelines:
        - Preserve factual accuracy and important details
        - Maintain the original meaning and intent of discussions
        - Focus on content over conversational fillers
        - Identify participants by name when possible
        - Capture the overall tone/sentiment of the meeting
        - Use a professional, neutral tone appropriate for business documentation

        Analyze the following meeting transcript and provide a complete structured summary.
        """
    
    def summarize(self, text, max_sentences=10):
        """Generate multi-level summaries from meeting transcript.
        
        Args:
            text (str): Text to summarize
            max_sentences (int, optional): Maximum number of sentences for text_rank summaries. Defaults to 10.
            
        Returns:
            dict: Summary result with different detail levels and metadata
        """
        logger.info(f"Generating multi-level summary with model: {self.model}")
        
        try:
            if not text or len(text.strip()) == 0:
                return {'error': 'No text provided for summarization', 'status': 'error'}
            
            # Choose summarization approach based on model and available capabilities
            if self.model == "ai_powered" and self.use_instructor:
                return self._ai_powered_summarize(text)
            elif self.model == "text_rank" or not self.use_instructor:
                return self._text_rank_summarize_enhanced(text, max_sentences)
            else:
                # Default to text rank with enhanced capabilities
                return self._text_rank_summarize_enhanced(text, max_sentences)
            
        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return {'error': f'Error generating summary: {e}', 'status': 'error'}
    
    def _ai_powered_summarize(self, text):
        """Generate comprehensive multi-level summary using AI models.
        
        Args:
            text (str): Meeting transcript text
            
        Returns:
            dict: Structured summary at multiple detail levels
        """
        try:
            # Use OpenAI with instructor for structured output
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",  # Use an appropriate model that's available
                response_model=MeetingSummary,
                temperature=0,
                max_retries=2,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": text}
                ]
            )
            
            # Convert to dict for processing
            summary_data = response.model_dump()
            
            # Format for compatibility with the existing application
            result = {
                'summary': summary_data.get('minutes', ''),
                'tldr': summary_data.get('tldr', ''),
                'key_points': summary_data.get('key_points', []),
                'topics': summary_data.get('topics', []),
                'decisions': summary_data.get('decisions', []),
                'meeting_title': summary_data.get('meeting_title', ''),
                'meeting_date': summary_data.get('meeting_date', ''),
                'participants': summary_data.get('participants', []),
                'next_steps': summary_data.get('next_steps', []),
                'notable_quotes': summary_data.get('notable_quotes', []),
                'status': 'success',
                'model': self.model
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error in AI-powered summarization: {e}")
            # Fallback to Text Rank
            return self._text_rank_summarize_enhanced(text)
    
    def _text_rank_summarize_enhanced(self, text, max_sentences=10):
        """Enhanced TextRank summarization with multi-level summary generation.
        
        Args:
            text (str): Text to summarize
            max_sentences (int, optional): Maximum number of sentences. Defaults to 10.
            
        Returns:
            dict: Summary at different detail levels
        """
        # Clean and tokenize text
        clean_text = re.sub(r'\s+', ' ', text).strip()
        sentences = sent_tokenize(clean_text)
        
        # If we have very little text, just return it
        if len(sentences) <= max_sentences // 2:
            return {
                'summary': text,
                'tldr': sentences[0] if sentences else "",
                'key_points': sentences,
                'status': 'success',
                'model': 'text_rank'
            }
        
        # Create similarity matrix
        stop_words = set(stopwords.words('english'))
        similarity_matrix = self._build_similarity_matrix(sentences, stop_words)
        
        # Apply PageRank algorithm to find important sentences
        nx_graph = nx.from_numpy_array(similarity_matrix)
        scores = nx.pagerank(nx_graph)
        
        # Sort sentences by score
        ranked_sentences = sorted([(scores[i], i, sentences[i]) for i in range(len(sentences))], 
                                reverse=True)
        
        # Generate TLDR (1-2 sentences)
        tldr_sentences = [ranked_sentences[i][2] for i in range(min(2, len(ranked_sentences)))]
        tldr = ' '.join(tldr_sentences)
        
        # Generate key points (5-10 points)
        key_points = []
        for i in range(min(10, len(ranked_sentences))):
            point = ranked_sentences[i][2]
            if point not in key_points:  # Avoid duplicates
                key_points.append(point)
        
        # Generate comprehensive summary (up to max_sentences)
        top_sentence_indices = [ranked_sentences[i][1] for i in range(min(max_sentences, len(ranked_sentences)))]
        top_sentence_indices.sort()  # Sort to maintain original order
        
        summary = ' '.join([sentences[i] for i in top_sentence_indices])
        
        # Attempt to identify topics using clustering (simplified)
        topics = self._extract_topics(text, sentences, ranked_sentences)
        
        return {
            'summary': summary,
            'tldr': tldr,
            'key_points': key_points,
            'topics': topics,
            'status': 'success',
            'model': 'text_rank'
        }
    
    def _extract_topics(self, text, sentences, ranked_sentences):
        """Simple topic extraction using text segmentation.
        
        Args:
            text (str): Original text
            sentences (list): List of sentences
            ranked_sentences (list): Ranked sentences with scores
            
        Returns:
            list: List of identified topics
        """
        # This is a simplified topic extraction method
        # A more sophisticated approach would use true topic modeling
        
        topics = []
        
        if len(sentences) < 10:
            # Too short for meaningful topic segmentation
            return topics
        
        # Use a sliding window to identify potential topic boundaries
        # based on changes in lexical cohesion
        
        window_size = min(5, len(sentences) // 3)
        current_topic_sentences = []
        current_topic_start = 0
        
        for i in range(len(sentences) - window_size):
            # Calculate cohesion within current window
            window1 = ' '.join(sentences[i:i+window_size])
            window2 = ' '.join(sentences[i+window_size:i+window_size*2]) if i+window_size*2 <= len(sentences) else ''
            
            if not window2:
                continue
                
            # Check if there's a significant change in vocabulary
            # This is a simple heuristic; more sophisticated methods would be better
            stop_words = set(stopwords.words('english'))
            words1 = set([w.lower() for w in re.findall(r'\w+', window1) if w.lower() not in stop_words])
            words2 = set([w.lower() for w in re.findall(r'\w+', window2) if w.lower() not in stop_words])
            
            overlap = len(words1.intersection(words2)) / max(1, len(words1.union(words2)))
            
            # If low overlap, consider it a topic boundary
            if overlap < 0.3 and len(current_topic_sentences) >= 3:
                # Create a topic from accumulated sentences
                topic_text = ' '.join(current_topic_sentences)
                
                # Extract key sentences for this topic
                topic_sentences = sent_tokenize(topic_text)
                if len(topic_sentences) > 2:
                    # Create a mini text rank for this segment
                    similarity_matrix = self._build_similarity_matrix(topic_sentences, stop_words)
                    nx_graph = nx.from_numpy_array(similarity_matrix)
                    try:
                        scores = nx.pagerank(nx_graph)
                        ranked_topic_sentences = sorted([(scores[i], topic_sentences[i]) for i in range(len(topic_sentences))], 
                                                     reverse=True)
                        
                        # Extract topic title from highest ranked sentence
                        title = self._generate_topic_title(ranked_topic_sentences[0][1])
                        
                        # Get key points
                        key_points = [s[1] for s in ranked_topic_sentences[:min(3, len(ranked_topic_sentences))]]
                        
                        topics.append({
                            'title': title,
                            'summary': topic_text,
                            'key_points': key_points,
                            'speakers': []  # Would need speaker diarization
                        })
                    except:
                        # If pagerank fails (can happen with very small graphs)
                        pass
                
                # Reset for next topic
                current_topic_sentences = []
                current_topic_start = i + window_size
            
            # Add current sentence to current topic
            if i == current_topic_start:
                current_topic_sentences.append(sentences[i])
        
        # Handle the last topic if there's enough content
        if len(current_topic_sentences) >= 3:
            topic_text = ' '.join(current_topic_sentences)
            topics.append({
                'title': self._generate_topic_title(current_topic_sentences[0]),
                'summary': topic_text,
                'key_points': current_topic_sentences[:min(3, len(current_topic_sentences))],
                'speakers': []
            })
        
        return topics
    
    def _generate_topic_title(self, sentence):
        """Generate a short title from a sentence.
        
        Args:
            sentence (str): Sentence to generate title from
            
        Returns:
            str: Generated title
        """
        # Remove stop words and keep only the important ones
        stop_words = set(stopwords.words('english'))
        words = [w for w in re.findall(r'\w+', sentence) if w.lower() not in stop_words]
        
        # Limit to 5-7 words
        if len(words) > 7:
            words = words[:7]
        
        if not words:
            return "Discussion Topic"
            
        title = ' '.join(words)
        
        # Capitalize first letter of each word
        title = ' '.join([w.capitalize() if len(w) > 3 else w for w in title.split()])
        
        return title
    
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

# Create a default instance
summarization_service = SummarizationService()