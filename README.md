# GliAAns - Gliomas Automatic Analysis

## Design Requirement Specification Document

DIBRIS – Università di Genova. Scuola Politecnica, Corso di Ingegneria del Software 80154


<div align='right'> <b> Authors </b> <br> Federico Giovanni Garau <br> Nicolò Trebino  </div>

### REVISION HISTORY

Version | Data | Author(s)| Notes
---------|------|--------|------
1 | 27/08/2025 | Federico G. Garau <br> Nicolò Trebino | First Versionn of the document

## Table of Content

1. [Introduction](#intro)
    1. [Purpose and Scope](#purpose)  
    2. [Definitions](#def)
    3. [Document Overview](#overview)
    4. [Bibliography](#biblio)
2. [Project Description](#description)
    1. [Project Introduction](#project-intro)
    2. [Technologies used](#tech)
    3. [Assumptions and Constraints](#constraints)
3. [System Overview](#system-overview)
    1. [System Architecture](#architecture)
    2. [System Interfaces](#interfaces)
    3. [System Data](#data)
        1. [System Inputs](#inputs)
        2. [System Outputs](#outputs)
4. [System Module 1](#sys-module-1)
    1. [Structural Diagrams](#sd)
        1. [Class Diagram](#cd)
            1. [Class Description](#cd-description)
        2. [Object Diagram](#od)
        3. [Dynamic Models](#dm)
5. [System Module 2](#sys-module-2)
   1. ...

##  <a name="intro"></a>  1 Introduction
    
### <a name="purpose"></a> 1.1 Purpose and Scope
This DRS defines the design specifications of the Pediatric FDOPA Pipeline GUI, a cross-platform desktop application that enables medical personnel to execute and visualize the results of the FDOPA neuroimaging pipeline without requiring programming knowledge. The document is intended for software developers, system architects, and testers.

### <a name="def"></a> 1.2 Definitions
Here are listed some definitions used during the project development
| Acronym	| Definition |
| --- | --- |
| FDOPA	| Fluorodopa (18F), a PET radiotracer |
| VOI	| Volume of Interest in neuroimaging |
| BIDS	| Brain Imaging Data Structure |
| GUI	| Graphical User Interface |
| DICOM	| Standard format for medical imaging |
| NIfTI	| Neuroimaging Informatics Technology Initiative format |

### <a name="overview"></a> 1.3 Document Overview
This document is structured to provide: 

(1) a project description, 

(2) a detailed system overview with software architecture, data, and interfaces,

(3) module-specific designs with diagrams and descriptions.

### <a name="biblio"></a> 1.4 Bibliography
- [docs/ref/res]
- Pediatric FDOPA Pipeline GitHub Repository
- Clinical Paper: FDOPA in Pediatric Oncology
- https://bids-specification.readthedocs.io/en/stable/

## <a name="description"></a> 2 Project Description

### <a name="project-intro"></a> 2.1 Project Introduction 
The Pediatric FDOPA Pipeline GUI addresses the usability gap between the command-line pipeline and clinical workflows. It simplifies input data handling, automates processing, and provides a better user experience for result visualization and export functionalities.

### <a name="tech"></a> 2.2 Technologies used
- Programming language & GUI: Python with PyQt6
- Imaging libraries: pydicom, nibabel, dcm2niix
- Scientific computing & optimization: numpy, scipy, numba
- Image processing & machine learning: scikit-image, scikit-learn, antspyx
- Data handling & statistics: pandas, seaborn, JSON
- Visualization: matplotlib
- Deep Learning model integration: PyTorch

### <a name="constraints"></a> 2.3 Assumption and Constraint 
- Offline execution only (no internet connection required).
- Cross-platform: Windows, Linux, macOS.
- Must comply with hospital data privacy rules (no storage of identifiable data).
- ASSUMPTION: l'utente è un medico che sa il fatto suo!

## <a name="system-overview"></a>  3 System Overview
In this section is shown the Use Case Model of the system:

[ USE CASES DIAGRAM ]

### <a name="architecture"></a>  3.1 System Architecture
The system architecture is designed to be simple and entirely local, reflecting the intended use within hospital environments by medical personnel.
- User: A clinician or medical researcher who interacts directly with the GUI.
- Hardware environment: A standard hospital workstation (desktop or laptop) equipped with sufficient CPU and memory resources. Additionally, a GPU is required to enable efficient execution of the Deep Learning–based segmentation module. No dedicated server or network infrastructure is needed.
- Software environment: The GUI application runs locally on the operating system (Linux, Windows, macOS) and communicates directly with the underlying processing libraries and pipeline components.
- Execution model: All computations, image processing, and data handling are performed locally on the clinician’s computer, ensuring offline functionality and compliance with data privacy requirements.

### <a name="interfaces"></a>  3.2 System Interfaces
The user interacts with the system exclusively through a dedicated Graphical User Interface (GUI). 

The GUI is structured into three main components:
1. Workspace Viewer – Provides an overview of the current working environment, displaying the files and folders that the user is handling. This allows clinicians to keep track of imported datasets and organized outputs.
2. Wizard Panel – Guides the user step by step through the different stages of the workflow. The wizard enables navigation forward and backward across multiple pages, each corresponding to a specific clinical or technical action. The final objective is to lead the clinician seamlessly toward the analysis of patient imaging data using the FDOPA pipeline.
3. NIfTI Viewer – A specialized module that enables visualization, interaction, and modification of imported NIfTI images. This viewer supports detailed inspection and manipulation of neuroimaging data within the workspace, ensuring that clinicians can fully interact with the images before and after pipeline execution.

### <a name="data"></a>  3.3 System Data

#### <a name="inputs"></a>  3.3.1 System Inputs
- DICOM series (`.dcm`)
- NIfTI volumes (`.nii`, `.nii.gz`)
- BIDS directory structure[https://bids-specification.readthedocs.io/en/stable/]

#### <a name="outputs"></a>  3.3.2 System Ouputs
- CSV result tables (`.csv`)
- NIfTI processed volumes (`.nii`, `.nii.gz`)
- H5 files (`.h5`)
- JSON files (`.json`)
- GIF result files (`.gif`)
- TXT logs (`.txt`)

## <a name="sys-module-1"></a>  4 Graphical User Interface

### <a name="sd"></a>  4.1 Structural Diagrams
<details> 
    <summary> Put a summary of the section
    </summary>
    <p>This sub section should describe ...</p>
</details>

#### <a name="cd"></a>  4.1.1 Class diagram
<details> 
    <summary> Put a summary of the section
    </summary>
    <p>This sub section should describe ...</p>
</details>

##### <a name="cd-description"></a>  4.1.1.1 Class Description
<details> 
    <summary> Put a summary of the section
    </summary>
    <p>This sub section should describe ...</p>
</details>

#### <a name="od"></a>  4.1.2 Object diagram
<details> 
    <summary> Put a summary of the section
    </summary>
    <p>This sub section should describe ...</p>
</details>

#### <a name="dm"></a>  4.2 Dynamic Models
<details> 
    <summary> Put a summary of the section
    </summary>
    <p>This sub section should describe ...</p>
</details>
