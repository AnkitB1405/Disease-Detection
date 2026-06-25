# Graph Report - Disease Detection  (2026-06-25)

## Corpus Check
- 31 files · ~612,217 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 607 nodes · 871 edges · 34 communities (31 shown, 3 thin omitted)
- Extraction: 99% EXTRACTED · 1% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.53)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `92f2daa0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]

## God Nodes (most connected - your core abstractions)
1. `5. Complete image journey: uploaded image` - 26 edges
2. `CropSession` - 23 edges
3. `16. High-value viva questions and answers` - 22 edges
4. `streamlit_main()` - 19 edges
5. `Detection` - 19 edges
6. `FeedbackManager` - 17 edges
7. `analyze_image()` - 16 edges
8. `MedicineEntry` - 16 edges
9. `_handle_analysis_common()` - 14 edges
10. `Crop Disease Detection Prototype` - 14 edges

## Surprising Connections (you probably didn't know these)
- `AnalysisResponse` --uses--> `Detection`  [INFERRED]
  chatbot/handlers.py → crop_detection/disease_logic.py
- `AnalysisResponse` --uses--> `MedicineEntry`  [INFERRED]
  chatbot/handlers.py → tracking/models.py
- `_render_feedback_section()` --calls--> `display_disease_name()`  [EXTRACTED]
  app.py → crop_detection/disease_logic.py
- `_run_analysis_and_stream()` --calls--> `append_message()`  [EXTRACTED]
  app.py → chatbot/state.py
- `streamlit_main()` --calls--> `append_message()`  [EXTRACTED]
  app.py → chatbot/state.py

## Import Cycles
- None detected.

## Communities (34 total, 3 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (38): AnalysisResponse, _canonical_disease_from_symptoms(), _canonical_disease_key(), _format_all_detections(), _handle_analysis_common(), handle_camera_analysis(), _handle_followup(), handle_image_analysis() (+30 more)

### Community 1 - "Community 1"
Cohesion: 0.05
Nodes (41): `AnalysisResponse`, `_canonical_disease_from_symptoms(symptoms_summary)`, `_canonical_disease_key(crop_name, display_name)`, `chatbot/handlers.py`, `chatbot/__init__.py`, `chatbot/summarizer.py`, Constants, Constants (+33 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (35): Connection, DataFrame, _make_entry(), _make_session(), Tests for tracking/persistence.py — uses tmp_path, no production DB touched., test_chat_summary_persisted(), test_delete_session_cascades_medicine_entries(), test_medicine_entry_is_improving_false() (+27 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (29): 10. Start Over is not a complete session reset, 11. Dependencies and why they are used, 11. Some code is currently unused or legacy, 12. Documentation contains historical plans, 12. Why Streamlit instead of FastAPI plus React?, 13. What is persisted and what is lost, 14. Important implementation details and limitations, 15. Error handling by layer (+21 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (28): 5. Complete image journey: uploaded image, Corn rule, Grape rule, Stage 10: The crop-specific disease model is selected, Stage 11: Disease inference runs on the original colour image, Stage 12: Disease-selection rules are applied, Stage 13: The image is annotated, Stage 14: Annotated output is saved (+20 more)

### Community 5 - "Community 5"
Cohesion: 0.12
Nodes (14): FeedbackManager, Live-learning feedback capture and immediate YOLOv5 fine-tuning.  This module is, Number of feedback entries recorded so far (append-only log)., True once after a hot-swap completes; resets the flag. UI-thread only., Persist one correction and return the new total feedback count.          Crop-la, Kick off a fine-tune of the affected model in the background.          ``target`, Background entry point — always releases the lock when finished., Back up the live weights, overwrite with the fresh best.pt, flag reload. (+6 more)

### Community 6 - "Community 6"
Cohesion: 0.13
Nodes (23): _is_streamlit_runtime(), launch(), load_uploaded_image(), _model_class_names(), Streamlit entry point for the Crop Disease Detection chatbot., Normalise st.write_stream output (list[Any] | str | None) to plain str., Collapsible detection panel: annotated image + full results.      Rendered from, Return a disease model's class names as an ordered list (handles dict or list). (+15 more)

### Community 7 - "Community 7"
Cohesion: 0.09
Nodes (22): 16. High-value viva questions and answers, Does Groq diagnose the image?, How is a long chat handled?, Is the project doing image classification or object detection?, What does `is_improving=None` mean?, What happens if Corn is not detected?, What is an upsert?, What is the role of `app.py`? (+14 more)

### Community 8 - "Community 8"
Cohesion: 0.09
Nodes (22): `AnalysisResult`, `analyze_image(image, manager) -> AnalysisResult`, Classes, Constants, `create_grayscale_copy(image) -> Image.Image`, `crop_detection/predictor.py`, `CROP_INFERENCE_THRESHOLD = 0.25`, `DISEASE_INFERENCE_THRESHOLD = 0.10` (+14 more)

