# Crop Disease Detection: Complete Codebase Guide

## Purpose of this guide

This document explains the project as a complete system rather than as isolated
lines of Python. It covers:

- The architecture and responsibility of every source package.
- Every class and function in the runtime code.
- What happens to an uploaded image or camera frame, step by step.
- How YOLOv5, Groq, Streamlit, SQLite, and the medication database interact.
- What is stored in memory, on disk, and in the database.
- What the tests verify.
- The purpose of the non-code folders and artifacts.
- Important limitations, implementation details, and likely viva questions.

The shortest accurate description of the project is:

> A single-user Streamlit application that validates a crop image, uses a
> Corn-first YOLOv5 routing pipeline to select a crop-specific disease model,
> annotates and saves the result, uses a controlled medication database plus
> Groq to generate a treatment explanation, and stores sessions and treatment
> progress in SQLite.

---

## 1. System architecture

The application has four main layers.

```text
┌────────────────────────────────────────────────────────────────────┐
│ Presentation and orchestration                                    │
│ app.py                                                             │
│ Streamlit pages, widgets, camera, navigation, result rendering     │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                ┌──────────────┼───────────────┐
                │              │               │
                ▼              ▼               ▼
┌──────────────────────┐ ┌──────────────────┐ ┌─────────────────────┐
│ Detection layer      │ │ Chatbot layer    │ │ Tracking layer      │
│ crop_detection/      │ │ chatbot/         │ │ tracking/           │
│                      │ │                  │ │                     │
│ YOLO loading         │ │ Groq calls       │ │ Dataclasses         │
│ Inference            │ │ Prompt rules     │ │ SQLite persistence  │
│ Crop routing         │ │ Clarification    │ │ Medicine-table UI   │
│ Disease selection    │ │ Summarization    │ │ Progress chart      │
│ Image annotation     │ │ Treatment flow   │ │                     │
└──────────┬───────────┘ └─────────┬────────┘ └──────────┬──────────┘
           │                       │                     │
           ▼                       ▼                     ▼
  models/*.pt              data/medications.json       tracking.db
  outputs/*.jpg            GROQ_API_KEY                SQLite file
```

### Separation of responsibilities

| Part | Main responsibility | What it deliberately does not own |
|---|---|---|
| `app.py` | User interface and workflow orchestration | YOLO implementation, SQL schema, prompt content |
| `crop_detection/` | Model loading, inference, routing, annotation | Streamlit screens, Groq, medicine tracking |
| `chatbot/` | Conversation state, prompts, Groq calls, treatment orchestration | YOLO tensor processing and table rendering |
| `tracking/` | Session/medicine models, SQLite, tracker UI | Crop inference and LLM prompting |
| `data/medications.json` | Approved treatment context supplied to Groq | Program logic |
| `tests/` | Isolated checks of important rules | Full browser/end-to-end testing |

---

## 2. Repository map

```text
Disease Detection/
├── app.py
├── requirements.txt
├── README.md
├── PROJECT_CODEBASE_GUIDE.md
├── .gitignore
│
├── chatbot/
│   ├── __init__.py
│   ├── state.py
│   ├── handlers.py
│   ├── groq_client.py
│   ├── prompts.py
│   ├── clarification.py
│   └── summarizer.py
│
├── crop_detection/
│   ├── __init__.py
│   ├── predictor.py
│   ├── disease_logic.py
│   └── solutions.py
│
├── tracking/
│   ├── __init__.py
│   ├── models.py
│   ├── persistence.py
│   └── tracker_ui.py
│
├── data/
│   └── medications.json
│
├── models/
│   ├── crop_detector.pt
│   ├── corn_disease.pt
│   ├── grape_disease.pt
│   └── older/versioned checkpoints
│
├── outputs/
│   ├── .gitkeep
│   └── analysis_<timestamp>_<id>.jpg
│
├── tests/
│   ├── test_disease_logic.py
│   ├── test_predictor.py
│   ├── test_groq_client.py
│   ├── test_clarification.py
│   ├── test_summarizer.py
│   └── test_persistence.py
│
├── docs/
│   ├── MULTI_USER_UPGRADE.md
│   ├── ANKIT_TASKS.md
│   ├── ISHAAN_TASKS.md
│   └── SUHAAN_TASKS.md
│
├── grape_disease/
├── corn_disease_v4/
├── model2_test/
├── grape_corn_detection_final/
└── sample/test image files
```

### Runtime source versus artifacts

The Python files under `chatbot/`, `crop_detection/`, and `tracking/`, plus
`app.py`, are runtime source code.

The `.pt` files are trained PyTorch model checkpoints. They contain learned
weights and, depending on checkpoint format, serialized model objects. They are
not normal Python source files.

The folders `grape_disease/`, `corn_disease_v4/`, and `model2_test/` contain
training outputs such as:

- `best.pt` and `last.pt`.
- Confusion matrices.
- Precision, recall, F1, and PR curves.
- Training batch images.
- Validation predictions.
- Hyperparameter and option files.
- Training result CSV files.

`grape_corn_detection_final/` contains crop-detection dataset metadata and YOLO
label text files. These files support training and dataset history; the running
application does not iterate through that training folder.

The root-level JPG, JPEG, and WEBP files are manual test images. They are not
automatically loaded by the app.

---

## 3. Application startup

The application supports two launch commands:

```bash
streamlit run app.py
```

and:

```bash
python app.py
```

### Startup using `streamlit run app.py`

1. Streamlit creates a script-run context.
2. Python executes `app.py`.
3. The main guard calls `launch()`.
4. `_is_streamlit_runtime()` finds the existing Streamlit context.
5. `launch()` calls `streamlit_main()`.
6. Streamlit constructs the page.

### Startup using `python app.py`

1. Python executes `app.py` normally.
2. The main guard calls `launch()`.
3. `launch()` confirms that Streamlit is installed.
4. `_is_streamlit_runtime()` returns `False`.
5. The code runs a child command equivalent to:

   ```bash
   <current-python> -m streamlit run <absolute-path-to-app.py>
   ```

6. The new Streamlit process executes the normal startup path.

Using `sys.executable` is important because it launches Streamlit with the same
Python interpreter or virtual environment that ran `app.py`.

---

## 4. The Streamlit execution model

Streamlit normally reruns the Python script from top to bottom after a widget
interaction.

This project survives those reruns through three mechanisms:

1. `st.session_state`
   - Active session ID.
   - Current UI mode.
   - Captured camera frame.
   - In-memory `CropSession` objects.
   - Whether Groq is currently responding.

2. `@st.cache_resource`
   - Keeps the expensive `ModelManager` and loaded YOLO models available across
     reruns.

3. SQLite
   - Persists session metadata, summaries, and medicine entries across browser
     and server restarts.

`st.rerun()` is therefore not restarting the whole product. It is asking
Streamlit to execute the script again and reconstruct the UI from stored state.

---

## 5. Complete image journey: uploaded image

This is the most important end-to-end flow to understand.

### Stage 1: User reaches the upload screen

Module: `app.py`

1. The user creates or selects a session.
2. `st.session_state.chat_mode` is initially `ONBOARDING`.
3. Clicking **Upload Image** calls:

   ```python
   set_chat_mode("AWAITING_UPLOAD")
   st.rerun()
   ```

4. On the rerun, the `AWAITING_UPLOAD` branch displays
   `st.file_uploader()`.

### Stage 2: Browser sends the uploaded file

Module: `app.py`

The browser sends the file to Streamlit. Streamlit exposes it as an
`UploadedFile`-like object.

The UI filter permits:

- JPG.
- JPEG.
- PNG.
- WEBP.

The UI filter is not considered sufficient validation. The file is passed to
`load_uploaded_image()`.

### Stage 3: File validation

Function: `app.load_uploaded_image(uploaded_file)`

The function performs these checks in order:

