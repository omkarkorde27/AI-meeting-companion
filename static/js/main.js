document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the index page or dashboard
    const isIndexPage = window.location.pathname === '/';
    const isDashboardPage = window.location.pathname === '/dashboard';
    
    // Initialize Socket.IO connection for dashboard
    let socket;
    if (isDashboardPage) {
        console.log("Dashboard page detected, initializing Socket.IO");
        socket = io({
            pingTimeout: 60000,  // Increase ping timeout
            pingInterval: 25000  // Increase ping interval
        });
        
        // Add more debug listeners
        socket.on('connect', function() {
            console.log('Socket.IO Connected');
        });
        
        socket.on('error', function(data) {
            console.error('Socket.IO Error:', data);
        });
        
        socket.on('disconnect', function() {
            console.log('Socket.IO Disconnected');
        });
        
        initializeDashboard(socket);
    }
    
    // Setup file upload form handler on index page
    if (isIndexPage) {
        const uploadForm = document.getElementById('upload-form');
        if (uploadForm) {
            uploadForm.addEventListener('submit', handleFileUpload);
        }
    }
});

/**
 * Handle file upload form submission
 */
function handleFileUpload(event) {
    event.preventDefault();
    
    const fileInput = document.getElementById('audio-file');
    const file = fileInput.files[0];
    
    if (!file) {
        alert('Please select a file to upload');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    // Show loading state
    const submitBtn = event.target.querySelector('button[type="submit"]');
    const originalBtnText = submitBtn.innerHTML;
    submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Uploading...';
    submitBtn.disabled = true;
    
    // Send the file to the server
    fetch('/api/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        console.log('Success:', data);
        // Redirect to dashboard with the uploaded file ID
        window.location.href = `/dashboard?file=${data.filename}&mode=uploaded&session_id=${data.session_id}`;
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while uploading the file.');
    })
    .finally(() => {
        // Reset button state
        submitBtn.innerHTML = originalBtnText;
        submitBtn.disabled = false;
    });
}

/**
 * Get session ID by filename
 */
function getSessionIdByFilename(filename) {
    // Poll for active sessions and find one with our filename
    console.log(`Looking for session with filename: ${filename}`);
    
    return fetch('/api/sessions')
        .then(response => response.json())
        .then(data => {
            const sessionId = data.find(session => session.filename === filename)?.id;
            console.log(`Found session ID: ${sessionId} for file: ${filename}`);
            return sessionId;
        })
        .catch(error => {
            console.error("Error finding session:", error);
            return null;
        });
}

/**
 * Initialize the dashboard functionality
 */
