from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from typing import List
import os
import shutil
import uuid


from src.core.cleaner import MeshCleaner
from src.core.stitcher import MeshStitcher
import pymeshlab

app = FastAPI(title="Digital Twin Backend")

# CONFIGURATION
UPLOAD_DIR = "data/uploads"
PROCESSED_DIR = "data/processed"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(PROCESSED_DIR, exist_ok=True)

# Initialize Workers
cleaner = MeshCleaner()
stitcher = MeshStitcher()

async def save_upload(file: UploadFile) -> str:
    """Helper to save uploaded file to disk."""
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    return file_path

def identify_file_pairs(file_paths: List[str]):
    """
    - Mesh has 'mesh' in name.
    - COLMAP has 'points3D' or 'colmap' in name.
    - Matches them if they share a prefix or index.
    """
    meshes = []
    colmaps = []

    for p in file_paths:
        if "points3d" in p.lower() or "colmap" in p.lower():
            colmaps.append(p)
        else:
            meshes.append(p)

    pairs = []

    for mesh in meshes:
        best_match = None
        mesh_name = os.path.basename(mesh).lower()
        
        for col in colmaps:
            col_name = os.path.basename(col).lower()
            common_id = mesh_name.split('_')[0] 
            if common_id in col_name:
                best_match = col
                break
        
        pairs.append({
            "mesh": mesh,
            "colmap": best_match
        })
        
    return pairs

def run_pipeline(file_paths: List[str], job_id: str):
    """
    Background Task: Cleans paired meshes -> Stitches them -> Saves final.
    """
    print(f"[{job_id}] Starting Pipeline with {len(file_paths)} files...")
    
    chunk_pairs = identify_file_pairs(file_paths)
    cleaned_files = []

    for i, pair in enumerate(chunk_pairs):
        mesh_path = pair["mesh"]
        colmap_path = pair["colmap"]
        
        if not colmap_path:
            print(f"[{job_id}] WARNING: No COLMAP file found for {os.path.basename(mesh_path)}. Skipping or cleaning blindly.")
            continue 

        filename = os.path.basename(mesh_path)
        out_path = os.path.join(PROCESSED_DIR, f"clean_{filename}")
        
        try:
            print(f"[{job_id}] Processing Chunk {i+1}: {filename}")
            cleaner.process_mesh(mesh_path, out_path, colmap_path)
            
            cleaner.ms.clear()
            cleaned_files.append(out_path)
        except Exception as e:
            print(f"[{job_id}] ERROR cleaning {filename}: {e}")

    if not cleaned_files:
        print(f"[{job_id}] FAILED: No files were successfully cleaned.")
        return

    final_output = os.path.join(PROCESSED_DIR, "final_environment.obj")
    
    try:
        if len(cleaned_files) > 1:
            print(f"[{job_id}] Stitching {len(cleaned_files)} chunks...")
            current_base = cleaned_files[0]
            
            for i in range(1, len(cleaned_files)):
                next_mesh = cleaned_files[i]
                temp_out = os.path.join(PROCESSED_DIR, f"temp_stitch_{i}.ply")
                
                # Stitch next_mesh onto current_base
                stitcher.stitch(current_base, next_mesh, temp_out)
                current_base = temp_out
            
            ms = pymeshlab.MeshSet()
            ms.load_new_mesh(current_base)
            ms.save_current_mesh(final_output)
            print(f"[{job_id}] SUCCESS: Pipeline finished. Result at {final_output}")
            
        else:
            ms = pymeshlab.MeshSet()
            ms.load_new_mesh(cleaned_files[0])
            ms.save_current_mesh(final_output)
            print(f"[{job_id}] SUCCESS: Single chunk processed. Result at {final_output}")

    except Exception as e:
        print(f"[{job_id}] ERROR during stitching: {e}")


@app.post("/upload-dataset/")
async def upload_dataset(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Upload ALL files at once (Meshes AND COLMAP .ply files).
    The backend will pair them automatically.
    The file names should be like: chunk01_mesh_learnable_sdf.ply and chunk01_points3d.ply.
    """
    saved_paths = []
    for file in files:
        path = await save_upload(file)
        saved_paths.append(path)
    
    job_id = str(uuid.uuid4())
    
    background_tasks.add_task(run_pipeline, saved_paths, job_id)
    
    return {
        "status": "processing_started",
        "job_id": job_id,
        "files_received": len(files),
        "message": "Pipeline started. Files are being paired and processed.",
        "expected_result": f"{PROCESSED_DIR}/final_environment.obj"
    }

@app.get("/")
def root():
    return {"message": "Digital Twin Backend is Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)