1. Extracts the lowercase filename suffix.
2. Rejects unsupported suffixes.
3. Reads the entire file into `bytes`.
4. Rejects an empty file.
5. Rejects a file over `15 * 1024 * 1024` bytes.
6. Wraps the bytes in `io.BytesIO`, which behaves like an in-memory file.
7. Opens the bytes with Pillow.
8. Calls `candidate.verify()` to verify that the bytes form a readable image.
9. Reopens the image because `verify()` consumes/invalidates the first Pillow
   image object for normal loading.
10. Applies EXIF orientation with `ImageOps.exif_transpose()`.
11. Converts the image to three-channel RGB.
12. Calls `image.load()` to decode pixels before the temporary stream closes.
13. Rejects images smaller than 16 by 16 pixels.
14. Returns a fully loaded `PIL.Image.Image`.

At this point, the image has not been saved to disk and no model has run.

### Stage 4: User starts analysis

Module: `app.py`

When the user clicks **Analyse Image**, the app calls:

```python
result = analyze_image(image, get_model_manager())
```

`get_model_manager()` is decorated with `@st.cache_resource`, so the same
manager is reused across Streamlit reruns.

### Stage 5: Model paths are configured

Module: `crop_detection/predictor.py`

Function: `ModelManager.from_project_root(PROJECT_ROOT)`

The manager points to:

```text
models/crop_detector.pt
models/corn_disease.pt
models/grape_disease.pt
outputs/
```

It also searches for a local YOLOv5 repository:

1. Path specified by `YOLOV5_REPO`.
2. `<project>/yolov5`.
3. `<project-parent>/yolov5`.

The folder is accepted only if it contains `hubconf.py`.

### Stage 6: A grayscale crop-detection copy is created

Module: `crop_detection/predictor.py`

Function: `create_grayscale_copy(image)`

```python
return image.convert("L").convert("RGB")
```

`"L"` creates one-channel grayscale. Converting back to `"RGB"` duplicates the
gray value across three channels so the YOLO model still receives a
three-channel image.

The original image is not mutated. It remains in colour for disease inference
and final annotation.

### Stage 7: Crop model is loaded

Module: `crop_detection/predictor.py`

Call path:

```text
manager.crop_model()
→ ModelManager._get_or_load(...)
→ load_yolov5_model(...)
```

The manager's internal `_models` dictionary prevents the same model from being
loaded more than once per manager.

`load_yolov5_model()`:

1. Resolves the checkpoint path.
2. Raises `FileNotFoundError` if the model file is missing.
3. Lazily imports PyTorch.
4. Sets `TORCH_FORCE_NO_WEIGHTS_ONLY_LOAD=1` if it is not already set.
5. Loads a custom YOLOv5 model:
   - From a local YOLOv5 repository when available.
   - Otherwise from `ultralytics/yolov5` through Torch Hub.
6. Selects `cuda:0` when CUDA is available; otherwise selects CPU.
7. Moves the model to that device.
8. Switches it to evaluation mode with `model.eval()`.
9. Sets its confidence threshold.
10. Returns the loaded model.

The crop model uses a confidence threshold of `0.25`.

Security note: serialized `.pt` checkpoints and trusted Torch Hub repositories
can execute Python during loading. Checkpoints must come from trusted sources.

### Stage 8: Crop inference runs

Module: `crop_detection/predictor.py`

Function: `run_inference(model, crop_input)`

The model is called with an inference size of 640:

```python
results = model(image, size=640)
```

YOLO output is read from:

```python
results.xyxy[0]
```

Each row contains approximately:

```text
x1, y1, x2, y2, confidence, class_id
```

The tensor is:

1. Detached from the autograd graph.
2. Moved to CPU.
3. Converted to a Python list.

Every row is normalized into a `Detection` dataclass containing:

- `class_name`.
- `confidence`.
- Bounding box `(x1, y1, x2, y2)`.

### Stage 9: Crop routing is decided

Module: `crop_detection/disease_logic.py`

Function: `select_crop(detections)`

This is not a general “Corn versus Grape” classifier.

The current crop logic is deliberately Corn-first:

1. Normalize class labels by:
   - Replacing underscores and hyphens with spaces.
   - Lowercasing.
   - Collapsing repeated whitespace.
2. Treat `corn` and `maize` as the canonical crop `Corn`.
3. Ignore every non-Corn label.
4. If one or more Corn detections exist:
   - Select the highest-confidence Corn detection.
   - Return `CropDecision("Corn", confidence, detection, False)`.
5. If no Corn detection exists:
   - Assume the crop is Grape.
   - Return confidence `0.0`.
   - Set `selected_detection=None`.
   - Set `was_assumed=True`.

This means “not Corn” currently means “assume Grape.” An unrelated leaf is not
explicitly rejected by crop routing.

### Stage 10: The crop-specific disease model is selected

Module: `crop_detection/predictor.py`

Function: `ModelManager.disease_model(crop_name)`

- `Corn` selects `models/corn_disease.pt`.
- Any other crop name selects `models/grape_disease.pt`.

Both disease models use a model-level confidence threshold of `0.10`.

### Stage 11: Disease inference runs on the original colour image

Module: `crop_detection/predictor.py`

The app intentionally sends the original colour image to the disease model:

```python
disease_detections = run_inference(
    manager.disease_model(crop.name),
    image,
)
```

Colour can be important for symptoms such as:

- Orange rust pustules.
- Gray or tan lesions.
- Black rot.
- Yellow oily spots.

The complete post-threshold detection list is preserved for:

- Confidence display.
- Inconclusiveness checks.
- Groq context.

### Stage 12: Disease-selection rules are applied

Module: `crop_detection/disease_logic.py`

Function: `select_disease(crop_name, detections)`

First, labels are normalized through crop-specific alias dictionaries.

Corn aliases include:

- `healthy`.
- `gray leaf`, `gray leaf spot`, and spelling variants.
- `blight`.
- `rust`.

Grape aliases include:

- Healthy variants.
- Black rot variants.
- Blight variants.

#### Corn rule

1. Remove unsupported labels.
2. If no valid detections remain, return:

   ```text
   Healthy, confidence 0.0, fallback=True
   ```

3. Otherwise select the disease class whose best detection has the highest
   confidence.
4. Preserve all boxes belonging to that selected class.

#### Grape rule

1. Remove unsupported labels.
2. If no valid detections remain, return healthy fallback.
3. Find the highest-confidence valid detection.
4. If its confidence is below `0.40`, return:

   ```text
   Healthy Grape Vine, confidence 0.0, fallback=True
   ```

5. Otherwise return the selected disease and all boxes of that class.

There are therefore multiple thresholds:

| Threshold | Location | Purpose |
|---|---|---|
| `0.25` | Predictor | Crop model's minimum output confidence |
| `0.10` | Predictor | Disease models' minimum output confidence |
| `0.40` | Disease logic | Extra acceptance threshold for Grape disease |
| `0.50` and `0.15 gap` | Handlers | Flag an uncertain/inconclusive result |
| `0.15` | Handlers | Decide which scores to include in Groq context |
| `0.05` | App UI | Decide which scores to display in the result panel |

These thresholds serve different purposes and should not be described as one
single confidence threshold.

### Stage 13: The image is annotated

Module: `crop_detection/predictor.py`

Function: `_draw_detection(image, detection, label, color)`

The original colour image is copied. The copy is annotated:

- Crop bounding box: green.
- Disease bounding boxes: red.

The line width scales with the image dimensions. A filled label background is
drawn above each box, followed by white label text and confidence.

If Grape was assumed, there is no crop box because no crop detection was
selected.

If a healthy fallback was used, there may be no disease box.

### Stage 14: Annotated output is saved

Module: `crop_detection/predictor.py`

The `outputs/` folder is created if necessary.

The filename contains:

- A UTC timestamp.
- Eight hexadecimal characters from a UUID.

Example:

```text
outputs/analysis_20260617T062823Z_b4d5b225.jpg
```

The image is saved as JPEG with quality 92.

### Stage 15: `AnalysisResult` is returned

Module: `crop_detection/predictor.py`

`analyze_image()` packages all useful output into `AnalysisResult`:

