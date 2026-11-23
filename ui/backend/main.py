import sys
from pathlib import Path
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Add project root to path so we can import pipeline modules
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from .routers import chat, pipeline, images


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="AI Video Director", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static file mounts for images and outputs
INPUT_DIR = Path("D:/ai-input")
OUTPUT_DIR = Path("D:/ai-output")
INPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static/input", StaticFiles(directory=str(INPUT_DIR)), name="input")
app.mount("/static/output", StaticFiles(directory=str(OUTPUT_DIR)), name="output")

app.include_router(chat.router)
app.include_router(pipeline.router)
app.include_router(images.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
