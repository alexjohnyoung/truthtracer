// API Service Module
// This interacts with the backend API

import Config from './config.js';

const ApiService = {
    // Check API status
    async checkApiStatus() {
        try {
            const response = await fetch(`${Config.getApiUrl()}/`);
            return { connected: response.ok };
        } catch (error) {
            console.error('API Connection Error:', error);
            return { connected: false };
        }
    },
    
    /**
     * Start the analysis of a URL
     * @param {string} url - URL to analyse
     * @param {number} maxReferences - Max number of reference articles
     * @returns {Promise<Object>} - Analysis start response
     */
    async startAnalysis(url, maxReferences = 3) {
        const params = new URLSearchParams();
        params.append('url', url);
        params.append('max_references', maxReferences);
        
        try {
            const response = await fetch(`${Config.getApiUrl()}/analyse-start?${params.toString()}`);
            if (!response.ok) throw new Error(`API error: ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error starting analysis:', error);
            throw error;
        }
    },
    
    /**
     * Check the status of an analysis
     * @param {string} analysisId - ID of the analysis to check
     * @returns {Promise<Object>} - Analysis status response
     */
    async getAnalysisStatus(analysisId) {
        try {
            const response = await fetch(`${Config.getApiUrl()}/analyse-status/${analysisId}`);
            if (!response.ok) throw new Error(`API error: ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Error checking analysis status:', error);
            throw error;
        }
    }
};

export default ApiService; 