- Crop name and confidence.
- Whether the crop was assumed.
- Disease name and confidence.
- Whether healthy was a fallback.
- Static recommendation, when one exists.
- Annotated Pillow image.
- Saved output path.
- All raw post-threshold disease detections.

The static `recommendation` field comes from
`crop_detection.solutions.get_recommendation()`. The current Streamlit result
panel does not directly render this field; treatment text primarily comes
through the medication database and Groq flow.

### Stage 16: Error handling returns to the UI

Module: `app.py`

The upload branch handles:

- `FileNotFoundError`: missing checkpoint.
- `ModelLoadError`: PyTorch/YOLO loading failure.
- Other exceptions: full traceback logged, generic message shown.

`st.stop()` halts only the current Streamlit script execution.

### Stage 17: Analysis enters the chatbot pipeline

Module: `app.py`

Function: `_run_analysis_and_stream(...)`

The function:

1. Sets `groq_thinking=True`.
2. Calls `handlers.handle_image_analysis()`.
3. Shows a warning when the result is unreliable.
4. Displays any generated medicine table.
5. Streams a crop-condition summary.
6. Saves the summary into in-memory chat history.
7. Resets `groq_thinking` in a `finally` block.
8. Reruns the Streamlit page.

### Stage 18: Reliability is evaluated

Module: `chatbot/handlers.py`

Function: `is_inconclusive(all_detections)`

The code filters detections above `0.10`, sorts them, and flags the result when:

- There are no detections, or
- The top confidence is below `0.50` and:
  - There is no second detection, or
  - The top-two confidence gap is below `0.15`.

This flag now produces a warning. It does not block treatment generation.

### Stage 19: Medication data is loaded

Module: `chatbot/handlers.py`

Functions:

- `_canonical_disease_key()`.
- `_load_medication_block()`.

The displayed disease name is converted back to the key used in
`data/medications.json`.

Examples:

```text
Gray Leaf Spot → gray_leaf
Healthy → healthy
Black Rot Grape Vine → Black Rot Grape Vine
```

The JSON file is opened and the matching disease entry is converted into a
plain-text block containing:

- Disease description.
- Cultural controls.
- Approved medicines.
- Active ingredients.
- Chemical classes.
- Application methods.
- Dosages.
- Water volumes.
- Timing.
- Reapplication intervals.
- Pre-harvest intervals.
- Maximum applications.
- Severity thresholds.
- Notes and research-source labels.

If the file is unavailable, malformed, or lacks an entry, a fixed
“no approved treatment data” message is returned.

### Stage 20: Conversation context is constructed

Module: `chatbot/handlers.py`

Function: `_handle_analysis_common(...)`

The handler:

1. Stores the `AnalysisResult` on the in-memory session.
2. Adds notes for assumed Grape, healthy fallback, or low confidence.
3. Formats disease scores above 15%.
4. Fills `ANALYSIS_USER_MESSAGE_TEMPLATE`.
5. Appends that assembled message to chat history with:
   - LLM role `user`, so Groq sees it as input.
   - UI `display_role="assistant"`, because the farmer did not type it.
6. Updates and persists the session's crop and disease.
7. Changes the mode to `ACTIVE_TREATMENT`.

### Stage 21: Long chat history may be summarized

Module: `chatbot/summarizer.py`

Before messages are sent to Groq, `messages_for_groq()` calls
`maybe_summarize()`.

Normally nothing happens because the history is below 91,750 characters.

If the threshold is crossed:

1. The first analysis message is kept as an anchor.
2. The eight newest messages are kept verbatim.
3. Older middle messages are summarized through Groq.
4. Those old messages are replaced by one system summary.
5. The summary is stored in `session.chat_summary`.
6. The session is saved to SQLite.

### Stage 22: Phase 1 Groq call creates structured medicines

Modules:

- `chatbot/handlers.py`.
- `chatbot/groq_client.py`.
- `chatbot/prompts.py`.

`groq_client.complete()`:

1. Creates a Groq client using `GROQ_API_KEY`.
2. Prepends `MEDICINE_JSON_SYSTEM_PROMPT` as a system message.
3. Makes a blocking chat-completion request.
4. Uses low temperature for predictable structured output.
5. Returns the complete response string.

The prompt requires JSON shaped like:

```json
{
  "medicines": [
    {
      "name": "...",
      "dosage": "...",
      "method": "Foliar Spray",
      "duration_weeks": 4,
      "week_start": 1,
      "reapplication_days": 14,
      "notes": "..."
    }
  ]
}
```

### Stage 23: Generated medicines are validated and saved

Module: `chatbot/handlers.py`

Function: `_parse_and_save_medicines(json_raw, session_id)`

The function:

1. Parses JSON.
2. Reads the `medicines` array.
3. Ignores entries without a name.
4. Restricts methods to:
   - Foliar Spray.
   - Soil Drench.
   - Seed Treatment.
   - Other.
5. Creates a `MedicineEntry` for each valid item.
6. Marks its source ID as `"auto_llm"`.
7. Uses today's date.
8. Assigns default severity 3.
9. Saves each entry through SQLite.
10. Builds a Markdown table for the chat.

Any parse failure produces no automatic entries rather than crashing the entire
analysis flow.

### Stage 24: Phase 2 Groq call streams the condition summary

Modules:

- `chatbot/handlers.py`.
- `chatbot/groq_client.py`.
- `chatbot/prompts.py`.

The second call uses `CROP_CONDITION_SUMMARY_SYSTEM_PROMPT`.

It asks for:

- A plain-language condition summary.
- Effects of the disease.
- Immediate non-chemical actions.
- Signs of improvement.
- A low-confidence reminder when needed.
- A pesticide disclaimer.

It explicitly tells Groq not to repeat the medicine table.

`groq_client.stream()` yields text chunks. `st.write_stream()` displays them as
they arrive.

### Stage 25: Final UI after rerun

Module: `app.py`

On the next rerun:

- `session.analysis_result` causes the persistent result expander to appear.
- Metrics show crop, disease, and confidence.
- The annotated image is shown.
- The user can download a JPEG copy.
- Chat history displays the treatment table and summary.
- `session.disease_name` causes the medicine tracker to appear.
- Mode `ACTIVE_TREATMENT` enables follow-up chat.

---

## 6. Complete image journey: live camera

The captured-frame path eventually uses the same full `analyze_image()` pipeline
as upload, but the preview has an additional real-time stage.

### Live preview modules

- `app.py`.
- `streamlit-webrtc`.
- PyAV (`av`).
- NumPy.
- Pillow.
- Crop portions of `crop_detection/`.

### Frame-by-frame flow

1. Clicking **Live Feed** sets `AWAITING_CAPTURE`.
2. `webrtc_streamer()` requests browser camera access.
3. Audio is disabled.
4. `streamlit-webrtc` passes each frame to `VideoProcessor.recv()`.
5. The PyAV frame is converted to a NumPy RGB array.
6. The array is converted into a Pillow image.
7. A clean copy is stored as `latest_frame`.
8. Every fifth frame:
   - A grayscale RGB copy is created.
   - Only the crop model runs.
   - `select_crop()` looks for Corn.
   - A green crop box is retained when available.
9. Frames between inference runs reuse the latest detection box.
10. Pillow draws the green box or “Searching for leaf...”.
11. The annotated image is converted back:

    ```text
    Pillow → NumPy → PyAV VideoFrame
    ```

12. The frame is returned to the WebRTC stream.

Running detection every fifth frame reduces compute and preview lag.

### Capturing and analysing

1. The main Streamlit thread copies the processor's latest clean frame into
   `st.session_state.latest_frame`.
2. Clicking **Capture Frame** copies it into `captured_frame`.
3. The captured image is displayed.
4. Clicking **Analyse Captured Frame** sends that image through the same
   `analyze_image()` function used for uploads.
5. After inference, `captured_frame` is cleared.
6. `_run_analysis_and_stream()` starts the same medication and Groq pipeline.

The camera path allows an optional note. The current upload path passes an empty
note to the handler.

---

## 7. Text-only journey when no image is available

This path does not run YOLO.

### Entry

