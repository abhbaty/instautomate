import uvicorn
from main import app

# Hugging Face Gradio Spaces always expose port 7860.
# By running our FastAPI app on this port inside app.py, 
# the Space will host our web app perfectly on the Free tier.
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=7860)
