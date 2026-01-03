import open3d as o3d
import numpy as np
import os

class MeshStitcher:
    def __init__(self):
        self.voxel_size = 0.5 

    def stitch(self, fixed_path, moving_path, output_path):
        print(f"STATUS: Smart Stitching {os.path.basename(moving_path)} -> {os.path.basename(fixed_path)}")
        
        target = o3d.io.read_triangle_mesh(fixed_path)
        source = o3d.io.read_triangle_mesh(moving_path)

        target.compute_vertex_normals()
        source.compute_vertex_normals()

        target_pcd = o3d.geometry.PointCloud()
        target_pcd.points = target.vertices
        target_pcd.normals = target.vertex_normals
        
        source_pcd = o3d.geometry.PointCloud()
        source_pcd.points = source.vertices
        source_pcd.normals = source.vertex_normals

        print("   > Refining alignment (ICP Point-to-Plane)...")
        
        threshold = 2.0  # Allow 'snapping' within 2 meters
        init_transformation = np.identity(4) # Trust the current position
        
        try:
            reg_p2l = o3d.pipelines.registration.registration_icp(
                source_pcd, target_pcd, threshold, init_transformation,
                o3d.pipelines.registration.TransformationEstimationPointToPlane(),
                o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=50)
            )
            
            print(f"     >> ICP Fitness: {reg_p2l.fitness:.4f} (Higher is better)")
            print(f"     >> RMSE: {reg_p2l.inlier_rmse:.4f} (Lower is better)")
            
            source.transform(reg_p2l.transformation)
            
        except Exception as e:
            print(f"     >> [WARNING] ICP Failed: {e}. Merging without refinement.")

        print("   > Merging meshes...")
        combined = target + source
        
        combined.compute_vertex_normals()

        o3d.io.write_triangle_mesh(output_path, combined, write_ascii=False, compressed=True)
        print(f"   > Saved stitched result to {output_path}")
        return output_path