1. User clicks **Describe Leaf**.
2. `app.py` appends an opening assistant message.
3. Mode changes to `CLARIFYING`.

### Each clarification turn

Modules:

- `app.py`.
- `chatbot/handlers.py`.
- `chatbot/clarification.py`.
- `chatbot/groq_client.py`.
- `chatbot/prompts.py`.

1. `app.py` receives `st.chat_input()`.
2. `handlers.handle_text_message()` sees mode `CLARIFYING`.
3. The user message is appended to chat history.
4. `clarification.process_turn()` calls Groq with
   `CLARIFICATION_SYSTEM_PROMPT`.
5. The prompt asks for one question at a time and requires JSON.
6. The required information is:
   - Crop type.
   - Affected plant part.
   - Symptom appearance.
   - Duration.
   - Approximate percentage affected.

### JSON parsing

`_parse_response()`:

1. Removes optional Markdown code fences.
2. Attempts normal `json.loads()`.
3. If parsing fails, searches for the first simple `{...}` block.
4. Validates that the result is a dictionary.
5. Returns either:
   - An unresolved result with another question.
   - A resolved result with crop and symptom summary.
   - A failure result with no question.

After two consecutive parse failures, `process_turn()` stops calling Groq and
returns a canned fallback question.

### Resolution

When enough information exists:

1. `handlers.py` tries to infer a medication-database disease key from symptom
   keywords.
2. It builds `TEXT_PATH_USER_MESSAGE_TEMPLATE`.
3. It marks the disease as `"Text-described (unconfirmed)"`.
4. Mode changes to `ACTIVE_TREATMENT`.
5. Groq streams a treatment response using `TREATMENT_SYSTEM_PROMPT`.

Important limitation: `_canonical_disease_from_symptoms()` is a small keyword
matcher, not a trained diagnostic classifier. It recognizes rust, gray/grey
leaf, blight, black rot, and grape blight patterns.

---

## 8. Module-by-module reference

# `app.py`

## Responsibility

The main Streamlit entry point and UI controller.

It owns:

- Upload validation.
- Page configuration and CSS.
- Sidebar session controls.
- State-based page rendering.
- Camera preview processing.
- Calling the detection and chatbot layers.
- Displaying and downloading results.
- Direct-Python launch support.

It does not implement the actual crop/disease decision rules or SQL queries.

## Constants

### `PROJECT_ROOT`

Absolute directory containing `app.py`. Used to locate models and outputs.

### `ALLOWED_EXTENSIONS`

Set of accepted upload suffixes.

### `MAX_UPLOAD_BYTES`

Upload limit of 15 MiB.

### `LOGGER`

Module logger used for unexpected inference and camera errors.

### `_CUSTOM_CSS`

Hard-coded CSS for option buttons, result-banner styles, and session cards.

The `.session-card` style is used. The `.detection-banner` styles are currently
defined but not used by the result renderer.

## Functions

### `load_uploaded_image(uploaded_file) -> Image.Image`

Validates extension, emptiness, byte size, image readability, EXIF orientation,
RGB mode, and minimum dimensions.

### `_stream_to_str(raw) -> str`

Normalizes `st.write_stream()` output:

- List of chunks → joined string.
- String → same string.
- `None`/falsey value → empty string.

### `_is_result_unreliable(result) -> bool`

Delegates reliability evaluation to `chatbot.handlers.is_inconclusive()`.

### `_render_detection_section(st, result, key_suffix, expanded=True)`

Renders:

- Low-confidence warning.
- Crop/disease metrics.
- Assumption/fallback captions.
- Visible class scores.
- Annotated image.
- Download button.

`key_suffix` prevents widget-key collisions.

### `_run_analysis_and_stream(...)`

Shared post-inference UI flow:

- Marks Groq busy.
- Runs handler's two-phase analysis.
- Displays generated medicine table.
- Streams summary.
- Appends summary.
- Handles runtime errors.
- Reruns the app.

### `streamlit_main()`

Builds the complete interface. It contains:

- Imports that are delayed until Streamlit execution.
- Page configuration.
- Session initialization.
- Cached model-manager factory.
- Sidebar.
- Chat-history rendering.
- Seven state-machine branches.
- Live `VideoProcessor` class.

### Nested `get_model_manager()`

Creates a `ModelManager` from the project root and is cached as a Streamlit
resource.

### Nested `VideoProcessor`

Receives WebRTC frames, runs crop preview inference every fifth frame, draws
preview annotations, and retains the latest clean frame.

### `_is_streamlit_runtime() -> bool`

Checks whether the file is already executing inside Streamlit.

### `launch()`

Either calls `streamlit_main()` or starts a Streamlit subprocess.

## State-machine modes

| Mode | UI rendered | Main exit/transition |
|---|---|---|
| `ONBOARDING` | Five navigation options | User selects a workflow |
| `AWAITING_UPLOAD` | File uploader and analysis button | Analysis or Back |
| `AWAITING_CAPTURE` | WebRTC camera and captured frame | Analysis or Back |
| `CLARIFYING` | Chat input for symptoms | Resolves to treatment |
| `ACTIVE_TREATMENT` | Follow-up chat and tracker | Start Over or continue |
| `PAST_SESSIONS` | Session browser | Switch, delete, or Back |
| `MEDICINE_TABLE` | Focused tracker panel | Back |

---

# `crop_detection/__init__.py`

This file is empty. Its presence marks `crop_detection` as a Python package and
allows imports such as:

```python
from crop_detection.predictor import analyze_image
```

---

# `crop_detection/disease_logic.py`

## Responsibility

Pure deterministic decision logic. It does not import Streamlit, PyTorch, Groq,
or SQLite.

This separation makes the routing rules easy to unit test without loading
models.

## Constant

### `GRAPE_CONF_THRESHOLD = 0.40`

Extra acceptance threshold for Grape disease results.

## Dataclasses

### `Detection`

Normalized result from a YOLO output row:

- `class_name`.
- `confidence`.
- `box`.

It is frozen, so its fields cannot normally be reassigned after creation.

### `CropDecision`

Final crop-routing result:

- Canonical crop name.
- Confidence.
- Selected crop detection or `None`.
- Whether the crop was assumed.

### `DiseaseDecision`

Final disease-selection result:

- Canonical disease name.
- Confidence.
- All selected boxes of the winning class.
- Whether a healthy fallback was used.

## Label dictionaries

### `CROP_ALIASES`

Normalizes Corn/Maize labels to `Corn`.

### `CORN_DISEASE_ALIASES`

Normalizes model label variants to canonical internal Corn disease keys.

### `GRAPE_DISEASE_ALIASES`

Normalizes short and long Grape disease labels.

### `DISPLAY_DISEASE_NAMES`

Converts internal canonical names into user-facing text.

### `HEALTHY_DISEASES`

Set used by `is_healthy()`.

## Functions

### `_label_key(label) -> str`

Normalizes separators, case, and whitespace.

### `select_crop(detections) -> CropDecision`

Selects the highest-confidence Corn detection or assumes Grape.

### `select_disease(crop_name, detections) -> DiseaseDecision`

Applies crop-specific aliases, best-class selection, and healthy fallbacks.

### `display_disease_name(canonical_name) -> str`

Returns a user-facing label, falling back to the original string when no mapping
exists.

### `is_healthy(canonical_name) -> bool`

Checks membership in `HEALTHY_DISEASES`.

---

# `crop_detection/predictor.py`

## Responsibility

The core computer-vision execution layer:

- Locates checkpoints.
- Loads YOLOv5.
- Chooses CPU/GPU.
- Runs inference.
- Converts tensor output.
- Routes to the disease model.
- Draws annotations.
- Saves output images.
- Builds `AnalysisResult`.

## Constants

### `CROP_INFERENCE_THRESHOLD = 0.25`

Minimum crop-model output confidence.

### `DISEASE_INFERENCE_THRESHOLD = 0.10`

Minimum disease-model output confidence before application decision logic.

### `INFERENCE_IMAGE_SIZE = 640`

Image size passed to YOLOv5 inference.

## Classes

### `ModelLoadError`

