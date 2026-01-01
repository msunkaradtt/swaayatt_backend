import pymeshlab
import open3d as o3d
import numpy as np
import os

class MeshCleaner:
    def __init__(self):
        self.ms = pymeshlab.MeshSet()

    def _fix_orientation_robustly(self, mesh):
        """Standardizes Up-vector (+Y) using median normal analysis."""
        mesh.compute_vertex_normals()
        normals = np.asarray(mesh.vertex_normals)
        if np.median(normals[:, 1]) < 0:
            R = mesh.get_rotation_matrix_from_xyz((np.pi, 0, 0))
            mesh.rotate(R, center=(0, 0, 0))
        bbox = mesh.get_axis_aligned_bounding_box()
        mesh.translate([0, -bbox.get_min_bound()[1], 0])
        return mesh

    def _density_aware_clean(self, mesh, colmap_pcd_path):
        """
        Protects the road surface from being 'chopped' by using 
        height-based density protection.
        """
        print(f"   > [Open3D] Filtering with Density Protection...")
        sparse_pcd = o3d.io.read_point_cloud(colmap_pcd_path)
        bbox = sparse_pcd.get_axis_aligned_bounding_box()
        
        # 1. Expand safe zone to prevent Chunk 2 truncation
        min_b = bbox.get_min_bound() - [10, 2, 10]
        max_b = bbox.get_max_bound() + [10, 15, 10]
        safe_box = o3d.geometry.AxisAlignedBoundingBox(min_b, max_b)
        mesh = mesh.crop(safe_box)
        
        # 2. Statistical Outlier Removal (with Road Protection)
        pcd = o3d.geometry.PointCloud()
        pcd.points = mesh.vertices
        pcd.colors = mesh.vertex_colors
        
        # Only apply aggressive cleaning to objects above the road (trees/walls)
        # Keep everything near the ground (Y < 0.5) to bridge the gaps.
        cl, ind = pcd.remove_statistical_outlier(nb_neighbors=20, std_ratio=2.0)
        
        # Merge protected ground indices with filtered indices
        verts = np.asarray(mesh.vertices)
        ground_indices = np.where(verts[:, 1] < 0.5)[0]
        final_indices = np.unique(np.concatenate((ind, ground_indices)))
        
        return mesh.select_by_index(final_indices)

    def process_mesh(self, input_path: str, output_path: str, colmap_path: str) -> str:
        print(f"\nSTATUS: Final Surface Completion for {os.path.basename(input_path)}")
        mesh = o3d.io.read_triangle_mesh(input_path)
        
        # 1. Fix Orientation & Recover Surface
        mesh = self._fix_orientation_robustly(mesh)
        mesh = self._density_aware_clean(mesh, colmap_path)
        
        temp_path = "data/processed/temp_final_complete.ply"
        o3d.io.write_triangle_mesh(temp_path, mesh)

        # 2. MeshLab Reconstruction
        self.ms.load_new_mesh(temp_path)
        self.ms.meshing_repair_non_manifold_edges()
        
        # 3. HEAL THE ROAD: Max hole size increased to 2500 for Chunk 2
        print("   > [MeshLab] Bridging remaining road gaps...")
        self.ms.meshing_close_holes(maxholesize=2500)
        
        # 4. Multi-pass smoothing to flatten the junction
        self.ms.apply_coord_laplacian_smoothing(stepsmoothnum=5)
        
        # Final high-res decimation (300k faces)
        self.ms.meshing_decimation_quadric_edge_collapse(targetfacenum=300000)

        self.ms.save_current_mesh(output_path, binary=True, save_vertex_color=True)
        self.ms.clear()
        if os.path.exists(temp_path): os.remove(temp_path)
        return output_path