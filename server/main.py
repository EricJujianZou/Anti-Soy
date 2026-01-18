import sys
import os

# Add the current directory to sys.path to allow absolute imports 
# when running from the project root (e.g. uvicorn server.main:app)
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import init_db
from routers import analysis

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize DB
@app.on_event("startup")
def on_startup():
    init_db()

app.include_router(analysis.router)

@app.get("/")
def read_root():
    return {"message": "Anti-Soy Backend Running"}
