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
    
    // Add the test button after a short delay to ensure other elements are loaded
    if (isDashboardPage) {
        setTimeout(addTestButton, 1000);
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
    let currentSessionId = null;
    
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
        console.log('Action items data type:', typeof data);
        console.log('Action items has items property:', data.hasOwnProperty('items'));
        
        if (data.items) {
            console.log('Number of action items:', data.items.length);
            console.log('First action item:', data.items[0]);
        }
        
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
    
    socket.on('session_created', function(data) {
        console.log('Session created:', data);
        if (data.session_id) {
            currentSessionId = data.session_id;
            console.log(`Current session ID set to: ${currentSessionId}`);
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
    let transcriptRequestInterval;
    async function startRecording() {
        try {
            const stream = await navigator.mediaDevices.getUserMedia({ 
                audio: {
                    channelCount: 1,
                    sampleRate: 44100,
                    echoCancellation: true,
                    noiseSuppression: true,
                }
            });
            
            // Use a WAV recorder which is more widely supported
            audioChunks = [];
            
            // Create an audio context to handle recording in a more controlled way
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = audioContext.createMediaStreamSource(stream);
            const processor = audioContext.createScriptProcessor(4096, 1, 1);
            
            let audioData = []; // To store raw audio data
            
            // Connect the nodes
            source.connect(processor);
            processor.connect(audioContext.destination);
            
            // Set up recording state variables
            let isRecording = true;
            let recordingInterval;
            let chunkCount = 0;
            
            // Process audio data
            processor.onaudioprocess = function(e) {
                if (!isRecording) return;
                
                // Get the raw audio data
                const channelData = e.inputBuffer.getChannelData(0);
                const buffer = new Float32Array(channelData.length);
                for (let i = 0; i < channelData.length; i++) {
                    buffer[i] = channelData[i];
                }
                
                // Add to our audio data collection
                audioData.push(buffer);
                chunkCount++;
                
                // Every 5 seconds (roughly), send the accumulated audio
                if (chunkCount >= 60) { // ~5 seconds at 4096 buffer size
                    // Convert to WAV
                    const blob = createWavBlob(audioData, audioContext.sampleRate);
                    
                    // Create a file from the blob
                    const fileName = `recording_${Date.now()}.wav`;
                    const file = new File([blob], fileName, { type: 'audio/wav' });
                    
                    // Upload the file
                    const formData = new FormData();
                    formData.append('file', file);
                    formData.append('session_id', currentSessionId || '');
                    
                    fetch('/api/chunk_upload', {
                        method: 'POST',
                        body: formData
                    })
                    .then(response => response.json())
                    .then(data => {
                        console.log("Chunk uploaded successfully:", data);
                        // Request latest transcript
                        if (currentSessionId) {
                            socket.emit('request_current_transcript', { 
                                session_id: currentSessionId 
                            });
                        }
                    })
                    .catch(error => {
                        console.error("Error uploading chunk:", error);
                    });
                    
                    // Reset for the next chunk
                    audioData = [];
                    chunkCount = 0;
                }
            };
            
            // Function to convert audio buffers to WAV blob
            function createWavBlob(audioData, sampleRate) {
                // Merge all buffer arrays into one
                let totalLength = 0;
                for (let i = 0; i < audioData.length; i++) {
                    totalLength += audioData[i].length;
                }
                
                const mergedAudio = new Float32Array(totalLength);
                let offset = 0;
                for (let i = 0; i < audioData.length; i++) {
                    mergedAudio.set(audioData[i], offset);
                    offset += audioData[i].length;
                }
                
                // Convert to 16-bit PCM
                const pcmData = new Int16Array(mergedAudio.length);
                for (let i = 0; i < mergedAudio.length; i++) {
                    const s = Math.max(-1, Math.min(1, mergedAudio[i]));
                    pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
                }
                
                // Create the WAV file
                const wavBuffer = new ArrayBuffer(44 + pcmData.length * 2);
                const view = new DataView(wavBuffer);
                
                // WAV header
                // "RIFF" chunk descriptor
                writeString(view, 0, 'RIFF');
                view.setUint32(4, 36 + pcmData.length * 2, true);
                writeString(view, 8, 'WAVE');
                
                // "fmt " sub-chunk
                writeString(view, 12, 'fmt ');
                view.setUint32(16, 16, true); // fmt chunk size
                view.setUint16(20, 1, true); // audio format (1 = PCM)
                view.setUint16(22, 1, true); // num channels (1 = mono)
                view.setUint32(24, sampleRate, true); // sample rate
                view.setUint32(28, sampleRate * 2, true); // byte rate
                view.setUint16(32, 2, true); // block align
                view.setUint16(34, 16, true); // bits per sample
                
                // "data" sub-chunk
                writeString(view, 36, 'data');
                view.setUint32(40, pcmData.length * 2, true);
                
                // Write PCM data
                const byteData = new Uint8Array(wavBuffer, 44);
                for (let i = 0; i < pcmData.length; i++) {
                    const sample = pcmData[i];
                    byteData[i * 2] = sample & 0xFF;
                    byteData[i * 2 + 1] = (sample >> 8) & 0xFF;
                }
                
                return new Blob([wavBuffer], { type: 'audio/wav' });
            }
            
            // Helper to write strings to DataView
            function writeString(view, offset, string) {
                for (let i = 0; i < string.length; i++) {
                    view.setUint8(offset + i, string.charCodeAt(i));
                }
            }
            
            // Store references for stopping
            mediaRecorder = {
                stream: stream,
                audioContext: audioContext,
                processor: processor,
                source: source,
                stop: function() {
                    isRecording = false;
                    if (recordingInterval) {
                        clearInterval(recordingInterval);
                    }
                    
                    this.processor.disconnect();
                    this.source.disconnect();
                    this.stream.getTracks().forEach(track => track.stop());
                    
                    // Send any remaining audio
                    if (audioData.length > 0) {
                        const blob = createWavBlob(audioData, audioContext.sampleRate);
                        const fileName = `recording_final_${Date.now()}.wav`;
                        const file = new File([blob], fileName, { type: 'audio/wav' });
                        
                        const formData = new FormData();
                        formData.append('file', file);
                        formData.append('session_id', currentSessionId || '');
                        
                        return fetch('/api/chunk_upload', {
                            method: 'POST',
                            body: formData
                        });
                    }
                    
                    return Promise.resolve();
                }
            };
            
            // Start recording
            isRecording = true;
            
            // Update UI
            startBtn.disabled = true;
            pauseBtn.disabled = false;
            stopBtn.disabled = false;
            statusIndicator.innerHTML = '<span class="badge bg-danger recording-active">Recording</span>';
            
            // Tell server we're starting to stream and get a session ID
            socket.emit('start_stream', { format: 'audio/wav' });
            
            // Set up periodic transcript requests
            transcriptRequestInterval = setInterval(() => {
                if (currentSessionId) {
                    console.log("Requesting current transcript");
                    socket.emit('request_current_transcript', { session_id: currentSessionId });
                }
            }, 5000); // Request update every 5 seconds
            
        } catch (error) {
            console.error('Error accessing microphone:', error);
            alert('Could not access microphone. Please check permissions.');
        }
    }
    
    // Update the stopRecording function to work with our new recorder
    function stopRecording() {
        if (mediaRecorder) {
            // Update UI first for responsive feel
            startBtn.disabled = false;
            pauseBtn.disabled = true;
            stopBtn.disabled = true;
            statusIndicator.innerHTML = '<span class="badge bg-success">Processing</span>';
            
            // Clear the transcript request interval
            if (transcriptRequestInterval) {
                clearInterval(transcriptRequestInterval);
            }
            
            // Tell server we're stopping
            if (currentSessionId) {
                console.log('Stopping stream with session ID:', currentSessionId);
                socket.emit('stop_stream', { session_id: currentSessionId });
            } else {
                console.error('No session ID available for stop_stream event');
            }
            
            // Stop the recorder and upload the final chunk
            mediaRecorder.stop()
                .then(response => {
                    if (response) return response.json();
                    return null;
                })
                .then(data => {
                    console.log('Final recording chunk processed:', data);
                    
                    // Creating a complete recording file for the full session
                    const formData = new FormData();
                    const fileName = `full_recording_${Date.now()}.wav`;
                    
                    // Instead of using blob which might have issues, create a simple text file
                    // that indicates the recording is done
                    const completionMarker = new Blob(['Recording completed'], { type: 'text/plain' });
                    formData.append('file', completionMarker, fileName);
                    formData.append('session_id', currentSessionId || '');
                    formData.append('is_complete', 'true');
                    
                    return fetch('/api/upload', {
                        method: 'POST',
                        body: formData
                    });
                })
                .then(response => {
                    if (response) return response.json();
                    return null;
                })
                .then(data => {
                    console.log('Recording completed:', data);
                    statusIndicator.innerHTML = '<span class="badge bg-info">Completed</span>';
                    
                    // Store the new session ID 
                    if (data && data.session_id) {
                        sessionId = data.session_id;
                        
                        // Start polling for results with the new session ID
                        setTimeout(() => {
                            pollForResultsById(sessionId);
                        }, 3000);
                    }
                })
                .catch(error => {
                    console.error('Error finalizing recording:', error);
                    statusIndicator.innerHTML = '<span class="badge bg-danger">Error</span>';
                });
        }
    }
    
    // Need to update the pauseRecording function as well
    function pauseRecording() {
        if (mediaRecorder) {
            if (isRecording) {
                // Pause recording
                isRecording = false;
                
                // Update UI
                pauseBtn.innerHTML = '<i class="bi bi-play-fill me-1"></i>Resume';
                statusIndicator.innerHTML = '<span class="badge bg-warning">Paused</span>';
                
                // Tell server we're pausing
                socket.emit('pause_stream', { session_id: currentSessionId });
            } else {
                // Resume recording
                isRecording = true;
                
                // Update UI
                pauseBtn.innerHTML = '<i class="bi bi-pause-fill me-1"></i>Pause';
                statusIndicator.innerHTML = '<span class="badge bg-danger recording-active">Recording</span>';
                
                // Tell server we're resuming
                socket.emit('resume_stream', { session_id: currentSessionId });
            }
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
                        // Fixed: Pass the action items with the expected format
                        updateActionItems({
                            items: data.action_items.items || [], 
                            status: data.action_items.status
                        });
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
    
    /**
     * Update the transcript display
     */
    function updateTranscript(data) {
        console.log("updateTranscript called with data:", data);
        
        // Make sure we have text to display
        if (!data || !data.text || data.text.trim() === '') {
            console.log("No text content to display in transcript");
            return;
        }
        
        // Set flag that we've displayed transcription
        transcriptionDisplayed = true;
        
        // Clear error messages if we get valid transcript data
        if (transcript.textContent.includes('Error:')) {
            transcript.innerHTML = '';
        }
        
        // If this is the first update, clear any placeholder
        if (transcript.textContent === 'No transcript available yet.' || 
            transcript.textContent.includes('Processing') ||
            transcript.textContent.includes('Transcript will appear here...')) {
            console.log("Clearing placeholder text");
            transcript.innerHTML = '';
        }
        
        // Get the existing transcript content
        const existingText = transcript.textContent || '';
        
        // Process the incoming text
        const newText = data.text.trim();
        
        // Check if this exact text already exists in the transcript
        if (existingText.includes(newText)) {
            console.log("Skipping duplicate text:", newText);
            return;
        }
        
        // Create a new transcript entry
        const entry = document.createElement('div');
        entry.className = 'transcript-entry';
        
        if (data.speaker) {
            // If we have speaker identification
            entry.innerHTML = `
                <span class="speaker-label">${data.speaker}:</span>
                <span class="speaker-text">${newText}</span>
            `;
        } else {
            // Simple transcript without speaker identification
            entry.textContent = newText;
        }
        
        // Add the entry to the transcript
        transcript.appendChild(entry);
        
        // Auto-scroll if enabled
        if (autoScroll && autoScroll.checked) {
            const container = document.querySelector('.transcript-container');
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
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
            tldr.innerHTML = `<h6>TL;DR</h6>
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
    
    // Add topics if available
    if (data.topics && data.topics.length > 0) {
        const topicsSection = document.createElement('div');
        topicsSection.className = 'mb-3';
        topicsSection.innerHTML = `<h6>Discussion Topics</h6>`;
        
        const topicsList = document.createElement('div');
        data.topics.forEach((topic, index) => {
            const topicDiv = document.createElement('div');
            topicDiv.className = 'mb-2';
            topicDiv.innerHTML = `
                <strong>${index+1}. ${topic.title}</strong>
                <p>${topic.summary}</p>
            `;
            topicsList.appendChild(topicDiv);
        });
        
        topicsSection.appendChild(topicsList);
        summaryContent.appendChild(topicsSection);
    }
}

/**
 * Update the action items list - FIXED VERSION
 */
function updateActionItems(data) {
    console.log('Updating action items with data:', data);
    const actionItemsList = document.getElementById('action-items-list');
    
    // Clear placeholder
    actionItemsList.innerHTML = '';
    
    // Handle both direct data and nested data formats
    let items = [];
    if (data.items) {
        // Direct data format from our fixed server response
        items = data.items;
    } else if (data.action_items && data.action_items.items) {
        // Nested format from polling or original server response
        items = data.action_items.items;
    }
    
    if (items && items.length > 0) {
        items.forEach(item => {
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
}

/**
* Add a test button to the dashboard UI
*/
function addTestButton() {
// Only add on dashboard page
if (window.location.pathname !== '/dashboard') return;

// Create the button
const buttonGroup = document.querySelector('.btn-group');
if (buttonGroup) {
    const testButton = document.createElement('button');
    testButton.id = 'test-action-items';
    testButton.className = 'btn btn-sm btn-outline-secondary';
    testButton.innerHTML = '<i class="bi bi-bug me-1"></i>Test';
    testButton.onclick = testActionItemExtraction;
    
    // Add the button to the UI
    buttonGroup.appendChild(testButton);
    console.log("Test button added to UI");
}
}

/**
* Test function for action item extraction
*/
function testActionItemExtraction() {
// Sample meeting transcript with clear action items
const testTranscript = `
John: Thanks everyone for joining today's project update meeting.

Sarah: I've been working on the frontend design. I'll finish the mockups by next Friday.

John: Great, Sarah. Mark, can you review those designs when they're ready?

Mark: Sure, I'll take care of it.

John: We need to finalize the database schema by the end of the week.

Lisa: I'll handle that. I'll send the schema document to everyone by Thursday.

John: Perfect. Lisa is responsible for the backend API documentation as well.

Mark: We should also schedule a meeting with the client next week.

Sarah: I'll coordinate with them and send a calendar invite by tomorrow.

John: One last thing - we need to prepare for the demo next month. Mark will lead that effort.

Mark: Yes, I'll create a plan and share it with the team by Monday.

John: Excellent. Thank you everyone!
`;

// Only run this on the dashboard page
if (window.location.pathname === '/dashboard') {
    // Get references to UI elements
    const statusIndicator = document.getElementById('status-indicator');
    const transcript = document.getElementById('transcript');
    
    // Update transcript display
    if (transcript) {
        transcript.innerHTML = `<div class="transcript-entry">${testTranscript.replace(/\n/g, '<br>')}</div>`;
        console.log("Test transcript added to UI");
    }
    
    // Create a session ID if one doesn't exist
    if (!currentSessionId) {
        currentSessionId = 'test-session-' + Date.now();
    }
    
    // Simulate a completed transcription by sending to the server
    console.log("Sending test transcript to server for action item extraction");
    socket.emit('manual_test', {
        session_id: currentSessionId,
        transcript: testTranscript
    });
    
    // Update status
    if (statusIndicator) {
        statusIndicator.innerHTML = '<span class="badge bg-info">Testing Action Items</span>';
    }
}
}

// Test function for manually testing the action items display
setTimeout(function() {
// Only run this if we're on the dashboard and the test parameter is in the URL
if (window.location.pathname === '/dashboard' && window.location.search.includes('test=true')) {
    console.log("Testing action items display...");
    
    // Create test action items
    const testData = {
        items: [
            {
                task: "Complete project documentation",
                assignee: "John",
                deadline: "Next Friday",
                priority: "high",
                status: "not_started"
            },
            {
                task: "Schedule follow-up meeting",
                assignee: "Sarah",
                deadline: "EOD",
                priority: "medium",
                status: "not_started"
            }
        ],
        status: 'success'
    };
    
    // Try to update action items with test data
    console.log("Updating action items with test data:");
    updateActionItems(testData);
}
}, 5000);