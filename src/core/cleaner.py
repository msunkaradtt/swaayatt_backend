import pymeshlab
import open3d as o3d
import numpy as np
import os

class MeshCleaner:
    def __init__(self):
        self.ms = pymeshlab.MeshSet()

    def _fix_orientation_robustly(self, mesh):
        mesh.compute_vertex_normals()
        normals = np.asarray(mesh.vertex_normals)
        if np.median(normals[:, 1]) < 0:
            R = mesh.get_rotation_matrix_from_xyz((np.pi, 0, 0))
            mesh.rotate(R, center=(0, 0, 0))
        
        bbox = mesh.get_axis_aligned_bounding_box()
        mesh.translate([0, -bbox.get_min_bound()[1], 0])
        return mesh

    def _remove_floating_artifacts(self, mesh):
        print("   > [Open3D] Removing floating artifacts (Largest Connected Component)...")
        triangle_clusters, cluster_n_triangles, _ = mesh.cluster_connected_triangles()
        triangle_clusters = np.asarray(triangle_clusters)
        cluster_n_triangles = np.asarray(cluster_n_triangles)
        
        if len(cluster_n_triangles) == 0:
            return mesh
            
        largest_cluster_idx = cluster_n_triangles.argmax()
        triangles_to_keep = (triangle_clusters == largest_cluster_idx)
        mesh.remove_triangles_by_mask(~triangles_to_keep)
        mesh.remove_unreferenced_vertices()
        return mesh

    def _density_aware_clean(self, mesh, colmap_pcd_path):
        print(f"   > [Open3D] Filtering with Density Protection...")
        sparse_pcd = o3d.io.read_point_cloud(colmap_pcd_path)
        bbox = sparse_pcd.get_axis_aligned_bounding_box()
        
        min_b = bbox.get_min_bound() - [15, 7, 15]
        max_b = bbox.get_max_bound() + [15, 20, 15]
        mesh = mesh.crop(o3d.geometry.AxisAlignedBoundingBox(min_b, max_b))
        
        pcd = o3d.geometry.PointCloud()
        pcd.points = mesh.vertices
        pcd.colors = mesh.vertex_colors
        _, ind = pcd.remove_statistical_outlier(nb_neighbors=25, std_ratio=2.0)
        
        verts = np.asarray(mesh.vertices)
        ground_indices = np.where(verts[:, 1] < 0.5)[0]
        final_indices = np.unique(np.concatenate((ind, ground_indices)))
        
        return mesh.select_by_index(final_indices)

    def _flatten_road_surface(self, mesh, height_threshold=0.5):
        print("   > [Open3D] Flattening road surface and updating normals...")
        verts = np.asarray(mesh.vertices)
        ground_indices = np.where(verts[:, 1] < height_threshold)[0]
        
        if len(ground_indices) > 100:
            ground_pcd = o3d.geometry.PointCloud()
            ground_pcd.points = o3d.utility.Vector3dVector(verts[ground_indices])
            plane_model, _ = ground_pcd.segment_plane(distance_threshold=0.05, ransac_n=3, num_iterations=1000)
            a, b, c, d = plane_model
            
            norm_sq = a**2 + b**2 + c**2
            for idx in ground_indices:
                p = verts[idx]
                dist = (a*p[0] + b*p[1] + c*p[2] + d) / norm_sq
                verts[idx] = p - dist * np.array([a, b, c])
                
            mesh.vertices = o3d.utility.Vector3dVector(verts)
        
        mesh.compute_vertex_normals()
        return mesh

    def process_mesh(self, input_path: str, output_path: str, colmap_path: str) -> str:
        print(f"\nSTATUS: High-Fidelity Refinement for {os.path.basename(input_path)}")
        
        self.ms.load_new_mesh(input_path)
        original_id = self.ms.current_mesh_id() 
        
        mesh = o3d.io.read_triangle_mesh(input_path)
        mesh = self._fix_orientation_robustly(mesh)
        mesh = self._density_aware_clean(mesh, colmap_path)
        mesh = self._remove_floating_artifacts(mesh)
        mesh = self._flatten_road_surface(mesh)
        
        temp_path = "data/processed/temp_refined_geo.ply"
        o3d.io.write_triangle_mesh(temp_path, mesh)

        self.ms.load_new_mesh(temp_path)
        
        self.ms.compute_normal_per_vertex()
        self.ms.compute_selection_by_condition_per_vertex(condselect="(nx==0 && ny==0 && nz==0)")
        self.ms.meshing_remove_selected_vertices()

        print("   > [MeshLab] Running Screened Poisson Reconstruction...")
        self.ms.generate_surface_reconstruction_screened_poisson(
            depth=10, 
            fulldepth=2, 
            preclean=True 
        )
        reconstructed_id = self.ms.current_mesh_id()

        print("   > [MeshLab] Trimming low-density artifacts (q < 7)...")
        self.ms.compute_selection_by_condition_per_vertex(condselect="(q < 7)")
        self.ms.meshing_remove_selected_vertices()

        print("   > [MeshLab] Recovering realistic textures...")
        try:
            kwargs = {
                'sourcemesh': original_id,
                'targetmesh': reconstructed_id,
                'colortransfer': True
            }
            self.ms.transfer_attributes_per_vertex(**kwargs)

        except Exception as e:
            print(f"     >> [ERROR] Dynamic color recovery failed: {e}")

        print("   > [MeshLab] Applying final Taubin smoothing and decimation...")
        self.ms.apply_coord_taubin_smoothing(stepsmoothnum=5)
        self.ms.meshing_decimation_quadric_edge_collapse(targetfacenum=450000)

        self.ms.save_current_mesh(output_path, binary=True, save_vertex_color=True)
        
        self.ms.clear()
        if os.path.exists(temp_path): os.remove(temp_path)
        return output_path