function initializeDashboard(socket) {
    let transcriptionDisplayed = false;
    // Add debugging
    console.log('Socket object:', socket);
    console.log('Socket handlers:', socket._callbacks);
    
    // Get URL parameters
    const urlParams = new URLSearchParams(window.location.search);
    const mode = urlParams.get('mode');
    let filename = urlParams.get('file');
    let sessionId = urlParams.get('session_id');
    
    console.log(`Dashboard initialized with mode: ${mode}, file: ${filename}, session_id: ${sessionId}`);
    
    // If filename contains URL encoding, decode it
    if (filename && filename.includes('%')) {
        filename = decodeURIComponent(filename);
        console.log(`Decoded filename: ${filename}`);
    }
    
    // UI Elements
    const startBtn = document.getElementById('start-recording');
    const pauseBtn = document.getElementById('pause-recording');
    const stopBtn = document.getElementById('stop-recording');
    const statusIndicator = document.getElementById('status-indicator');
    const transcript = document.getElementById('transcript');
    const autoScroll = document.getElementById('auto-scroll');
    
    // Variables for recording
    let mediaRecorder;
    let audioChunks = [];
    let isRecording = false;
    
    // Register ALL event handlers at initialization
    socket.on('connect', () => {
        console.log('Connected to server');
    });
    
    socket.on('disconnect', () => {
        console.log('Disconnected from server');
    });
    
    socket.on('transcription_update', (data) => {
        console.log('Transcription update received:', data);
        updateTranscript(data);
    });
    
    socket.on('transcription_complete', (data) => {
        console.log('Transcription complete event received:', data);
        // Check if data contains text or transcript property
        if (data.transcript) {
            updateTranscript({text: data.transcript});
        } else if (data.text) {
            updateTranscript({text: data.text});
        }
    });
    
    socket.on('summary_update', (data) => {
        console.log('Summary update received:', data);
        updateSummary(data);
    });
    
    socket.on('action_items_update', (data) => {
        console.log('Action items update received:', data);
        updateActionItems(data);
    });
    
    socket.on('sentiment_update', (data) => {
        console.log('Sentiment update received:', data);
        updateSentimentChart(data);
    });
    
    socket.on('error', function(data) {
        console.error('Socket Error:', data);
        statusIndicator.innerHTML = `<span class="badge bg-danger">Error: ${data.message}</span>`;
        transcript.innerHTML = `<p class="text-center text-danger">Error: ${data.message}</p>`;
    });
    
    socket.on('status_update', function(data) {
        console.log('Status update:', data);
        if (data.status === 'error') {
            statusIndicator.innerHTML = `<span class="badge bg-danger">Error</span>`;
            transcript.innerHTML = `<p class="text-center text-danger">Error: ${data.error}</p>`;
        } else {
            statusIndicator.innerHTML = `<span class="badge bg-info">${data.status}</span>`;
        }
    });
    
    // Initialize based on mode
    if (mode === 'live') {
        // Setup for live recording
        setupLiveRecording();
    } else if (mode === 'uploaded' && filename) {
        // Setup for uploaded file
        loadUploadedFile(filename, sessionId);
    }
    
    /**
     * Setup for live recording mode
     */
    function setupLiveRecording() {
        // Enable start recording button
        startBtn.disabled = false;
        
        // Add event listeners
        startBtn.addEventListener('click', startRecording);
        pauseBtn.addEventListener('click', pauseRecording);
        stopBtn.addEventListener('click', stopRecording);
    }
    
    /**
     * Start recording audio
     */
    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            
            mediaRecorder = new MediaRecorder(stream);
            audioChunks = [];
            
            mediaRecorder.addEventListener('dataavailable', event => {
                if (event.data.size > 0) {
                    audioChunks.push(event.data);
                    
                    // Convert audio chunk to base64 and send to server
                    const reader = new FileReader();
                    reader.readAsDataURL(event.data);
                    reader.onloadend = () => {
                        const base64data = reader.result.split(',')[1];
                        socket.emit('audio_chunk', { audio: base64data });
                    };
                }
            });
            
            // Start recording
            mediaRecorder.start(1000); // Collect data every second
            isRecording = true;
            
            // Update UI
            startBtn.disabled = true;
            pauseBtn.disabled = false;
            stopBtn.disabled = false;
            statusIndicator.innerHTML = '<span class="badge bg-danger recording-active">Recording</span>';
            
            // Tell server we're starting to stream
            socket.emit('start_stream', { format: 'audio/webm' });
            
        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Could not access microphone. Please check permissions.');
        }
    }
    
    /**
     * Pause recording
     */
    function pauseRecording() {
        if (mediaRecorder && isRecording) {
            mediaRecorder.pause();
            isRecording = false;
            
            // Update UI
            pauseBtn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Resume';
            statusIndicator.innerHTML = '<span class="badge bg-warning">Paused</span>';
            
            // Tell server we're pausing
            socket.emit('pause_stream');
        } else if (mediaRecorder) {
            mediaRecorder.resume();
            isRecording = true;
            
            // Update UI
            pauseBtn.innerHTML = '<i class="bi bi-pause-fill me-1"></i>Pause';
            statusIndicator.innerHTML = '<span class="badge bg-danger recording-active">Recording</span>';
            
            // Tell server we're resuming
            socket.emit('resume_stream');
        }
    }
    
    /**
     * Stop recording
     */
    function stopRecording() {
        if (mediaRecorder) {
            mediaRecorder.stop();
            
            // Stop all tracks in the stream
            mediaRecorder.stream.getTracks().forEach(track => track.stop());
            
            // Update UI
            startBtn.disabled = false;
            pauseBtn.disabled = true;
            stopBtn.disabled = true;
            statusIndicator.innerHTML = '<span class="badge bg-success">Processing</span>';
            
            // Tell server we're stopping
            socket.emit('stop_stream');
            
            // Combine audio chunks and create a blob
            const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
            
            // Upload the complete recording for final processing
            const formData = new FormData();
            formData.append('file', audioBlob, 'recording.webm');
            
            fetch('/api/upload', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                console.log('Recording uploaded:', data);
                statusIndicator.innerHTML = '<span class="badge bg-info">Completed</span>';
            })
            .catch(error => {
                console.error('Error uploading recording:', error);
                statusIndicator.innerHTML = '<span class="badge bg-danger">Error</span>';
            });
        }
    }
    
    /**
     * Load and process an uploaded file
     */
    function loadUploadedFile(filename, sessionId) {
        // Update UI
        statusIndicator.innerHTML = '<span class="badge bg-info">Processing</span>';
        transcript.innerHTML = '<p class="text-center">Processing uploaded file...</p>';
        
        console.log(`Processing uploaded file: ${filename} with session ID: ${sessionId}`);
        
        // Request processing of the uploaded file
        socket.emit('process_file', { filename: filename });
        
        // Start a timer to check if we've received a response after 8 seconds instead of 5
        setTimeout(() => {
            // If transcript is still showing processing message and we haven't displayed anything yet
            if (transcript.textContent.includes('Processing') && !transcriptionDisplayed) {
                console.log("No transcription received through socket, falling back to polling");
                
                if (sessionId) {
                    // If we have a session ID, use it directly
                    pollForResultsById(sessionId);
                } else {
                    // Otherwise try to find the session ID by filename
                    pollForResults(filename);
                }
            }
        }, 8000);
    }

    /**
     * Poll for results using session ID
     */
    function pollForResultsById(sessionId) {
        console.log(`Starting to poll for results for session ID: ${sessionId}`);
        
        // Poll every 3 seconds
        const pollInterval = setInterval(() => {
            console.log(`Polling for results for session: ${sessionId}`);
            
            // Make an API request to get the session results
            fetch(`/api/results/${sessionId}`)
                .then(response => response.json())
                .then(data => {
                    console.log("Polled data:", data);
                    
                    if (data.transcript && !transcriptionDisplayed) {
                        // Update transcript only if not already displayed
                        updateTranscript({text: data.transcript});
                    }
                    
                    // Only update summary if it exists and has necessary properties
                    if (data.summary && typeof data.summary === 'object') {
                        updateSummary(data.summary);
                    }
                    
                    // Only update action items if they exist
                    if (data.action_items && typeof data.action_items === 'object') {
                        updateActionItems(data.action_items);
                    }
                    
                    // Only update sentiment if it exists
                    if (data.sentiment && typeof data.sentiment === 'object') {
                        updateSentimentChart(data.sentiment);
                    }
                    
                    // Stop polling if complete
                    if (data.status === 'completed') {
                        clearInterval(pollInterval);
                    }
                })
                .catch(error => {
                    console.error("Error polling for results:", error);
                });
        }, 3000);
        
        // Stop polling after 2 minutes
        setTimeout(() => {
            clearInterval(pollInterval);
            console.log("Stopped polling for results");
        }, 120000);
    }
    
    /**
     * Poll for results using filename
     */
    function pollForResults(filename) {
        console.log("Starting to poll for results by filename");
        
        // First get the session ID for this filename
        getSessionIdByFilename(filename).then(sessionId => {
            if (!sessionId) {
                console.error("Couldn't find session ID for filename:", filename);
                return;
            }
            
            // Now that we have the session ID, use it to poll
            pollForResultsById(sessionId);
        });
    }
    
    // Then modify the updateTranscript function
    function updateTranscript(data) {
        console.log("updateTranscript called with data:", data);
        
        // Skip if we've already displayed this transcript
        if (transcriptionDisplayed) {
            console.log("Skipping duplicate transcript");
            return;
        }
        
        // If this is the first update, clear the placeholder
        if (transcript.querySelector('.text-muted')) {
            console.log("Clearing placeholder text");
            transcript.innerHTML = '';
        }
        
        // Create a new transcript entry
        const entry = document.createElement('div');
        entry.className = 'transcript-entry';
        
        if (data.speaker) {
            // If we have speaker identification
            entry.innerHTML = `
                <span class="speaker-label">${data.speaker}:</span>
                <span class="speaker-text">${data.text}</span>
            `;
        } else {
            // Simple transcript without speaker identification
            entry.textContent = data.text;
        }
        
        // Add the entry to the transcript
        transcript.appendChild(entry);
        
        // Mark as displayed to prevent duplicates
        transcriptionDisplayed = true;
        
        // Auto-scroll if enabled
        if (autoScroll.checked) {
            const container = document.querySelector('.transcript-container');
            container.scrollTop = container.scrollHeight;
        }
    }
    
    /**
     * Update the summary display
     */
    function updateSummary(data) {
        const summaryContent = document.getElementById('summary-content');
        
        // Clear placeholder
        summaryContent.innerHTML = '';
        
        // Add TLDR
        if (data.tldr) {
            const tldr = document.createElement('div');
            tldr.className = 'mb-3';
            tldr.innerHTML = `
                <h6>TL;DR</h6>
                <p>${data.tldr}</p>
            `;
            summaryContent.appendChild(tldr);
        }
        
        // Add key points
        if (data.key_points && data.key_points.length > 0) {
            const keyPoints = document.createElement('div');
            keyPoints.className = 'mb-3';
            keyPoints.innerHTML = `<h6>Key Points</h6>`;
            
            const pointsList = document.createElement('ul');
            data.key_points.forEach(point => {
                const li = document.createElement('li');
                li.textContent = point;
                pointsList.appendChild(li);
            });
            
            keyPoints.appendChild(pointsList);
            summaryContent.appendChild(keyPoints);
        }
    }
    
    /**
     * Update the action items list
     */
    function updateActionItems(data) {
        const actionItemsList = document.getElementById('action-items-list');
        
        // Clear placeholder
        actionItemsList.innerHTML = '';
        
        if (data.items && data.items.length > 0) {
            data.items.forEach(item => {
                const li = document.createElement('li');
                li.className = 'list-group-item action-item';
                
                // Create content with assignee and deadline if available
                let content = `<div><strong>${item.task}</strong>`;
                
                if (item.assignee) {
                    content += `<br><small>Assigned to: ${item.assignee}</small>`;
                }
                
                content += '</div>';
                
                // Add deadline badge if available
                if (item.deadline) {
                    content += `<span class="badge bg-info">${item.deadline}</span>`;
                }
                
                li.innerHTML = content;
                actionItemsList.appendChild(li);
            });
        } else {
            // No action items found
            actionItemsList.innerHTML = '<li class="list-group-item text-center">No action items detected</li>';
        }
    }
    
    /**
     * Update the sentiment analysis chart
     */
    function updateSentimentChart(data) {
        const sentimentContainer = document.getElementById('sentiment-chart');
        
        // Clear placeholder
        sentimentContainer.innerHTML = '';
        
        if (!data || !data.sentiments) {
            sentimentContainer.innerHTML = '<p class="text-center">No sentiment data available</p>';
            return;
        }
        
        // Create canvas for Chart.js
        const canvas = document.createElement('canvas');
        canvas.id = 'sentiment-canvas';
        sentimentContainer.appendChild(canvas);
        
        // Prepare data for Chart.js
        const labels = data.sentiments.map(item => item.timestamp || item.segment);
        const sentimentData = data.sentiments.map(item => item.score);
        
        // Create the chart
        const ctx = canvas.getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Sentiment Score',
                    data: sentimentData,
                    borderColor: 'rgb(75, 192, 192)',
                    tension: 0.1,
                    fill: false
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: {
                        min: -1,
                        max: 1,
                        title: {
                            display: true,
                            text: 'Sentiment (Negative to Positive)'
                        }
                    },
                    x: {
                        title: {
                            display: true,
                            text: 'Time'
                        }
                    }
                }
            }
        });
    }
};