Custom `RuntimeError` used to distinguish model initialization failures from a
missing file or ordinary application error.

### `AnalysisResult`

Immutable container for all analysis output.

### `ModelManager`

Holds model paths, output path, optional local YOLOv5 path, and an internal
model cache.

#### `ModelManager.__init__(...)`

Stores configuration and initializes `_models={}`.

#### `ModelManager.from_project_root(project_root)`

Constructs standard project paths.

#### `ModelManager.crop_model()`

Returns the cached/loaded crop model.

#### `ModelManager.disease_model(crop_name)`

Returns the Corn model for exactly `Corn`, otherwise the Grape model.

#### `ModelManager._get_or_load(key, path, confidence)`

Lazy-loads one model per key.

## Functions

### `_find_local_yolov5_repo(project_root)`

Searches configured and conventional local YOLOv5 directories.

### `load_yolov5_model(weights_path, confidence, yolov5_repo=None)`

Loads trusted custom weights through local Torch Hub or the official remote
YOLOv5 repository, configures device/evaluation/confidence, and returns the
model.

### `run_inference(model, image) -> list[Detection]`

Runs YOLO and converts tensor rows into plain dataclasses.

### `create_grayscale_copy(image) -> Image.Image`

Returns a three-channel grayscale copy while preserving the original.

### `analyze_image(image, manager) -> AnalysisResult`

Coordinates the full crop and disease pipeline.

### `_draw_detection(image, detection, label, color)`

Draws a bounding box and confidence label.

---

# `crop_detection/solutions.py`

## Responsibility

Provides short static integrated disease-management recommendations.

## `DISEASE_SOLUTIONS`

Dictionary keyed by canonical disease names. Healthy classes are intentionally
absent.

## `get_recommendation(disease_name) -> str | None`

Returns the mapped recommendation or `None`.

This is a deterministic fallback/reference source, separate from the richer
medication JSON and Groq response.

---

# `chatbot/__init__.py`

Empty package marker for `chatbot`.

---

# `chatbot/state.py`

## Responsibility

Defines Streamlit session-state keys and basic session operations.

Despite being in the chatbot package, this module is coupled to Streamlit
because its functions import `streamlit` internally.

## `ChatMode`

A `Literal` type describing the seven valid UI modes. It helps static type
checkers catch invalid mode strings but does not enforce values at runtime.

## Functions

### `init_session_state()`

Safely initializes all expected state keys.

On first use it:

1. Calls `persistence.load_sessions()`.
2. Converts the result to a dictionary keyed by session ID.
3. Marks sessions as loaded.

It also initializes:

- Active session ID.
- Chat mode.
- Latest/captured frames.
- A currently unused top-level `latest_detection` key.
- Groq busy flag.
- Medicine-panel visibility flag.

### `active_session() -> CropSession | None`

Looks up the active session ID in the in-memory session dictionary.

### `create_new_session(display_name) -> CropSession`

Creates a UUID session, puts it in Streamlit state, activates it, initializes
the database, and persists it.

### `append_message(session, role, content)`

Appends an in-memory chat-history dictionary.

### `set_chat_mode(mode)`

Writes the mode to Streamlit session state.

### `update_session_crop_disease(session, crop_name, disease_name)`

Mutates the session and persists its metadata.

---

# `chatbot/groq_client.py`

## Responsibility

Small wrapper around the Groq SDK. It deliberately contains no Streamlit UI.

## Constants

### `_DEFAULT_MODEL`

Default model used for normal completions and streams:

```text
llama-3.3-70b-versatile
```

### `_SUMMARIZE_MODEL`

Smaller model used for chat summarization:

```text
llama-3.1-8b-instant
```

## Functions

### `_client()`

Lazily imports `Groq`, validates `GROQ_API_KEY`, and returns a client.

### `complete(messages, system_prompt, model=...) -> str`

Blocking completion used when the entire result must be parsed before
continuing, such as medicine JSON or clarification JSON.

Configuration:

- Temperature 0.2.
- Maximum 1024 output tokens.

### `stream(messages, system_prompt, model=...) -> Iterator[str]`

Streaming completion used for visible conversational responses.

Configuration:

- Temperature 0.3.
- Maximum 2048 output tokens.
- `stream=True`.

It yields only non-empty text deltas.

### `summarize(messages_to_compress, model=...) -> str`

Returns early for an empty list. Otherwise converts messages into role-prefixed
text, asks the smaller model for a concise factual summary, and returns it.

---

# `chatbot/prompts.py`

## Responsibility

Central location for prompt text and canned messages. It contains no operational
logic.

## Constants

### `TREATMENT_SYSTEM_PROMPT`

Rules for initial and follow-up treatment chat:

- Do not invent diagnoses.
- Use only medication data supplied in context.
- Explain low confidence.
- Use plain language.
- Include a fixed pesticide disclaimer.

### `CLARIFICATION_SYSTEM_PROMPT`

Forces one question at a time and JSON-only output until five required symptom
details are collected.

### `SUMMARIZE_PROMPT_TEMPLATE`

Template for summary instructions. The current `groq_client.summarize()`
duplicates similar text inline instead of using this constant, so this template
is currently unused.

### `ANALYSIS_USER_MESSAGE_TEMPLATE`

Combines model detections, all visible class scores, medication data, and the
farmer's message.

### `TEXT_PATH_USER_MESSAGE_TEMPLATE`

Equivalent context template for the no-image clarification path.

### `INCONCLUSIVE_RESPONSE`

Canned response intended for an inconclusive result. The current code uses
`INCONCLUSIVE_WARNING` and continues analysis, so this older blocking response
is not used in the main flow.

### `NO_MEDICATION_DATA_RESPONSE`

Safe response when no approved data can be loaded.

### `MEDICINE_JSON_SYSTEM_PROMPT`

Requires a strict structured medicine plan and forbids medicines absent from
the approved data block.

### `CROP_CONDITION_SUMMARY_SYSTEM_PROMPT`

Requests a friendly non-chemical condition summary after the medicine table has
already been generated.

### `INCONCLUSIVE_WARNING`

Visible warning for tentative results. It does not stop analysis.

---

# `chatbot/clarification.py`

## Responsibility

Handles the no-image question loop and defensive parsing of model-generated
JSON.

## Constants

### `_MAX_PARSE_RETRIES = 2`

After two consecutive parse failures, stop making clarification API calls and
use a fixed question.

### `_FALLBACK_QUESTION`

Asks for affected part, appearance, and duration.

## Dataclass

### `ClarificationResult`

Represents either:

- Unresolved: `question` is present.
- Resolved: `crop_type` and `symptoms_summary` are present.
- Parsing failure: all optional values are absent.

## Functions

### `process_turn(messages, consecutive_failures=0)`

Returns the fallback question after too many failures; otherwise calls Groq and
parses its response.

Note: this function explicitly requests model `"llama3-70b-8192"` rather than
using `groq_client`'s default model.

### `_parse_response(raw)`

Parses strict JSON, attempts simple embedded-object recovery, validates required
fields, and creates a `ClarificationResult`.

### `_strip_fences(text)`

