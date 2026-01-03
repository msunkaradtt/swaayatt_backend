# Large-Scale Environment for Simulation: Digital Twin Pipeline

**Author:** Mohith Bhargav Sunkara

## 1. Project Overview

This project provides an automated pipeline to build large-scale digital twins from real-world scenes. It takes raw, imperfect 3D meshes (generated from Gaussian Splatting + SLAM) and turns them into a clean, continuous environment ready for simulation.

The system is built as a backend service using **FastAPI**. It handles the following tasks automatically:

1. **Cleaning:** Removes noise, floating artifacts, and fixes geometry.
2. **Refinement:** Flattens road surfaces and improves mesh quality using Poisson reconstruction.
3. **Stitching:** Merges multiple mesh chunks into one single map using advanced registration techniques.

## 2. Features

* **Automatic File Pairing:** You can upload all files at once. The system automatically matches mesh files with their corresponding COLMAP point cloud files.
* **Density-Aware Cleaning:** Uses the original COLMAP point cloud to identify and keep only the valid parts of the mesh.
* **Road Flattening:** Detects the ground using mathematics (RANSAC plane fitting) and flattens it to make it smooth for vehicles.
* **Robust Multi-Stage Stitching:** Implements a "Coarse-to-Fine" registration strategy using FPFH features for rough alignment and Point-to-Plane ICP for precise locking.
* **Texture Recovery:** Preserves the original colors during the remeshing process.

## 3. Directory Structure

```text
swaayatt_backend/
├── data/
│   ├── uploads/          # Where raw files are saved
│   └── processed/        # Final cleaned and stitched outputs
├── src/
│   └── core/
│       ├── cleaner.py    # Logic for mesh cleaning and refining
│       └── stitcher.py   # Logic for aligning and merging meshes
├── main.py               # The API server entry point
├── requirements.txt      # List of software dependencies
└── .gitignore

```

## 4. Setup Instructions

### Prerequisites

* Python 3.12.10
* Operating System: Windows

### Installation

1. **Clone the repository** (or unzip the project folder).
2. **Create a virtual environment** (optional but recommended):
```bash
py -3.12 -m venv venv
venv\Scripts\activate  # for Windows

```


3. **Install dependencies**:
This project relies on `FastAPI`, `Open3D`, `PyMeshLab`, and `NumPy`. Install them using the provided file:
```bash
pip install -r requirements.txt

```



## 5. Execution Steps

### Starting the Server

To run the automation pipeline, start the backend server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000

```

* The server will start at `http://localhost:8000`.
* You can see the interactive API documentation at `http://localhost:8000/docs`.

### Running the Pipeline

You do not need to run manual scripts. You can trigger the process via the API.

1. Open your web browser and go to `http://localhost:8000/docs`.
2. Find the **POST** endpoint `/upload-dataset/`.
3. Click **Try it out**.
4. Upload all your `.ply` or `.obj` files at once. You should include:
* The mesh files (e.g., `chunk1_mesh.ply`).
* The COLMAP/Points3D files (e.g., `chunk1_points3D.ply`).


5. Click **Execute**.

The system will verify the files, start a background job, and return a `job_id`.

### Check Results

Check the server logs to see the progress. Once finished, the files will be saved in the `data/processed/` folder:

* `clean_chunkX.ply`: The cleaned version of individual chunks.
* `final_environment.obj`: The final stitched digital twin.

## 6. Algorithmic Approach

### A. Mesh Cleaning (`cleaner.py`)

The cleaning process follows these mathematical steps:

1. **Orientation Fix:** We check the vertex normals. If the mesh is upside down (median normal y < 0), we rotate it 180 degrees.
2. **Statistical Outlier Removal:** We load the sparse COLMAP point cloud. We remove mesh vertices that are too far from the dense areas of the point cloud. This removes "floating" noise in the sky or underground.
3. **Road Flattening:** We assume the road is roughly at height `y=0`. We use RANSAC (Random Sample Consensus) to find the best geometric plane for the floor and project noisy road vertices onto this flat plane.
4. **Poisson Reconstruction:** We use PyMeshLab to generate a watertight surface from the points, filling small holes.

### B. Stitching (`stitcher.py`)

To merge chunks (like Chunk 1 and Chunk 2), we use a robust **Global-to-Local** registration pipeline using Open3D:

1. **Preprocessing & Feature Extraction:**
* The system downsamples the high-resolution meshes using a voxel grid (0.5 units) to make calculations faster.
* It computes **FPFH (Fast Point Feature Histograms)** features. These describe the 3D shape around each point, allowing the algorithm to recognize similar shapes even if they are in different positions.


2. **Global Alignment (RANSAC):**
* We use a RANSAC-based matching algorithm that compares the FPFH features of the two meshes.
* This step finds a rough alignment without needing a manual starting position. It checks millions of possibilities to find the one where the shapes overlap best.


3. **Fine Alignment (Point-to-Plane ICP):**
* Once loosely aligned, we run the **Iterative Closest Point (ICP)** algorithm.
* We specifically use the **Point-to-Plane** metric (instead of Point-to-Point), which allows the meshes to slide along flat surfaces (like roads) to find the perfect lock.


4. **Merging:**
* The "moving" mesh is transformed using the calculated matrix and merged into the "fixed" mesh to create a single continuous environment.


## 7. Dependencies

* **FastAPI & Uvicorn:** For creating the automation server.
* **Open3D:** For geometry processing, feature extraction (FPFH), and registration (RANSAC/ICP).
* **PyMeshLab:** For advanced mesh filters (Poisson reconstruction, simplification).
* **NumPy:** For numerical calculations.

---