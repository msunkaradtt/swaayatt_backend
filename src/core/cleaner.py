import pymeshlab
import open3d as o3d
import numpy as np
import os
import copy

class MeshCleaner:
    def __init__(self):
        self.ms = pymeshlab.MeshSet()

    def _bake_colors(self, mesh_path):
        print(f"   > [MeshLab] Baking texture to vertex color...")
        self.ms.load_new_mesh(mesh_path)
        try:
            self.ms.compute_color_from_texture_per_vertex()
        except:
            pass 
        
        temp_path = mesh_path.replace(".ply", "_temp.ply")
        self.ms.save_current_mesh(file_name=temp_path, save_vertex_color=True, binary=True)
        self.ms.clear()
        return temp_path

    def _align_to_floor(self, mesh):
        """
        Iteratively finds the floor. 
        If it finds a vertical wall first, it ignores it and keeps searching.
        """
        print(f"   > [Open3D] Searching for the Road Floor...")
        
        # We work on a copy to find the plane, then apply transform to the original
        work_mesh = copy.deepcopy(mesh)
        
        # Max 5 attempts to find a non-vertical plane
        for i in range(5):
            pcd = work_mesh.sample_points_uniformly(number_of_points=10000)
            plane_model, inliers = pcd.segment_plane(distance_threshold=0.2, ransac_n=3, num_iterations=2000)
            [a, b, c, d] = plane_model
            
            # Check orientation (Normal Vector [a,b,c])
            # If it's the floor, the normal should be roughly Up [0,1,0]
            # If it's a wall, the normal will be Sideways (Y near 0)
            
            # Normalize the normal vector
            normal = np.array([a, b, c])
            normal = normal / np.linalg.norm(normal)
            
            # Dot product with UP vector [0,1,0]
            # 1.0 = Perfectly Flat, 0.0 = Perfectly Vertical wall
            flatness = np.abs(np.dot(normal, np.array([0, 1, 0])))
            
            print(f"     Attempt {i+1}: Plane Flatness = {flatness:.2f} (1.0 is Floor, 0.0 is Wall)")

            if flatness > 0.5: # It's somewhat horizontal (The Road!)
                print("     > FOUND ROAD! Aligning...")
                
                # Align this plane to [0,1,0]
                target_normal = np.array([0, 1, 0])
                v = np.cross(normal, target_normal)
                c_val = np.dot(normal, target_normal)
                s = np.linalg.norm(v) + 1e-8
                kmat = np.array([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])
                rot = np.eye(3) + kmat + kmat.dot(kmat) * ((1 - c_val) / (s**2))
                
                mesh.rotate(rot, center=(0,0,0))
                
                # Move to Y=0
                center = mesh.get_center()
                mesh.translate([0, -center[1], 0])
                return mesh
            else:
                print("     > Found a Wall. Ignoring and searching again...")
                # Remove these inliers from the search set (conceptually)
                # In practice, for RANSAC, we can just rotate the mesh to kill this plane? 
                # Easier: Just rotate the mesh 90 degrees and try again
                mesh.rotate(mesh.get_rotation_matrix_from_xyz([np.pi/2, 0, 0]), center=(0,0,0))
                work_mesh = copy.deepcopy(mesh)

        print("   > WARNING: Could not definitively find floor. Using default.")
        return mesh

    def _aggressive_crop_and_clean(self, mesh):
        print(f"   > [Open3D] Aggressive Cutting...")
        
        # 1. CEILING CUT (Strict 1.5m height)
        # This decapitates the balloon/sky
        bbox = mesh.get_axis_aligned_bounding_box()
        min_b = bbox.get_min_bound()
        max_b = bbox.get_max_bound()
        min_b[1] = -2.0
        max_b[1] = 1.5 
        mesh = mesh.crop(o3d.geometry.AxisAlignedBoundingBox(min_b, max_b))

        # 2. WALL SEVER
        mesh.compute_triangle_normals()
        normals = np.asarray(mesh.triangle_normals)
        vertices = np.asarray(mesh.vertices)
        triangles = np.asarray(mesh.triangles)
        
        # Remove anything strictly vertical (Walls)
        mask_keep = np.abs(normals[:, 1]) > 0.3 # Keep things pointing somewhat Up
        mesh.remove_triangles_by_mask(np.invert(mask_keep))
        mesh.remove_unreferenced_vertices()

        # 3. ISLAND KEEP
        # Keep largest connected chunk (Road)
        with o3d.utility.VerbosityContextManager(o3d.utility.VerbosityLevel.Debug) as cm:
            triangle_clusters, cluster_n_triangles, cluster_area = (
                mesh.cluster_connected_triangles()
            )
        if len(cluster_area) > 0:
            largest = int(np.argmax(cluster_area))
            mask = np.asarray(triangle_clusters) == largest
            mesh.remove_triangles_by_mask(np.invert(mask))
            mesh.remove_unreferenced_vertices()
            
        return mesh

    def process_mesh(self, input_path: str, output_path: str) -> str:
        print(f"STATUS: Cleaning {os.path.basename(input_path)}")
        
        # 1. Bake Color
        temp_path = self._bake_colors(input_path)
        
        # 2. Iterative Floor Align
        mesh = o3d.io.read_triangle_mesh(temp_path)
        mesh = self._align_to_floor(mesh)
        
        # 3. Cut & Clean
        mesh = self._aggressive_crop_and_clean(mesh)
        
        # Save for MeshLab
        o3d.io.write_triangle_mesh(temp_path, mesh, write_ascii=False, compressed=True)
        
        # 4. Final Polish (NO HOLE CLOSING)
        self.ms.load_new_mesh(temp_path)
        self.ms.meshing_merge_close_vertices(threshold=pymeshlab.PercentageValue(0.1))
        self.ms.meshing_repair_non_manifold_edges(method='Remove Faces')
        self.ms.meshing_repair_non_manifold_vertices(vertdispratio=0)
        
        # DISABLED HOLE CLOSING TO PREVENT BALLOON
        # self.ms.meshing_close_holes(maxholesize=30) 
        
        self.ms.meshing_decimation_quadric_edge_collapse(targetfacenum=300000)
        
        print(f"STATUS: Saving to {output_path}...")
        self.ms.save_current_mesh(file_name=output_path, save_vertex_color=True, binary=True)
        self.ms.clear()
        
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        return output_path