Removes leading/trailing Markdown code fences, including ```json.

### `_failure_result()`

Returns an unresolved result with no question so the caller can count a parse
failure.

---

# `chatbot/summarizer.py`

## Responsibility

Prevents a long conversation from exceeding the LLM context window while
retaining the original detection evidence and recent conversation.

## Constants

### `SUMMARIZE_THRESHOLD = 91_750`

Approximate character threshold for compression.

### `MESSAGES_TO_KEEP = 8`

Number of newest messages retained verbatim.

## Functions

### `total_chars(messages) -> int`

Adds the lengths of all message contents.

### `maybe_summarize(session) -> bool`

Compresses old middle messages, mutates the session, persists the summary, and
reports whether compression occurred.

### `messages_for_groq(session) -> list[dict]`

Triggers summarization if needed, then strips UI-only fields such as
`display_role`, returning only `role` and `content`.

---

# `chatbot/handlers.py`

## Responsibility

The main business-orchestration module between detection, medication data,
session state, Groq, and persistence.

## Constants

- `_MEDICATIONS_PATH`: absolute path to the JSON database.
- `_INCONCLUSIVENESS_TOP_CONF_THRESHOLD = 0.50`.
- `_INCONCLUSIVENESS_GAP_THRESHOLD = 0.15`.
- `_DETECTION_DISPLAY_THRESHOLD = 0.15`.
- `_VALID_METHODS`: accepted tracker application methods.

## `AnalysisResponse`

Named tuple containing:

- Reliability flag.
- Automatically saved medicine entries.
- Markdown medicine table.
- Lazy summary iterator.

## Functions

### `is_inconclusive(all_detections) -> bool`

Applies the no-detection and low-top/close-gap uncertainty rules.

### `_load_medication_block(crop_name, disease_canonical) -> str`

Loads and formats the relevant JSON disease record.

### `_format_all_detections(all_detections) -> str`

Formats detections above 15% for LLM context.

### `_parse_and_save_medicines(json_raw, session_id)`

Defensively parses phase-1 JSON, validates method values, creates
`MedicineEntry` objects, saves them, and creates a Markdown table.

Its nested `_esc(s)` helper escapes pipe characters as `\|` so medicine text
cannot accidentally split the generated Markdown table into extra columns.

### `_handle_analysis_common(result, user_message, session)`

Shared upload/camera business flow:

- Reliability.
- Session result.
- Medication lookup.
- LLM context.
- Session persistence.
- Mode transition.
- Phase-1 medicine call.
- Phase-2 summary iterator.

### `handle_image_analysis(...)`

Public upload wrapper around `_handle_analysis_common()`.

### `handle_camera_analysis(...)`

Public camera wrapper around `_handle_analysis_common()`.

The current `app.py` calls `handle_image_analysis()` for both upload and camera
through `_run_analysis_and_stream()`. Because both wrappers currently do the
same thing, behavior is unchanged, but `handle_camera_analysis()` is not used.

### `handle_text_message(user_text, session)`

Routes a message according to current mode:

- `ACTIVE_TREATMENT` → follow-up stream.
- Otherwise → clarification loop.

When clarification resolves, it constructs text-path treatment context and
starts treatment mode.

### `_handle_followup(user_text, session)`

Appends the user message, prepares summarized context if necessary, and returns
a treatment stream.

### `_canonical_disease_key(crop_name, display_name)`

Maps displayed image-result names back to medication JSON keys.

### `_canonical_disease_from_symptoms(symptoms_summary)`

Uses keyword matching to choose a medication key for text-only symptoms.

---

# `tracking/__init__.py`

Empty package marker for `tracking`.

---

# `tracking/models.py`

## Responsibility

Defines shared Python data structures without Streamlit or database logic.

## `MedicineEntry`

A dataclass representing one treatment-log row:

| Field | Meaning |
|---|---|
| `entry_id` | UUID primary key |
| `session_id` | Parent session |
| `week_number` | Treatment week |
| `date_applied` | Application date |
| `medicine_id` | JSON ID, `"manual"`, or `"auto_llm"` |
| `medicine_name` | Human-readable treatment |
| `dosage_applied` | Actual dose text |
| `application_method` | Spray/drench/etc. |
| `symptom_severity` | Integer from 1 to 5 |
| `notes` | Farmer notes |
| `is_improving` | `True`, `False`, or `None` |

## `CropSession`

Represents one crop/field investigation:

| Field | Stored where |
|---|---|
| `session_id` | SQLite and memory |
| `display_name` | SQLite and memory |
| `crop_name` | SQLite and memory |
| `disease_name` | SQLite and memory |
| `created_at` | SQLite and memory |
| `chat_history` | Memory only |
| `chat_summary` | SQLite and memory |
| `analysis_result` | Memory only |
| `clarification_state` | Memory only |
| `medicine_entries` | Loaded from SQLite, though tracker also reloads directly |

`analysis_result` uses `Any` to avoid importing the predictor and creating a
circular dependency.

---

# `tracking/persistence.py`

## Responsibility

SQLite data-access layer for sessions and medicine records.

The default database is:

```text
tracking.db
```

in the project root.

## Module state

### `_DB_PATH`

Optional override used by tests.

## Functions

### `_db_path() -> Path`

Returns the test override or default database path.

### `set_db_path(path)`

Changes the database path. Tests use a temporary file.

The annotation says `Path`, although tests pass `None` to restore the default;
runtime logic accepts that value.

### `_connect() -> sqlite3.Connection`

Creates a connection, enables foreign keys, and configures rows for named-column
access.

### `init_db()`

Creates `crop_sessions` and `medicine_log` if absent.

### `save_session(session)`

Uses an SQLite upsert:

- Insert new session.
- On duplicate ID, update editable metadata and summary.

### `load_sessions()`

Loads sessions newest first, loads each session's medicine entries, and creates
`CropSession` objects.

Chat history is restored as an empty list because complete chat history is not
persisted.

### `delete_session(session_id)`

Deletes the session. Foreign-key cascade deletes its medicine rows.

### `save_medicine_entry(entry)`

Converts three-state Python `is_improving` into:

- `NULL`.
- `0`.
- `1`.

Then inserts or updates the medicine row.

### `load_medicine_entries(session_id)`

Loads ordered rows, converts ISO strings back to dates, converts improvement
integers to booleans, and creates dataclasses.

### `delete_medicine_entry(entry_id)`

Deletes one treatment row.

### `new_entry_id() -> str`

Returns a UUID. Current tracker code creates UUIDs directly, so this helper is
currently unused.

## Database schema

```text
crop_sessions
├── session_id       TEXT PRIMARY KEY
├── display_name     TEXT NOT NULL
├── crop_name        TEXT
├── disease_name     TEXT
├── created_at       TEXT NOT NULL
└── chat_summary     TEXT

medicine_log
├── entry_id             TEXT PRIMARY KEY
├── session_id           TEXT FOREIGN KEY
├── week_number          INTEGER
├── date_applied         TEXT
├── medicine_id          TEXT
├── medicine_name        TEXT
├── dosage_applied       TEXT
├── application_method   TEXT
├── symptom_severity     INTEGER 1..5
├── notes                TEXT
└── is_improving         INTEGER/NULL
```

---

# `tracking/tracker_ui.py`

## Responsibility

Renders the medicine log, editing controls, delete controls, and severity chart.

This module uses Pandas to exchange table-shaped data with Streamlit.

## Functions

### `render_tracking_panel(session_id, disease_name)`

Loads current entries, renders the add form, renders the editable table when
data exists, and renders the progress chart.

The `disease_name` parameter is currently accepted but not used.

### `_render_add_entry_form(session_id, disease_name, existing_entries)`

Calculates the next week, accepts treatment details, validates a non-empty
medicine name, creates a manual `MedicineEntry`, saves it, and reruns.

### `_render_table(session_id, entries)`

Converts dataclasses to a DataFrame, displays `st.data_editor`, saves edits, and
allows selected rows to be deleted.

### `_apply_edits(original_df, edited_df, entries)`

Compares each original and edited row, skips unchanged rows, parses edited
dates, rebuilds changed dataclasses, and upserts them.

Invalid edited date strings silently retain the previous date.

### `_render_sparkline(entries)`

Despite its name, it renders a bar chart rather than a sparkline.

For each week it keeps the maximum recorded severity. At least two weeks are
required before the chart is displayed.

---

## 9. Medication database

File: `data/medications.json`

The structure is:

```text
root
├── version
├── note
└── diseases
    ├── corn
    │   ├── rust
    │   ├── gray_leaf
    │   └── blight
    └── grape
        ├── Black Rot Grape Vine
        └── Blight Grape Vine
