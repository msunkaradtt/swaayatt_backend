import os
import shutil
from fastapi import UploadFile

UPLOAD_DIR = "data/uploads"
PROCESSED_DIR = "data/processed"

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

async def save_upload(file: UploadFile) -> str:
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path