import open3d as o3d
import os

class MeshStitcher:
    def __init__(self):
        self.voxel_size = 0.5 

    def _preprocess(self, pcd):
        pcd_down = pcd.voxel_down_sample(self.voxel_size)
        pcd_down.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=self.voxel_size * 2, max_nn=30))
        pcd_fpfh = o3d.pipelines.registration.compute_fpfh_feature(
            pcd_down, o3d.geometry.KDTreeSearchParamHybrid(radius=self.voxel_size * 5, max_nn=100))
        return pcd_down, pcd_fpfh

    def stitch(self, fixed_path, moving_path, output_path):
        print(f"STATUS: Stitching {os.path.basename(moving_path)} -> {os.path.basename(fixed_path)}")
        target = o3d.io.read_triangle_mesh(fixed_path)
        source = o3d.io.read_triangle_mesh(moving_path)

        target_pcd = o3d.geometry.PointCloud(); target_pcd.points = target.vertices
        source_pcd = o3d.geometry.PointCloud(); source_pcd.points = source.vertices
        target_pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        source_pcd.estimate_normals(search_param=o3d.geometry.KDTreeSearchParamHybrid(radius=0.1, max_nn=30))
        
        s_down, s_fpfh = self._preprocess(source_pcd)
        t_down, t_fpfh = self._preprocess(target_pcd)

        print("   > Global Alignment (RANSAC)...")
        result_ransac = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
            s_down, t_down, s_fpfh, t_fpfh, True, self.voxel_size * 1.5,
            o3d.pipelines.registration.TransformationEstimationPointToPoint(False), 3, 
            [o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
             o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(self.voxel_size * 1.5)], 
            o3d.pipelines.registration.RANSACConvergenceCriteria(100000, 0.999)
        )

        print("   > Fine Alignment (ICP)...")
        reg_p2l = o3d.pipelines.registration.registration_icp(
            source_pcd, target_pcd, 0.2, result_ransac.transformation,
            o3d.pipelines.registration.TransformationEstimationPointToPlane()
        )

        source.transform(reg_p2l.transformation)
        combined = target + source
        o3d.io.write_triangle_mesh(output_path, combined, write_ascii=False, compressed=True)
        return output_path