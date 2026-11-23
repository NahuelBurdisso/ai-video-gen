import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/api/images", tags=["images"])

INPUT_DIR = Path("D:/ai-input")


@router.get("/list")
async def list_images():
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    images = []
    for f in sorted(INPUT_DIR.iterdir()):
        if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"):
            images.append({
                "name": f.name,
                "size": f.stat().st_size,
                "url": f"/static/input/{f.name}",
            })
    return {"images": images}


@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    dest = INPUT_DIR / file.filename
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return {
        "name": file.filename,
        "size": dest.stat().st_size,
        "url": f"/static/input/{file.filename}",
    }
