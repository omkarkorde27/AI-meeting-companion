#!/usr/bin/env python3
import os
import sys
from services.transcription_service import TranscriptionService

def test_transcription(file_path):
    """Test the transcription service with a given file."""
    
    print(f"Testing transcription of: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"ERROR: File not found at {file_path}")
        return
    
    # Create transcription service
    service = TranscriptionService()
    
    # Try to transcribe the file
    print("Starting transcription...")
    result = service.transcribe_file(file_path)
    
    # Print the result
    print("\nTranscription Result:")
    print(f"Status: {result.get('status', 'Unknown')}")
    
    if result.get('status') == 'success':
        print(f"\nTranscribed Text:\n{result.get('text', 'No text found')}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_transcription.py <path_to_audio_file>")
        sys.exit(1)
    
    file_path = sys.argv[1]
    test_transcription(file_path)