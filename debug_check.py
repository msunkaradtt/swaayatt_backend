import pymeshlab
import open3d as o3d
import os

def check_mesh(path, description):
    if not os.path.exists(path):
        print(f"[{description}] File not found: {path}")
        return

    try:
        # Try opening with Open3D
        mesh = o3d.io.read_triangle_mesh(path)
        v_count = len(mesh.vertices)
        f_count = len(mesh.triangles)
        print(f"[{description}] Open3D Read -> Verts: {v_count}, Faces: {f_count}")
        
        if v_count == 0:
            print(f"   !!! WARNING: {description} IS EMPTY !!!")
            
    except Exception as e:
        print(f"[{description}] Failed to open: {e}")

# Check the files in your processed directory
processed_dir = "data/processed"
files = os.listdir(processed_dir)
print("--- Checking Processed Files ---")
for f in files:
    if f.endswith(".obj") or f.endswith(".ply"):
        check_mesh(os.path.join(processed_dir, f), f)