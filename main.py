"""
TruthTracer API - News article analysis for detecting misleading content

This FastAPI application provides endpoints for analysing news articles by:
1. Processing the main article content
2. Finding related reference articles
3. Cross-referencing them to detect potentially misleading information
4. Providing status updates throughout the analysis process

The application uses asynchronous processing with a RESTful API architecture.
"""

# Import and load environment variables first
from dotenv import load_dotenv
load_dotenv()

import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import os

# Uvicorn
import uvicorn

# FastAPI framework
from fastapi import FastAPI, Query, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel, Field

# Application-specific imports
from src.processing.news_processor import NewsProcessor
from src.scraping.controller import ScrapingController
from src.utils.status import update_status, analysis_store, set_current_analysis_id
from src.google.google import GoogleSearchScraper

# Initialise FastAPI application
app = FastAPI(
    title="TruthTracer API",
    description="News article analysis for detecting misleading content",
    version="1.0.0"
)

# Configure CORS for allowing frontend applications to access the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

#------------------------------------------------------------------------------
# PYDANTIC MODELS
#------------------------------------------------------------------------------

class StatusResponse(BaseModel):
    """Model for status information"""
    progress: int = Field(..., description="Analysis progress percentage (0-100)")
    message: str = Field(..., description="Current status message")
    step_name: str = Field("", description="Name of the current processing step")
    step: int = Field(0, description="Current step number")

class AnalysisStartResponse(BaseModel):
    """Model for analysis start response"""
    analysis_id: str = Field(..., description="Unique ID for tracking the analysis")
    url: str = Field(..., description="URL of the article being analysed")
    status: StatusResponse = Field(..., description="Initial status information")

class AnalysisStatusResponse(BaseModel):
    """Model for analysis status response"""
    url: str = Field(..., description="URL of the article being analysed")
    status: StatusResponse = Field(..., description="Current status information")
    log_messages: List[str] = Field(..., description="Log messages from the analysis process")
    complete: bool = Field(..., description="Whether the analysis is complete")
    success: Optional[bool] = Field(None, description="Whether the analysis was successful (only if complete)")
    error: Optional[str] = Field(None, description="Error message if analysis failed")
    result: Optional[Dict[str, Any]] = Field(None, description="Analysis results if successful and complete")

class ApiInfo(BaseModel):
    """Model for API information"""
    name: str
    version: str
    description: str
    endpoints: List[Dict[str, str]]


# Create global service instances
scraping_controller = ScrapingController()
news_processor = NewsProcessor(scraping_controller)

