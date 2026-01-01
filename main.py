from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from typing import List
import os
from src.utils.file_manager import save_upload, PROCESSED_DIR
from src.core.cleaner import MeshCleaner
from src.core.stitcher import MeshStitcher
import pymeshlab

app = FastAPI(title="Backend")

# Initialize Workers
cleaner = MeshCleaner()
stitcher = MeshStitcher()

def run_pipeline(file_paths: List[str], job_id: str):
    """
    Background task that runs the full Cleaning -> Stitching pipeline.
    """
    cleaned_files = []
    
    # Step 1: Clean each chunk individually
    for path in file_paths:
        filename = os.path.basename(path)
        out_path = os.path.join(PROCESSED_DIR, f"clean_{filename}")
        cleaner.process_mesh(path, out_path)
        cleaned_files.append(out_path)
    
    # Step 2: Stitch chunks (Simple sequential stitching for demo)
    # Merges chunk 2 into chunk 1, then chunk 3 into result, etc.
    base_mesh = cleaned_files[0]
    final_output = os.path.join(PROCESSED_DIR, "final_environment.obj")
    
    if len(cleaned_files) > 1:
        current_base = base_mesh
        for i in range(1, len(cleaned_files)):
            next_mesh = cleaned_files[i]
            temp_out = os.path.join(PROCESSED_DIR, f"temp_stitch_{i}.ply")
            
            # Stitch next_mesh onto current_base
            stitcher.stitch(next_mesh, current_base, temp_out)
            current_base = temp_out
        
        # Convert final PLY to OBJ for Unity
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(current_base)
        ms.save_current_mesh(final_output)
    else:
        # If only one chunk, just convert and save
        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(base_mesh)
        ms.save_current_mesh(final_output)

    print(f"SUCCESS: Pipeline finished. Result at {final_output}")

@app.post("/upload-chunks/")
async def upload_chunks(background_tasks: BackgroundTasks, files: List[UploadFile] = File(...)):
    """
    Endpoint for Unity/User to upload multiple mesh chunks.
    Starts the processing pipeline in the background.
    """
    saved_paths = []
    for file in files:
        path = await save_upload(file)
        saved_paths.append(path)
    
    job_id = "job_001" # In a real app, generate a UUID
    
    # Hand off to background task so API responds immediately
    background_tasks.add_task(run_pipeline, saved_paths, job_id)
    
    return {
        "status": "processing_started",
        "job_id": job_id,
        "message": f"Processing {len(files)} chunks in background.",
        "result_path": f"{PROCESSED_DIR}/final_environment.obj" 
        # Unity will watch this path
    }

@app.get("/")
def root():
    return {"message": "Mesh Refinement Server is Running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)