### Community 9 - "Community 9"
Cohesion: 0.18
Nodes (18): ClarificationResult, _failure_result(), _parse_response(), process_turn(), JSON-structured clarification loop for the text-only input path.  Groq is instru, Remove markdown code fences Groq occasionally wraps JSON in., Run one clarification turn and return the result.      Parameters     ----------, _strip_fences() (+10 more)

### Community 10 - "Community 10"
Cohesion: 0.19
Nodes (17): CropDecision, DiseaseDecision, _label_key(), Pure decision logic for crop routing and disease fallbacks., Apply the crop-specific highest-confidence and fallback rules., Select Corn from the single-class detector; otherwise assume Grape., select_crop(), select_disease() (+9 more)

### Community 11 - "Community 11"
Cohesion: 0.10
Nodes (19): Clarification Loop (`chatbot/clarification.py`) — already written, Critical: Day 1 PR #2, Critical rules encoded in the prompts (non-negotiable):, Failure handling (already implemented):, Groq Client (`chatbot/groq_client.py`) — already written, Inconclusiveness Thresholds (`chatbot/handlers.py`) — review and tune, Interface Contract with Ankit, Medication Database (`data/medications.json`) — already seeded, needs completion (+11 more)

### Community 12 - "Community 12"
Cohesion: 0.10
Nodes (20): 1. System architecture, 2. Repository map, 3. Application startup, 4. The Streamlit execution model, 6. Complete image journey: live camera, 7. Text-only journey when no image is available, 8. Module-by-module reference, Capturing and analysing (+12 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (20): `ALLOWED_EXTENSIONS`, `app.py`, Constants, `_CUSTOM_CSS`, Functions, `_is_result_unreliable(result) -> bool`, `_is_streamlit_runtime() -> bool`, `launch()` (+12 more)

### Community 14 - "Community 14"
Cohesion: 0.10
Nodes (20): Constant, `CORN_DISEASE_ALIASES`, `CROP_ALIASES`, `crop_detection/disease_logic.py`, `CropDecision`, Dataclasses, `Detection`, `DiseaseDecision` (+12 more)

### Community 15 - "Community 15"
Cohesion: 0.12
Nodes (16): Ankit's Tasks — Developer B (State Machine, UI, app.py), Day 1 Prerequisites (before you write any code), Interface Contracts, Running the App During Development, Task 1 — Verify `chatbot/state.py` (already implemented, review and extend), Task 2 — Verify `chatbot/handlers.py` (already implemented, review and extend), Task 3 — `app.py` state machine (already implemented, test each mode), Task 4 — Sidebar session management (+8 more)

### Community 16 - "Community 16"
Cohesion: 0.12
Nodes (16): Files changed in Phase 1:, Multi-User Upgrade Guide, Option A — Streamlit Authenticator (simpler, stays on Streamlit), Option B — FastAPI + JWT (proper, required for React migration), Phase 1 — Session Isolation Without Authentication (Quick Win), Phase 2 — Real Authentication, Phase 3 — React + FastAPI Migration, Search Tags for Single-User Removal (+8 more)

### Community 17 - "Community 17"
Cohesion: 0.12
Nodes (17): `_connect() -> sqlite3.Connection`, Database schema, `_DB_PATH`, `_db_path() -> Path`, `delete_medicine_entry(entry_id)`, `delete_session(session_id)`, Functions, `init_db()` (+9 more)

### Community 18 - "Community 18"
Cohesion: 0.12
Nodes (16): Crop Disease Detection Prototype, Decision Logic, Error Handling, Expected Output, Features, Folder Structure, Installation, Linux or macOS (+8 more)

### Community 19 - "Community 19"
Cohesion: 0.21
Nodes (14): display_disease_name(), AnalysisResult, analyze_image(), create_grayscale_copy(), _draw_detection(), YOLOv5 model loading, inference, annotation, and result assembly., Run one model and convert its tensor output into plain detections., Return an RGB grayscale copy without modifying the original image. (+6 more)

### Community 20 - "Community 20"
Cohesion: 0.18
Nodes (9): _client(), complete(), Groq API wrapper — complete, stream, and summarize.  Reads GROQ_API_KEY from the, Blocking call — returns the full response string.      Used for structured JSON, Streaming call — yields text chunks.      Pass the returned iterator directly to, Summarize a slice of chat history into one compact paragraph.      Called by cha, stream(), summarize() (+1 more)

### Community 21 - "Community 21"
Cohesion: 0.14
Nodes (13): Critical: Day 1 PR, `CropSession` fields, Data Models (already written — review and confirm), Ishaan's Tasks — Developer C (Persistence, Medicine Tracking), Medicine ID and medications.json, Medicine Tracking UI (`tracking/tracker_ui.py`) — already written, `MedicineEntry` fields, SQLite Layer (`tracking/persistence.py`) — already written (+5 more)

### Community 22 - "Community 22"
Cohesion: 0.15
Nodes (13): `ANALYSIS_USER_MESSAGE_TEMPLATE`, `chatbot/prompts.py`, `CLARIFICATION_SYSTEM_PROMPT`, Constants, `CROP_CONDITION_SUMMARY_SYSTEM_PROMPT`, `INCONCLUSIVE_RESPONSE`, `INCONCLUSIVE_WARNING`, `MEDICINE_JSON_SYSTEM_PROMPT` (+5 more)

### Community 23 - "Community 23"
Cohesion: 0.17
Nodes (12): `chatbot/clarification.py`, `ClarificationResult`, Constants, Dataclass, `_failure_result()`, `_FALLBACK_QUESTION`, Functions, `_MAX_PARSE_RETRIES = 2` (+4 more)

### Community 24 - "Community 24"
Cohesion: 0.27
Nodes (8): Any, load_yolov5_model(), ModelLoadError, ModelManager, Load custom YOLOv5 weights from a local repository or Torch Hub., Raised when a YOLOv5 model cannot be initialized., Load each YOLOv5 model at most once and route by crop., RuntimeError

### Community 25 - "Community 25"
Cohesion: 0.20
Nodes (8): _load_dotenv(), Load KEY=VALUE pairs from a .env file into os.environ.      Zero-dependency, so, _find_local_yolov5_repo(), Path, isolated_db(), Point the persistence module at a temporary database for each test., Override default DB location (used in tests)., set_db_path()

### Community 26 - "Community 26"
Cohesion: 0.27
Nodes (7): Detection, One normalized YOLO detection., FakeManager, Focused tests for crop preprocessing and inference routing., test_all_disease_detections_empty_when_no_detections(), test_all_disease_detections_preserved(), test_crop_uses_grayscale_but_disease_uses_original()

### Community 27 - "Community 27"
Cohesion: 0.20
Nodes (10): 10. Test suite, 9. Medication database, `_apply_edits(original_df, edited_df, entries)`, Functions, `_render_add_entry_form(session_id, disease_name, existing_entries)`, `_render_sparkline(entries)`, `_render_table(session_id, entries)`, `render_tracking_panel(session_id, disease_name)` (+2 more)

### Community 28 - "Community 28"
Cohesion: 0.20
Nodes (10): `active_session() -> CropSession | None`, `append_message(session, role, content)`, `chatbot/state.py`, `ChatMode`, `create_new_session(display_name) -> CropSession`, Functions, `init_session_state()`, Responsibility (+2 more)

### Community 29 - "Community 29"
Cohesion: 0.20
Nodes (10): `chatbot/groq_client.py`, `_client()`, `complete(messages, system_prompt, model=...) -> str`, Constants, `_DEFAULT_MODEL`, Functions, Responsibility, `stream(messages, system_prompt, model=...) -> Iterator[str]` (+2 more)

### Community 30 - "Community 30"
Cohesion: 0.50
Nodes (4): _is_result_unreliable(), Mirror the handlers.is_inconclusive check without importing to avoid circular de, is_inconclusive(), Return True when the model cannot reliably identify a single disease.      Rules

## Knowledge Gaps
- **287 isolated node(s):** `Purpose of this guide`, `Separation of responsibilities`, `Runtime source versus artifacts`, `Startup using `streamlit run app.py``, `Startup using `python app.py`` (+282 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **3 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does ``tests/test_persistence.py`` connect `Community 3` to `Community 1`, `Community 7`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `Crop Disease Detection: Complete Codebase Guide` connect `Community 12` to `Community 1`, `Community 4`?**
  _High betweenness centrality (0.062) - this node is a cross-community bridge._
- **Why does `5. Complete image journey: uploaded image` connect `Community 4` to `Community 12`?**
  _High betweenness centrality (0.038) - this node is a cross-community bridge._
- **Are the 5 inferred relationships involving `Detection` (e.g. with `AnalysisResponse` and `AnalysisResult`) actually correct?**
  _`Detection` has 5 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Streamlit entry point for the Crop Disease Detection chatbot.`, `Load KEY=VALUE pairs from a .env file into os.environ.      Zero-dependency, so`, `Normalise st.write_stream output (list[Any] | str | None) to plain str.` to the rest of the system?**
  _362 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.09872241579558652 - nodes in this community are weakly interconnected._
- **Should `Community 1` be split into smaller, more focused modules?**
  _Cohesion score 0.047619047619047616 - nodes in this community are weakly interconnected._