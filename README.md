# Crop Disease Detection Prototype

A local Streamlit application that uses three custom YOLOv5 models to identify
Corn or Grape leaves, detect supported diseases, show confidence scores, provide
concise management recommendations, and produce an annotated image.

This is a screening prototype, not a substitute for diagnosis by an agronomist
or local agricultural extension professional.

## Features

- JPG, JPEG, PNG, and WEBP uploads
- Grayscale Corn detection with the required Corn-biased decision rule
- Crop-specific disease detection and confidence fallbacks
- YOLO bounding-box annotation
- Practical recommendations only for diseased results
- Friendly handling of missing weights and invalid uploads
- Automatic saving of annotated images in `outputs/`
- Launch support through either `python app.py` or `streamlit run app.py`

## Folder Structure

```text
.
├── app.py                       # Streamlit UI and direct Python launcher
├── requirements.txt            # Application and YOLOv5 runtime dependencies
├── README.md                    # Setup, model placement, and usage guide
├── models/
│   ├── crop_detector.pt         # Crop model; add after retraining
│   ├── corn_disease.pt          # Corn disease YOLOv5 weights
│   └── grape_disease.pt         # Grape disease YOLOv5 weights
├── crop_detection/
│   ├── __init__.py
│   ├── predictor.py             # Model loading, inference, boxes, output files
│   ├── disease_logic.py         # Routing, aliases, thresholds, fallbacks
│   └── solutions.py             # Disease-to-recommendation mapping
├── outputs/                     # Generated annotated images
└── tests/
    └── test_disease_logic.py    # Focused fallback and routing tests
```

The existing training-result folders are intentionally left untouched. The
available `best.pt` disease checkpoints have been copied into `models/` under
the filenames used by the application.

## Required Model Placement

All three trained YOLOv5 weight files must use these exact paths:

```text
models/crop_detector.pt
models/corn_disease.pt
models/grape_disease.pt
```

`crop_detector.pt` is not included yet because its training is being rerun.
Until that real checkpoint is placed at the path above, the application starts
normally but displays a clear missing-model message when **Analyze Image** is
pressed. No dummy checkpoint is used.

Only load `.pt` files from a source you trust. YOLOv5 checkpoints may contain
serialized Python model objects.

## Supported Classes

Crop model:

```text
Corn
```

Corn disease model:

```text
healthy
gray_leaf
blight
rust
```

Grape disease model:

```text
Healthy Grape Vine
Black Rot Grape Vine
Blight Grape Vine
```

The included Grape checkpoint stores the shorter labels `Healthy`, `Black Rot`,
and `Blight`. The application maps both short and full forms to the required
display names.

## Decision Logic

1. The application creates an in-memory grayscale copy of the uploaded image
   for the single-class Corn detector. The original image remains unchanged.
2. If any Corn detection survives the model confidence filter, the
   highest-confidence Corn box is selected and the Corn disease model runs.
3. If Corn is not detected, the crop is intentionally assumed to be Grape and
   crop confidence is `0.0%`.
4. The original color image, not the grayscale copy, is sent to the selected
   disease model and used for annotation.
5. Corn uses the highest-confidence supported disease detection. No detection
   returns `Healthy` with `0.0%` confidence.
6. Grape uses a `0.40` disease confidence threshold. No detection or a highest
   confidence below `0.40` returns `Healthy Grape Vine` with `0.0%` confidence.

## Installation

Python 3.10 through 3.12 is recommended for the broadest PyTorch and YOLOv5
compatibility.

### Linux or macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## YOLOv5 Loading

The loader supports two modes:

1. **Local YOLOv5 repository:** set `YOLOV5_REPO` to a trusted YOLOv5 checkout,
   or place that checkout in `./yolov5`. This mode works offline.
2. **Torch Hub:** when no local repository is found, PyTorch downloads and
   caches the official `ultralytics/yolov5` repository. The first model load
   therefore needs internet access; later runs use the local Torch Hub cache.

Example local setup:

```bash
git clone https://github.com/ultralytics/yolov5.git
export YOLOV5_REPO="$PWD/yolov5"
```

On Windows PowerShell:

```powershell
$env:YOLOV5_REPO="$PWD\yolov5"
```

## Running

Standard Streamlit command:

```bash
streamlit run app.py
```

Automatic launcher:

```bash
python app.py
```

The second command starts Streamlit for this application automatically. Use
`Ctrl+C` in the terminal to stop the server.

## Preparing the Crop Dataset

[`prepare_crop_dataset.py`](prepare_crop_dataset.py) follows the split approach
used in `Diseased_Corn.ipynb`. Edit `SOURCE_IMAGES`, `SOURCE_LABELS`, and
`DATASET_ROOT` near the top of the script, then run:

```bash
python prepare_crop_dataset.py
```

The script matches images and labels by filename stem, reads class IDs from the
YOLO annotations, and creates:

```text
dataset/
├── data.yaml
├── images/
│   ├── train/
│   ├── val/
│   └── test/
└── labels/
    ├── train/
    ├── val/
    └── test/
```

Using seed `42`, it places 15 Corn and 15 Grape samples in validation, another
15 of each in test, and all remaining samples in training. Empty-label
background images are assigned to training only. Source files are copied, not
moved.

To intentionally rebuild a populated destination:

```bash
python prepare_crop_dataset.py --overwrite
```

Paths can also be supplied without editing the script:

```bash
python prepare_crop_dataset.py \
  --source-images /path/to/images \
  --source-labels grape_corn_detection_final/obj_train_data \
  --dataset-root dataset
```

## Expected Output

Example diseased result:

```text
Crop: Corn
Crop Confidence: 96.4%

Disease: Rust
Disease Confidence: 91.2%

Recommended Action:
Plant resistant corn hybrids, monitor disease development, and use a locally
registered fungicide only when disease pressure and expected loss justify it.
```

Example healthy Grape fallback:

```text
Crop: Grape
Crop Confidence: 0.0%

Disease: Healthy Grape Vine
Disease Confidence: 0.0%
```

The page also displays the annotated image and provides a download button. A
JPEG copy is written to `outputs/` for each completed analysis.

## Error Handling

- Missing model files are reported with the exact expected path.
- Invalid, empty, oversized, and unsupported uploads are rejected.
- Empty Corn predictions fall back to `Healthy`.
- Empty or low-confidence Grape predictions fall back to
  `Healthy Grape Vine`.
- Model-loading and inference failures produce user-facing guidance.

## Tests

The decision logic tests use Python's built-in assertions and do not load
PyTorch models:

```bash
python -m pytest tests
```

Install `pytest` separately when developing:

```bash
pip install pytest
```

## Recommendation Basis

Recommendations use integrated disease-management principles described by
university extension and crop-protection guidance: resistant varieties,
sanitation or residue management, crop rotation where appropriate, canopy
airflow, scouting, and locally registered fungicides only when justified.

Useful references:

- [Crop Protection Network](https://cropprotectionnetwork.org/)
- [University of Minnesota Extension: Corn pest management](https://extension.umn.edu/corn-pest-management)
- [Penn State Extension: Grapes](https://extension.psu.edu/forage-and-food-crops/fruit/grapes)

Always follow the pesticide label and local regulations. Product availability,
timing, and legal uses vary by crop and region.
