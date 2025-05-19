// UI Handlers Module
const UIHandlers = {
    // Update status display
    updateStatusDisplay(data) {
        if (!data || !data.status) return;
        
        const progressBar = document.getElementById('progressBar');
        const stepName = document.getElementById('stepName');
        const statusSection = document.getElementById('statusSection');
        
        // Get status data
        const progress = data.status.progress || 0;
        const message = data.status.message || 'Processing...';
        const stepNameText = data.status.step_name || '';
        
        // Update progress bar
        progressBar.style.width = `${progress}%`;
        progressBar.textContent = `${progress}%`;
        
        // Set progress bar colour
        progressBar.className = 'progress-bar progress-bar-striped progress-bar-animated';
        
        if (data.error) {
            progressBar.classList.add('bg-danger');
        } else if (progress >= 100) {
            progressBar.classList.add('bg-success');
        } else if (progress >= 70) {
            progressBar.classList.add('bg-warning');
        } else if (progress >= 30) {
            progressBar.classList.add('bg-info');
        } else {
            progressBar.classList.add('bg-primary');
        }
        
        // Update step name
        if (stepNameText !== '') {
            stepName.innerHTML = `<span class="fw-bold">${stepNameText}:</span> ${message}`;
        } else {
            stepName.innerHTML = `<span class="fw-bold">${message}</span>`;
        }
        
        // Update page title
        document.title = `${progress}% | TruthTracer`;
        
        // Show status section
        statusSection.classList.remove('d-none');
    },
    
    // Update log messages
    updateLogMessages(data) {
        if (!data || !data.log_messages || !Array.isArray(data.log_messages)) return;
        
        const logMessages = document.getElementById('logMessages');
        logMessages.innerHTML = '';
        
        // Add each message
        data.log_messages.forEach(msg => {
            const messageDiv = document.createElement('div');
            
            if (msg.includes('Error:')) {
                messageDiv.className = 'text-danger';
            } else if (msg.includes('Warning:')) {
                messageDiv.className = 'text-warning';
            } else if (msg.includes('complete')) {
                messageDiv.className = 'text-success';
            } else {
                messageDiv.className = 'text-info';
            }
            
            messageDiv.textContent = msg;
            logMessages.appendChild(messageDiv);
        });
        
        this.scrollLogToBottom();
    },
    
    scrollLogToBottom() {
        const logMessages = document.getElementById('logMessages');
        logMessages.scrollTop = logMessages.scrollHeight;
    },

    // Reset UI for new analysis
    resetForNewAnalysis() {
        const statusSection = document.getElementById('statusSection');
        const resultsSection = document.getElementById('resultsSection');
        const logMessages = document.getElementById('logMessages');
        const progressBar = document.getElementById('progressBar');
        const stepName = document.getElementById('stepName');
        
        // Remove results-displayed class to make log container larger
        document.body.classList.remove('results-displayed');
        
        statusSection.classList.remove('d-none');
        resultsSection.classList.add('d-none');
        logMessages.innerHTML = '';
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        
        stepName.innerHTML = '<span class="fw-bold">Starting:</span> Preparing to analyse article';
        logMessages.innerHTML = '<div class="text-info">Starting analysis...</div>';
    },
    
    // Add a single log message
    addLogMessage(message, type = 'info') {
        const logMessages = document.getElementById('logMessages');
        const messageDiv = document.createElement('div');
        
        switch (type) {
            case 'error':
                messageDiv.className = 'text-danger';
                break;
            case 'warning':
                messageDiv.className = 'text-warning';
                break;
            case 'success':
                messageDiv.className = 'text-success';
                break;
            default:
                messageDiv.className = 'text-info';
        }
        
        messageDiv.textContent = message;
        logMessages.appendChild(messageDiv);
        this.scrollLogToBottom();
    },

    // Update UI on analysis step change
    updateAnalysisStep(stepNum, stepName) {
        if (stepNum < 0) return; // Invalid step
        
        // Update step indicator
        document.querySelectorAll('.step').forEach((step, idx) => {
            if (idx < stepNum) {
                step.classList.add('completed');
                step.classList.remove('current');
            } else if (idx === stepNum) {
                step.classList.add('current');
                step.classList.remove('completed');
            } else {
                step.classList.remove('current', 'completed');
            }
        });

        // Update step name
        const stepNameElement = document.getElementById('currentStep');
        if (stepNameElement) {
            stepNameElement.innerHTML = '<span class="fw-bold">Starting:</span> Preparing to analyse article';
            if (stepName && stepNum > 0) {
                stepNameElement.innerHTML = `<span class="fw-bold">Step ${stepNum}:</span> ${stepName}`;
            }
        }
    },
};

export default UIHandlers; 