```

Every disease can contain:

- `display_name`.
- `description`.
- `cultural_controls`.
- `medications`.

Every medication can contain:

- Internal ID.
- Trade name.
- Active ingredient.
- Chemical class.
- Application method.
- Dosage rate.
- Water volume.
- Timing.
- Reapplication interval.
- Pre-harvest interval.
- Maximum seasonal applications.
- Notes.
- Research-source label.
- Severity threshold.

The file is not queried like a database. `handlers.py` loads it with Python's
`json` module and converts one matching record into text for Groq.

Healthy results have no medication entries and therefore receive the safe
no-approved-data response.

The JSON note correctly warns that pesticide labels vary by jurisdiction and
change over time. This data must be independently re-verified before real-world
use.

---

## 10. Test suite

The project uses `pytest`. Most tests avoid expensive models and external API
calls through fakes, monkeypatching, and temporary databases.

# `tests/test_disease_logic.py`

Verifies:

- Corn wins whenever a Corn detection exists.
- Grape is assumed when Corn is absent.
- Non-Corn crop labels are ignored.
- Highest-confidence Corn disease wins.
- Empty Corn output falls back to healthy.
- Grape below 40% falls back to healthy.
- Short Grape checkpoint labels are normalized.

# `tests/test_predictor.py`

Verifies:

- Grayscale conversion does not mutate the original.
- Crop inference receives grayscale.
- Disease inference receives the original colour image.
- All disease detections are preserved in `AnalysisResult`.
- Empty detections produce an empty tuple and fallback.

These tests monkeypatch `run_inference()`, so they do not load real YOLO models.

# `tests/test_groq_client.py`

Verifies:

- Missing `GROQ_API_KEY` raises a clear error.
- A mocked completion returns content.
- Summarizing an empty list returns immediately.

No real Groq API call is made.

# `tests/test_clarification.py`

Verifies:

- Markdown fences are stripped.
- Plain JSON remains unchanged.
- Resolved JSON is parsed.
- Follow-up questions are parsed.
- Malformed JSON returns a failure result.
- Embedded JSON can be recovered.
- Missing resolved fields are rejected.

# `tests/test_summarizer.py`

Verifies:

- Character counting.
- No compression below threshold.
- Compression above threshold.
- First analysis message remains anchored.
- Eight recent messages remain.
- `messages_for_groq()` returns a normal list.

Groq and persistence are mocked.

# `tests/test_persistence.py`

Uses an automatically applied `tmp_path` fixture so production `tracking.db` is
never touched.

Verifies:

- Saving/loading sessions.
- Updating session names.
- Saving/loading medicine entries.
- Three-state improvement values.
- Cascade deletion.
- Session isolation.
- Persisted chat summary.

---

## 11. Dependencies and why they are used

File: `requirements.txt`

| Dependency | Role in this project | Common alternative |
|---|---|---|
| Streamlit | Python-first web UI | Gradio, Dash, FastAPI + React |
| Groq SDK | Hosted LLM completion/streaming | OpenAI, Anthropic, Gemini, Ollama |
| Pillow | Image opening, validation, conversion, drawing | OpenCV, scikit-image |
| PyTorch | YOLOv5 checkpoint execution | TensorFlow, ONNX Runtime |
| torchvision | PyTorch vision support/YOLO dependency | TensorFlow vision stack |
| NumPy | Pixel arrays and frame conversion | Fundamental dependency for most alternatives |
| OpenCV headless | YOLO/image runtime support without desktop GUI | Pillow, scikit-image |
| PyYAML | YOLO configuration parsing | JSON/TOML, depending on model stack |
| requests | HTTP support used by model/runtime tooling | httpx |
| tqdm | Progress bars used by training/runtime tooling | Rich progress |
| pandas | Editable medicine-table DataFrames | Polars, plain records |
| matplotlib | Training/evaluation visualization support | Plotly |
| seaborn | Statistical visualization support | Matplotlib/Plotly |
| scipy | Scientific operations used by ML stack | NumPy-specific implementations |
| psutil | System-resource inspection | Standard-library partial alternatives |
| thop | Neural-network FLOP profiling | fvcore |
| gitpython | Git operations used by ML tooling | subprocess + Git CLI |
| ultralytics | YOLO ecosystem support | Detectron2, MMDetection |
| streamlit-webrtc | Browser camera/WebRTC | Custom JavaScript/WebSocket frontend |
| av | FFmpeg-compatible video frames | OpenCV/FFmpeg wrappers |

Not every requirement is imported directly by application code. Several are
supporting dependencies expected by YOLOv5 or its tooling.

---

## 12. Why Streamlit instead of FastAPI plus React?

### Why Streamlit is reasonable here

- The application and ML models are Python-based.
- Uploads, images, chat, metrics, forms, tables, downloads, and charts are
  available without writing a separate frontend.
- Pillow and PyTorch objects can move directly through the application.
- It minimizes prototype-development time.
- One Python process is enough for the current single-user academic/demo scope.

### What FastAPI plus React would add

- Clean frontend/backend separation.
- More custom UI control.
- Explicit REST/SSE/WebSocket APIs.
- Better multi-user authentication patterns.
- Independent frontend and backend deployment.
- Easier support for mobile or third-party clients.
- Better scaling around GPU workers and background jobs.

### Why it would cost more

The project would need:

- API routes and request/response schemas.
- Multipart image endpoints.
- Streaming response handling.
- CORS configuration.
- React components and frontend state.
- Camera code in JavaScript.
- Authentication and per-user authorization.
- Separate deployment and observability for two applications.

### Practical migration trigger

Migrate when the project needs real authentication, concurrent public users,
mobile/API clients, dedicated inference servers, sophisticated frontend
interaction, or separate team ownership of frontend and backend.

The existing `docs/MULTI_USER_UPGRADE.md` sketches this migration, but one claim
in that document is broader than the current code: not all `chatbot/` and
`tracking/` modules are Streamlit-free. `chatbot/state.py`,
`chatbot/handlers.py`, and `tracking/tracker_ui.py` currently import Streamlit,
so a real FastAPI migration would require extracting or adapting those UI/state
dependencies.

---

## 13. What is persisted and what is lost

| Data | Location | Survives Streamlit rerun? | Survives server restart? |
|---|---|---:|---:|
| Loaded models | Cached resource/RAM | Yes | No |
| Active session ID | Streamlit state | Yes | No |
| Full chat history | `CropSession` in RAM | Yes | No |
| Last `AnalysisResult` | `CropSession` in RAM | Yes | No |
| Captured camera frame | Streamlit state/RAM | Yes | No |
| Session metadata | SQLite | Yes | Yes |
| Crop and disease names | SQLite | Yes | Yes |
| Chat summary | SQLite | Yes | Yes |
| Medicine entries | SQLite | Yes | Yes |
| Annotated JPEG | `outputs/` | Yes | Yes until deleted |

After a server restart, old sessions can reappear, but their full visible chat
history and in-memory annotated result do not reappear.

---

## 14. Important implementation details and limitations

### 1. “No Corn” means “assume Grape”

This is the largest model-routing assumption. The crop model is not a robust
open-world crop classifier.

### 2. Healthy can be a fallback

A healthy result with 0% confidence can mean “no qualifying disease detected,”
not “the model positively detected health.”

### 3. Model confidence is not guaranteed to be calibrated probability

A displayed value such as 82% is a model score. It should not automatically be
interpreted as an 82% scientifically calibrated probability.

### 4. Low confidence does not stop treatment generation

The system shows a warning and proceeds. Older documentation may describe a
blocking inconclusive response, but the current handlers use a warning flag.

### 5. LLM medicine output is constrained but still model-generated

The prompt says to use only approved data, and parsing restricts method values,
but the generated name/dosage text is not programmatically cross-checked
against each JSON medication record before saving.

### 6. Chat history is in memory

Only the rolling summary is stored in SQLite.

### 7. Current build is single-user

All sessions in `tracking.db` are visible to anyone using the same deployed
application. There is no authentication or ownership column.

### 8. Raw HTML includes session data

Past-session cards interpolate `display_name`, crop, and disease into HTML with
`unsafe_allow_html=True`. Production code should HTML-escape user-controlled
values.

### 9. Live-frame sharing can involve concurrent threads

WebRTC processing is asynchronous. Production-grade frame sharing should
consider synchronization around shared mutable values.

### 10. Start Over is not a complete session reset

The button clears:

- Chat history.
- Analysis result.
- Clarification state.

It does not clear or persistently reset `crop_name`, `disease_name`, or previous
medicine entries.

### 11. Some code is currently unused or legacy

- `app.py`: local `labels` list.
- CSS: `.detection-banner` rules.
- Session state: top-level `latest_detection`.
- Camera detection dictionary: `"status"`.
- `chatbot.prompts.SUMMARIZE_PROMPT_TEMPLATE`.
- `chatbot.prompts.INCONCLUSIVE_RESPONSE`.
- `chatbot.handlers.handle_camera_analysis()`.
- `tracking.persistence.new_entry_id()`.
- `tracking.tracker_ui`'s `disease_name` parameter.

Unused code is not necessarily harmful, but it can confuse maintenance and viva
explanations unless identified.

### 12. Documentation contains historical plans

The developer task files describe ownership and earlier expected behavior.
Where they disagree with runtime code, the Python source is the current source
of truth.

---

## 15. Error handling by layer

| Layer | Error handling |
|---|---|
| Upload | Friendly `ValueError` messages |
| Model path | `FileNotFoundError` with expected path |
| Model initialization | `ModelLoadError` |
| Inference | Wrapped `RuntimeError` |
| Unexpected UI inference | Logged traceback + generic Streamlit error |
| Medication JSON file | Safe no-data response |
| Groq SDK missing | Clear installation error |
| Groq API key missing | Clear environment-variable error |
| Clarification JSON malformed | Recovery attempt, failure count, fallback question |
| Medicine JSON malformed | Log warning, skip auto-entry creation |
| Edited medicine date invalid | Keep previous date |

---

## 16. High-value viva questions and answers

### What is the role of `app.py`?

It is the Streamlit presentation and orchestration layer. It gathers input,
calls detection/chatbot/tracking modules, and renders output.

### Is the project doing image classification or object detection?

Object detection. YOLO returns bounding boxes, class labels, and confidence
scores.

### Why are there three models?

One model routes the crop, and two specialized models detect diseases for Corn
and Grape.

### Why is the crop image converted to grayscale?

The crop detector is intentionally run on a grayscale RGB copy. Disease models
still use the original colour image because disease appearance often depends on
colour.

### Why convert grayscale back to RGB?

To preserve the three-channel input shape expected by the YOLO pipeline while
keeping all channels equal.

### Why cache models?

Streamlit reruns the script frequently. Loading large PyTorch models on every
rerun would be slow and waste memory.

### Why use a `ModelManager` as well as `st.cache_resource`?

They cache at different levels:

- Streamlit caches the manager across reruns.
- The manager lazily caches each individual model inside `_models`.

### What happens if Corn is not detected?

The business rule assumes Grape with 0% crop confidence.

### Why does Grape have an extra 40% threshold?

It is an application-level acceptance rule. A lower Grape score is treated as
insufficient evidence and falls back to healthy.

### Why preserve all disease detections?

The selected top class alone is insufficient for uncertainty analysis. The
handler needs competing scores to determine whether the result is ambiguous.

### Does Groq diagnose the image?

No. YOLO and deterministic routing produce the image result. Groq receives that
result and controlled medication context to generate explanations and treatment
text.

### Why make two Groq calls after image analysis?

The first call returns machine-readable medicine JSON for automatic table
entries. The second streams a human-readable condition summary without
duplicating the table.

### Why use blocking completion for JSON and streaming for chat?

JSON must be complete before it can be parsed safely. Human-readable chat
benefits from appearing incrementally.

### Why SQLite?

It is simple, local, requires no separate server, and is sufficient for the
single-user prototype. PostgreSQL would be more appropriate for concurrent
production users.

### What is an upsert?

Insert a row if its primary key is new; otherwise update the existing row.

### Why enable SQLite foreign keys?

So deleting a session can automatically cascade and delete its medicine
records.

### What does `is_improving=None` mean?

The farmer selected “Too early to tell.” SQLite stores it as `NULL`.

### How is a long chat handled?

The original analysis and eight newest messages are retained; older messages
are summarized and the summary is persisted.

### Why not save every chat message?

The current prototype only persists summaries and session metadata. Persisting
full conversations would require an additional message table and privacy/data
retention decisions.

### Why Streamlit rather than FastAPI and React?

Streamlit keeps this Python-first ML prototype in one codebase with minimal UI
boilerplate. FastAPI plus React becomes preferable when custom UI, auth,
multiple clients, concurrency, or independent deployments matter more.

### What would you improve first?

A strong answer:

1. Replace “not Corn means Grape” with a robust crop/unknown classifier.
2. Add authentication and user-scoped persistence.
3. Programmatically validate LLM medicine output against JSON IDs and fields.
4. Persist full analysis/chat data when required.
5. Calibrate confidence thresholds on a held-out validation set.
6. Add end-to-end tests and deployment monitoring.

---

## 17. One-minute project explanation

> The application is built in Streamlit and behaves as a state machine. A user
> creates a crop session and either uploads an image, uses a WebRTC camera, or
> describes symptoms. For an image, Pillow validates and normalizes it. The
> predictor creates a grayscale RGB copy for a Corn detector. If Corn is found,
> it runs the Corn disease model; otherwise the current business rule assumes
> Grape and runs the Grape disease model on the original colour image.
> Deterministic disease logic normalizes labels, selects the strongest valid
> disease, and applies healthy fallbacks. The predictor draws bounding boxes,
> saves a JPEG, and returns an `AnalysisResult`. The chatbot handler looks up
> matching approved treatment data from JSON, flags ambiguous detections, saves
> the diagnosis, then makes two Groq calls: structured medicine JSON for the
> tracker and a streamed plain-language condition summary. SQLite stores session
> metadata and treatment progress, while Streamlit session state holds the
> current chat and analysis result.

---

## 18. Function call cheat sheet

### Upload analysis

```text
app.streamlit_main
└── app.load_uploaded_image
    └── Pillow verification/conversion

