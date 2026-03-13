import logging
from fastapi import FastAPI

# Configure logging as per your requirements
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("uvicorn")

app = FastAPI()

@app.get("/")
def read_root():
    try:
        logger.info("Root endpoint accessed")
        return {"message": "Hello from FastAPI + uv!"}
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        raise