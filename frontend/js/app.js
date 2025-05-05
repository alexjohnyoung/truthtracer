// Main Application Entry Point for TruthTracer

import Config from './config.js';
import ApiService from './api.js';
import UIHandlers from './ui-handlers.js';
import AnalysisController from './analysis-controller.js';

document.addEventListener('DOMContentLoaded', () => {
    // Initialise API URL in config modal
    document.getElementById('apiUrlInput').value = Config.getApiUrl();
    
    // Check API status on load
    checkApiStatus();
    
    // Handle API configuration changes
    document.getElementById('saveApiConfig').addEventListener('click', () => {
        const newApiUrl = document.getElementById('apiUrlInput').value.trim();
        if (Config.saveApiUrl(newApiUrl)) {
            checkApiStatus();
            
            // Close the modal
            const configModal = bootstrap.Modal.getInstance(document.getElementById('apiConfigModal'));
            if (configModal) {
                configModal.hide();
            }
        }
    });
    
    // Check API status
    async function checkApiStatus() {
        const statusResult = await ApiService.checkApiStatus();
        UIHandlers.updateApiStatusBadge(statusResult.connected);
    }
    
    // Handle form submission
    document.getElementById('analyseForm').addEventListener('submit', e => {
        e.preventDefault();
        
        const url = document.getElementById('urlInput').value;
        const maxReferences = document.getElementById('maxReferences').value;
        
        AnalysisController.startAnalysis(url, maxReferences);
    });
    
    // Function to scroll to a specific section
    window.scrollToSection = (sectionId) => {
        const element = document.getElementById(sectionId);
        if (element) {
            element.scrollIntoView({behaviour: 'smooth'});
        }
    };
    
    // Clean up when navigating away
    window.addEventListener('beforeunload', () => {
        AnalysisController.stopPolling();
    });
}); 