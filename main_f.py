import os
import sys

# Ensure we can import from src
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.core.cleaner import MeshCleaner
from src.core.stitcher import MeshStitcher

# CONFIGURATION
# ---------------------------------------------------------
# UPDATE THESE PATHS TO MATCH YOUR FOLDER STRUCTURE
DATA_DIR = "data/uploads" 
OUTPUT_DIR = "data/processed"
CHUNK_1_FILE = "chunk01_mesh_learnable_sdf.ply"
CHUNK_2_FILE = "chunk02_with_overlap_mesh_learnable_sdf.ply"
# ---------------------------------------------------------

os.makedirs(OUTPUT_DIR, exist_ok=True)

def main():
    cleaner = MeshCleaner()
    stitcher = MeshStitcher()

    # Define paths
    raw_c1 = os.path.join(DATA_DIR, CHUNK_1_FILE)
    raw_c2 = os.path.join(DATA_DIR, CHUNK_2_FILE)
    
    clean_c1 = os.path.join(OUTPUT_DIR, "clean_chunk_1.ply")
    clean_c2 = os.path.join(OUTPUT_DIR, "clean_chunk_2.ply")
    final_mesh = os.path.join(OUTPUT_DIR, "final_stitched_road.ply")

    # --- STEP 1: CLEAN CHUNK 1 ---
    print("\n=== STEP 1: PROCESSING CHUNK 1 ===")
    if os.path.exists(raw_c1):
        cleaner.process_mesh(raw_c1, clean_c1)
    else:
        print(f"Error: Could not find {raw_c1}")
        return

    # --- STEP 2: CLEAN CHUNK 2 ---
    print("\n=== STEP 2: PROCESSING CHUNK 2 ===")
    if os.path.exists(raw_c2):
        cleaner.process_mesh(raw_c2, clean_c2)
    else:
        print(f"Error: Could not find {raw_c2}")
        return

    # --- STEP 3: STITCHING ---
    print("\n=== STEP 3: STITCHING ===")
    if os.path.exists(clean_c1) and os.path.exists(clean_c2):
        stitcher.stitch(clean_c1, clean_c2, final_mesh)
        print(f"\n[SUCCESS] Pipeline Finished.")
        print(f"Final output saved to: {final_mesh}")
        print("Open this file in MeshLab to verify the stitching.")
    else:
        print("Skipping stitching (missing clean files).")

if __name__ == "__main__":
    main()