app.streamlit_main
└── crop_detection.predictor.analyze_image
    ├── create_grayscale_copy
    ├── ModelManager.crop_model
    │   └── _get_or_load
    │       └── load_yolov5_model
    ├── run_inference (crop)
    ├── disease_logic.select_crop
    ├── ModelManager.disease_model
    │   └── _get_or_load
    │       └── load_yolov5_model
    ├── run_inference (disease)
    ├── disease_logic.select_disease
    ├── _draw_detection
    ├── solutions.get_recommendation
    └── AnalysisResult

app._run_analysis_and_stream
└── handlers.handle_image_analysis
    └── handlers._handle_analysis_common
        ├── is_inconclusive
        ├── _canonical_disease_key
        ├── _load_medication_block
        ├── _format_all_detections
        ├── state.update_session_crop_disease
        │   └── persistence.save_session
        ├── summarizer.messages_for_groq
        ├── groq_client.complete
        ├── _parse_and_save_medicines
        │   └── persistence.save_medicine_entry
        ├── summarizer.messages_for_groq
        └── groq_client.stream
```

### Follow-up chat

```text
app.streamlit_main
└── handlers.handle_text_message
    └── handlers._handle_followup
        ├── state.append_message
        ├── summarizer.messages_for_groq
        │   └── maybe_summarize
        └── groq_client.stream
```

### Manual medicine entry

```text
tracking.tracker_ui.render_tracking_panel
└── _render_add_entry_form
    └── persistence.save_medicine_entry
        └── SQLite medicine_log
```

### Session deletion

```text
app.streamlit_main
└── persistence.delete_session
    └── SQLite crop_sessions DELETE
        └── ON DELETE CASCADE → medicine_log
```

---

## 19. Final mental model

When explaining any part of the project, keep these boundaries clear:

```text
Streamlit asks for work.
Predictor runs the models.
Disease logic makes deterministic choices.
Handlers coordinate business flow.
Prompts constrain Groq.
Medication JSON supplies treatment facts.
Tracking models describe records.
Persistence stores records.
Tracker UI edits records.
Tests protect important assumptions.
```

That is the architecture of the project in one compact model.
