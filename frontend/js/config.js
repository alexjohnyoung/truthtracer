// Configuration Module for TruthTracer
const Config = {
    API_CONFIG_KEY: 'truthtracer_api_url',
    DEFAULT_API_URL: 'http://localhost:8000',
    
    getApiUrl() {
        return this.DEFAULT_API_URL;
    }
};

export default Config;