import os
import sys

# Ensure the local 'src' directory is in the Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.cleaner import MeshCleaner
from src.core.stitcher import MeshStitcher

# CONFIGURATION
# ---------------------------------------------------------
DATA_DIR = "data/uploads" 
OUTPUT_DIR = "data/processed"

# Define your data pairs: (Mesh File, Its specific COLMAP Sparse Cloud)
# This mapping prevents the blob from 'overwriting' the real road data.
CHUNKS = {
    "chunk1": {
        "mesh": "chunk01_mesh_learnable_sdf.ply",
        "colmap": "chunk1_points3D.ply" 
    },
    "chunk2": {
        "mesh": "chunk02_with_overlap_mesh_learnable_sdf.ply",
        "colmap": "chunk2_points3D.ply" 
    }
}
# ---------------------------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    cleaner = MeshCleaner()
    stitcher = MeshStitcher()
    clean_paths = []

    # --- STEP 1 & 2: RECOVER REAL GEOMETRY FROM BLOBS ---
    for chunk_id, files in CHUNKS.items():
        print(f"\n=== PROCESSING {chunk_id.upper()} ===")
        
        mesh_path = os.path.join(DATA_DIR, files["mesh"])
        colmap_path = os.path.join(DATA_DIR, files["colmap"])
        out_path = os.path.join(OUTPUT_DIR, f"recovered_{chunk_id}.ply")

        if os.path.exists(mesh_path) and os.path.exists(colmap_path):
            # The cleaner now uses the COLMAP file as a 'Truth Mask' to reveal the road
            cleaner.process_mesh(mesh_path, out_path, colmap_path)
            cleaner.ms.clear()
            clean_paths.append(out_path)
        else:
            if not os.path.exists(mesh_path):
                print(f"Error: Mesh file not found at {mesh_path}")
            if not os.path.exists(colmap_path):
                print(f"Error: COLMAP 'Truth Mask' not found at {colmap_path}")

    # --- STEP 3: STITCHING RECOVERED CHUNKS ---
    if len(clean_paths) == 2:
        print("\n=== STEP 3: STITCHING RECOVERED ROAD SECTIONS ===")
        final_output = os.path.join(OUTPUT_DIR, "final_digital_twin_road.ply")
        
        # Stitches the road sections revealed by the Truth Mask
        stitcher.stitch(clean_paths[0], clean_paths[1], final_output)
        
        print(f"\n[SUCCESS] Pipeline Completed.")
        print(f"Final simulation-ready road saved to: {final_output}")
    else:
        print("\n[FAILED] Could not proceed to stitching. Check file paths above.")

if __name__ == "__main__":
    main()