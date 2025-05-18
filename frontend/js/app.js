// Main Application Entry Point for TruthTracer
import AnalysisController from './analysis-controller.js';

document.addEventListener('DOMContentLoaded', () => {
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