# Lifecycle Event Handlers
@app.on_event("startup")
async def startup_event():
    """Application startup event handler"""
    print("TruthTracer API starting up")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler - clean up resources"""
    print("TruthTracer API shutting down, cleaning up resources...")
    
    # Flag to indicate shutdown is in progress to prevent new tasks
    app.state.shutting_down = True
    
    # Cleanup resources
    try:
        if hasattr(news_processor, 'cleanup'):
            news_processor.cleanup()
            print("Successfully cleaned up NewsProcessor resources")
    except Exception as e:
        print(f"Error cleaning up NewsProcessor: {str(e)}")
    
    try:
        if hasattr(scraping_controller, 'cleanup'):
            scraping_controller.cleanup()
            print("Successfully cleaned up ScrapingController resources")
    except Exception as e:
        print(f"Error cleaning up ScrapingController: {str(e)}")
    
    print("All resources cleaned up successfully")

#------------------------------------------------------------------------------
# CORE ANALYSIS FUNCTIONS
#------------------------------------------------------------------------------

async def process_url_async(analysis_id: str, url: str, max_references: int = 3, days_old: int = 7):
    """
    Background task to process a URL asynchronously
    
    Args:
        analysis_id: Unique ID for tracking this analysis
        url: URL to analyse
        max_references: Maximum number of reference articles to process
        days_old: Maximum age of reference articles in days
    """
    set_current_analysis_id(analysis_id)
    
    # Initialise result structure
    analysis_store[analysis_id]["complete"] = False
    analysis_store[analysis_id]["success"] = False
    
    # Block requests if the server is shutting down
    try:
        if hasattr(app.state, "shutting_down") and app.state.shutting_down:
            analysis_store[analysis_id]["error"] = "Server is shutting down, cannot process request"
            analysis_store[analysis_id]["complete"] = True
            analysis_store[analysis_id]["success"] = False
            update_status("Analysis cancelled: server is shutting down", 100, "Error", -1)
            return
            
        # Start article analysis 
        result = await news_processor.analyse_article(url, max_references=max_references, days_old=days_old)
        
        if not result:
            analysis_store[analysis_id]["error"] = "Failed to analyse article"
            analysis_store[analysis_id]["complete"] = True
            analysis_store[analysis_id]["success"] = False
            update_status("Analysis failed: could not process article", 100, "Error", -1)
            return
               
        analysis_store[analysis_id]["result"] = result
        analysis_store[analysis_id]["success"] = True
        
        # Final status update
        update_status("Analysis complete", 100, "Complete", 5)
        
    except Exception as e:
        # Log and store any errors
        error_message = f"Error analysing article: {str(e)}"
        update_status(error_message, 100, "Error", -1)
        analysis_store[analysis_id]["error"] = error_message
        analysis_store[analysis_id]["success"] = False

    finally:
        # Mark the analysis as complete
        analysis_store[analysis_id]["complete"] = True
        set_current_analysis_id(None)
        print(f"Analysis {analysis_id} completed")

#------------------------------------------------------------------------------
# API ENDPOINTS
#------------------------------------------------------------------------------

@app.get("/", response_model=ApiInfo)
async def api_root():
    """API root endpoint providing basic API information"""
    return {
        "name": "TruthTracer API",
        "version": "1.0.0",
        "description": "News article analysis for detecting misleading content",
        "endpoints": [
            {
                "path": "/analyse-start",
                "description": "Start asynchronous analysis of a news article"
            },
            {
                "path": "/analyse-status/{analysis_id}",
                "description": "Check the status of an ongoing analysis"
            }
        ]
    }

@app.get("/analyse-start", response_model=AnalysisStartResponse)
async def analyse_start(
    background_tasks: BackgroundTasks,
    url: str = Query(..., description="URL of the article to analyse"),
    days_old: int = Query(7, description="Time window for reference search in days", ge=1, le=3650),
    max_references: int = Query(3, description="Maximum number of reference articles to process", ge=1, le=20)
):
    """
    Start asynchronous analysis of a news article
    
    This endpoint initiates the analysis process in the background and returns
    immediately with an analysis ID that can be used to check the status.
    """
    # Generate a unique ID for this analysis
    analysis_id = str(uuid.uuid4())
    
    # Initialise status information
    status_info = {
        "message": "Analysis queued",
        "progress": 0,
        "step_name": "Initialisation",
        "step": 0
    }
    
    # Store initial information
    analysis_store[analysis_id] = {
        "url": url,
        "status": status_info,
        "log_messages": ["[" + datetime.now().strftime("%H:%M:%S") + "] Analysis queued"],
        "result": None,
        "complete": False,
        "error": None,
        "timestamp": datetime.now().isoformat()
    }
    
    # Schedule the background task
    background_tasks.add_task(
        process_url_async,
        analysis_id=analysis_id,
        url=url,
        max_references=max_references,
        days_old=days_old
    )
    
    # Return initial status
    return {
        "analysis_id": analysis_id,
        "url": url,
        "status": status_info
    }

@app.get("/analyse-status/{analysis_id}", response_model=AnalysisStatusResponse)
async def analyse_status(analysis_id: str):
    """
    Check the status of an ongoing analysis
    
    This endpoint returns the current status of the analysis identified by the
    given analysis_id, including progress information and any log messages.
    """
    # Check if the analysis ID exists
    if analysis_id not in analysis_store:
        raise HTTPException(status_code=404, detail="Analysis ID not found")
    
    # Get the analysis information
    analysis_info = analysis_store[analysis_id]
    
    # Construct the response
    response = {
        "url": analysis_info["url"],
        "status": analysis_info["status"],
        "log_messages": analysis_info["log_messages"],
        "complete": analysis_info["complete"]
    }
    
    # Add success/error information if complete
    if analysis_info["complete"]:
        response["success"] = analysis_info["success"]
        if not analysis_info["success"]:
            response["error"] = analysis_info["error"]
        else:
            response["result"] = analysis_info["result"]
    
    return response

# Using a custom OpenAPI schema to improve documentation
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title="TruthTracer API",
        version="1.0.0",
        description="API for analysing news articles to detect potentially misleading content",
        routes=app.routes,
    )
    
    # For better organisation
    openapi_schema["tags"] = [
        {
            "name": "Analysis",
            "description": "Endpoints for article analysis"
        },
        {
            "name": "Status",
            "description": "Endpoints for checking analysis status"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True) 