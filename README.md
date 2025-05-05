# TruthTracer

TruthTracer is a sophisticated news article analysis tool designed to detect potentially misleading content by cross-referencing information with multiple sources.

## Overview

TruthTracer combines web scraping and natural language processing to provide an objective assessment of news article reliability. 

The system works by:

1. Analysing a primary news article's content
2. Finding related articles from other publications
3. Cross-referencing information between sources
4. Identifying potential discrepancies, omissions, or misleading content
5. Providing a detailed report on the article's reliability

## Features

- **Article Content Extraction**: Automatically extracts the meaningful content from news articles, removing ads, navigation, and other noise
- **Reference Article Discovery**: Finds related articles from other sources covering the same topic
- **Cross-Reference Analysis**: Compares how different sources report on the same events
- **Misleading Content Detection**: Identifies potentially misleading statements, omissions, or distortions
- **Clean API Interface**: RESTful API for easy integration with other systems
- **Modern Web Interface**: User-friendly frontend for analysing articles

## System Architecture

TruthTracer consists of several components:

- **Scraping Module**: Extracts content from news websites using both static and dynamic scraping techniques
- **Processing Module**: Cleans, normalises, and analyses text content
- **Google Module**: Handles search operations to find reference articles
- **Utilities**: Common utility functions for text processing, URL handling, etc.
- **API**: FastAPI backend that coordinates the analysis process
- **Frontend**: Simple, elegant web interface for submitting articles and viewing results

## Installation

### Prerequisites

- Python 3.9+ 
- Ollama
- Chrome/Chromium (for dynamic web scraping)

### Setup

1. Clone the repository:
   ```
   git clone https://github.com/alexjohnyoung/truthtracer.git
   cd truthtracer
   ```

2. Create and activate a virtual environment:
   ```
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Setup ChromeDriver (required for local API deployment):
   - Download the appropriate version of ChromeDriver that matches your Chrome/Chromium version 
   - For Windows: Place the chromedriver.exe in your PATH or in the project's root directory
   - For macOS/Linux: Place the chromedriver executable in your PATH or in the project's root directory

## Usage

### Starting the API Server

```
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Starting the Frontend Server

The frontend is served via a web server.

Navigate to the frontend directory and run:

```
python serve.py
```

This will start a web server on port 8080 and automatically open your browser.

To use a different port, run with the '--port' argument.

### Using the API Directly

The API provides endpoints for starting an analysis and checking its status:

- `GET /analyse-start?url={article_url}&max_references={number}` - Start analysing an article
- `GET /analyse-status/{analysis_id}` - Check analysis status and get results

## Development

### Project Structure

- `src/` - Main source code directory
  - `utils/` - Utility functions and helpers
  - `scraping/` - Web scraping modules
  - `processing/` - Text processing and analysis modules
  - `google/` - Google search functionality
- `frontend/` - Web interface
- `main.py` - API entry point

## Acknowledgements

- Big thank you to my supervisors at Munster Technological University for their guidance and support
- All contributors to the open-source projects that make this possible
