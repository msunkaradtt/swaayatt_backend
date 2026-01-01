import os
from src.core.cleaner import MeshCleaner

# SETUP
INPUT_FILE = "data/uploads/chunk02_with_overlap_mesh_learnable_sdf.ply" # REPLACE with your actual file name
OUTPUT_FILE = "data/processed/test_clean_chunk_24.ply"

# Ensure directories exist
os.makedirs("data/processed", exist_ok=True)

def test_cleaning():
    if not os.path.exists(INPUT_FILE):
        print(f"ERROR: Please put your input ply file at {INPUT_FILE}")
        return

    print("--- STARTING CLEANER TEST ---")
    cleaner = MeshCleaner()
    
    try:
        result = cleaner.process_mesh(INPUT_FILE, OUTPUT_FILE)
        print(f"\nSUCCESS! File saved to: {result}")
        print("Next Steps:")
        print("1. Open the output file in MeshLab or Unity.")
        print("2. Check: Is the road flat?")
        print("3. Check: Is the color preserved?")
        print("4. Check: Are the sky spikes gone?")
    except Exception as e:
        print(f"\nFAILURE: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_cleaning()