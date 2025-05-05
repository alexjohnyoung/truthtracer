// Analysis Controller Module

import ApiService from './api.js';
import UIHandlers from './ui-handlers.js';
import ResultsRenderer from './results-renderer.js';

const AnalysisController = {
    // Configuration
    MAX_ATTEMPTS: 150,
    POLL_INTERVAL: 2000,
    
    // State
    pollAttempts: 0,
    isCompleted: false,
    pollIntervalId: null,
    
    // Start analysis
    async startAnalysis(url, maxReferences) {
        try {
            // Reset UI and state
            UIHandlers.resetForNewAnalysis();
            this.stopPolling();
            this.pollAttempts = 0;
            this.isCompleted = false;
            
            // Start analysis
            const data = await ApiService.startAnalysis(url, maxReferences);
            if (!data.analysis_id) {
                throw new Error("No analysis ID returned");
            }
            
            UIHandlers.addLogMessage(`Analysis started (ID: ${data.analysis_id.substring(0, 8)}...)`);
            this.pollForStatus(data.analysis_id);
        } catch (error) {
            UIHandlers.addLogMessage(`Error: ${error.message}`, 'error');
        }
    },
    
    // Poll for status updates
    pollForStatus(analysisId) {
        const checkStatus = async () => {
            // Check if we should stop polling
            if (this.pollAttempts >= this.MAX_ATTEMPTS || this.isCompleted) {
                this.stopPolling();
                if (!this.isCompleted) {
                    UIHandlers.addLogMessage("Analysis timed out", 'error');
                }
                return;
            }
            
            this.pollAttempts++;
            
            try {
                // Get status update
                const data = await ApiService.getAnalysisStatus(analysisId);
                
                // Update UI
                UIHandlers.updateStatusDisplay(data);
                UIHandlers.updateLogMessages(data);
                
                // Check for completion or error
                if (data.error) {
                    UIHandlers.addLogMessage(`Error: ${data.error}`, 'error');
                    this.isCompleted = true;
                    this.stopPolling();
                } else if (data.complete && data.success) {
                    UIHandlers.addLogMessage("Analysis complete", 'success');
                    this.isCompleted = true;
                    this.stopPolling();
                    
                    if (data.result) {
                        ResultsRenderer.displayResults(data);
                    }
                }
            } catch (error) {
                UIHandlers.addLogMessage(`API error: ${error.message}`, 'warning');
            }
        };
        
        // Start polling
        checkStatus();
        this.pollIntervalId = setInterval(checkStatus, this.POLL_INTERVAL);
    },
    
    // Stop polling
    stopPolling() {
        if (this.pollIntervalId) {
            clearInterval(this.pollIntervalId);
            this.pollIntervalId = null;
        }
    },
    
};

export default AnalysisController; 