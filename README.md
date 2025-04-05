# AI-Powered Meeting Companion

An AI-powered assistant that can transcribe, summarize, and analyze meetings in real-time or from recordings. This tool helps teams quickly understand what was discussed, what actions are needed, and the tone of the discussion.

## Features

- **Audio Transcription**: Transcribe meeting audio in real-time or from uploaded files
- **Intelligent Summarization**: Generate concise TL;DRs and bullet-point summaries
- **Action Item Extraction**: Automatically identify tasks, assignees, and deadlines
- **Sentiment Analysis**: Analyze the emotional tone throughout the meeting
- **Real-Time Processing**: Process audio as the meeting happens
- **User-Friendly Dashboard**: Visualize all meeting insights in one place

## Getting Started

### Prerequisites

- Python 3.8 or higher
- Virtual environment (recommended)
- A modern web browser

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/meeting-companion.git
   cd meeting-companion
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on the provided template:
   ```bash
   cp .env.example .env
   ```

5. Edit the `.env` file to add your API keys and configuration.

### Running the Application

1. Start the Flask server:
   ```bash
   python app.py
   ```

2. Open your browser and navigate to:
   ```
   http://localhost:5000
   ```

## Usage

### Upload a Meeting Recording

1. From the home page, click on "Upload Recording"
2. Select an audio or video file (MP3, WAV, MP4, etc.)
3. Click "Upload & Analyze"
4. View the processed results on the dashboard

### Record a Live Meeting

1. From the home page, click on "Start Recording"
2. Grant microphone permissions when prompted
3. Use the dashboard controls to start, pause, or stop recording
4. View real-time transcription and analysis results

### Viewing Results

The dashboard provides several sections:
- **Transcript**: The full text of the meeting
- **Summary**: A concise overview with key points
- **Action Items**: Tasks extracted from the discussion
- **Sentiment Analysis**: Emotional tone throughout the meeting

## Project Structure

```
meeting_companion/
├── app.py                  # Main Flask application
├── config.py               # Configuration settings
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (create from .env.example)
├── services/               # Core functionality modules
│   ├── transcription_service.py    # Audio transcription
│   ├── summarization_service.py    # Text summarization
│   ├── action_items_service.py     # Action item extraction
│   └── sentiment_service.py        # Sentiment analysis
├── static/                 # Static files
│   ├── css/                # Stylesheets
│   └── js/                 # JavaScript files
├── templates/              # HTML templates
│   ├── index.html          # Home page
│   └── dashboard.html      # Analysis dashboard
└── uploads/                # Directory for uploaded files (created automatically)
```

## Technical Implementation

- **Backend**: Flask with Flask-SocketIO for real-time communication
- **Frontend**: HTML, CSS, JavaScript with Bootstrap for styling
- **Transcription**: Using SpeechRecognition library
- **Analysis**: Natural Language Processing with NLTK and custom algorithms
- **Visualization**: Chart.js for sentiment visualization

## Future Enhancements

- Multi-language support
- Speaker diarization (identifying who said what)
- Integration with calendar and task management tools
- Custom vocabulary for domain-specific terminology
- End-to-end encryption for sensitive meetings

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.