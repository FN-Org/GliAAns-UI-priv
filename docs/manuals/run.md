# Execution & User Guide
This document explains how to launch the GliAAns-UI application and guides the user through the standard medical workflow for Glioma analysis.

## 1. Launching the Application
### A. For End Users (Compiled Application)

If you are running the standalone version distributed via the dist/ folder:

- **From the graphical interface**:
  1. Navigate to the application folder (e.g., dist/GliAAns-UI). 
  2. Locate GliAAns-UI.exe. 
  3. Double-click to launch.

  - **From the terminal or with wsl**:
    1. Open a terminal in the application folder. 
    2. Run the executable:
      ```bash
      ./GliAAns-UI
      ```
    >   Important for Deep Learning Users: 
    > 
    >   If you intend to use the Tumor Segmentation features, ensure the Deep Learning module has been initialized. If you have not done so, navigate to the deep_learning subfolder inside the application directory and follow the instructions in the [README.md](./../../src/main/deep_learning/README.md) there.

### B. For Developers (Source Code)

If you are working on the source code and want to run the application without compiling:

1. Open your terminal in the project root. 
2. Activate your virtual environment (see [install.md](./install.md)). 
3. Run the entry point:
    ```bash
    python main.py
    ```
   
### 2. Clinical Workflow Guide
Once the GUI is running, follow this pipeline to analyze patient data.

**Step 1: Import Data**

The application supports standard medical imaging formats (DICOM and NIfTI).

1. Go to File > Import MRI, drag&drop or click inside the big squared area.

2. Select the patient's scan directory (DICOM series) or individual file (.nii / .nii.gz).

3. The image will load into the main window.

**Step 2: Skull Stripping**

Before tumor segmentation, it is recommended to remove non-brain tissue.

1. Navigate to the Skull Stripping tab.

2. Select the image that you want to process.

3. Click Execute Skull Stripping.

Note: This process uses external binaries bundled with the app and may take a few moments depending on CPU speed.

**Step 3: Tumor Segmentation (Deep Learning)**

This step utilizes the GPU to identify Glioma regions.

1. Navigate to the Deep Learning tab.

2. Select the desired image that you want to process.

3. Click Run Segmentation.

System Check: The app will verify that the CUDA environment and all the requirements are satisfied.

Once complete, the segmentation mask can be overlaid onto the original MRI.

**Step 4: Run FDOPA Pipeline**
1. Navigate to the Pipeline tab.
2. Select the eligible patient to proceed with the pipeline analysis.
3. Start the pipeline.

**Step 5: Visualization & Reporting**

- 3D Viewer: Use the mouse to rotate and inspect the segmented tumor volume in 3D space.

- Analysis: The side panel will display calculated metrics and pipeline outputs.

- Export: Export the entire workspace or each single folder and file.