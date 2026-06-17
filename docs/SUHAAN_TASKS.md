# Suhaan's Tasks — Developer A (ML Pipeline + Groq Layer)

## Your Ownership

| File | Status |
|------|--------|
| `crop_detection/predictor.py` | Yours (the `all_disease_detections` change is already done — review it) |
| `chatbot/groq_client.py` | Yours |
| `chatbot/prompts.py` | Yours — all prompt engineering lives here |
| `chatbot/clarification.py` | Yours |
| `chatbot/summarizer.py` | Yours |
| `data/medications.json` | Yours — populate with real research data |
| `tests/test_groq_client.py` | Yours |
| `tests/test_clarification.py` | Yours |
| `tests/test_summarizer.py` | Yours |

You do **not** edit `app.py`, `tracking/`, or `chatbot/state.py`. If Ankit needs a change to the Groq call signatures, coordinate before changing — he calls your functions.

---

## Critical: Day 1 PR #2

**Your first task is shipping the `all_disease_detections` field change in `predictor.py`.**

This has already been implemented. Verify it at `crop_detection/predictor.py`:
- `AnalysisResult` dataclass has the new field: `all_disease_detections: tuple[Detection, ...]`
- `analyze_image()` populates it with `tuple(disease_detections)` before passing to `select_disease()`
- Existing tests in `tests/test_predictor.py` still pass (the new field has a default-compatible position at the end)

Run to verify:
```bash
python -m pytest tests/test_predictor.py -v
```

---

## Interface Contract with Ankit

These are the exact signatures Ankit calls. Do not change them without coordinating:

```python
# chatbot/groq_client.py
from chatbot.groq_client import complete, stream, summarize

complete(
    messages: list[dict[str, str]],
    system_prompt: str,
    model: str = "llama3-70b-8192",
) -> str

stream(
    messages: list[dict[str, str]],
    system_prompt: str,
    model: str = "llama3-70b-8192",
) -> Iterator[str]

summarize(
    messages_to_compress: list[dict[str, str]],
    model: str = "llama3-8b-8192",
) -> str
```

---

## Groq Client (`chatbot/groq_client.py`) — already written

Review the implementation. Key points:
- `GROQ_API_KEY` must be set in the environment: `export GROQ_API_KEY=your_key`
- `complete()` is blocking — used for clarification JSON (small, fast response)
- `stream()` returns an iterator — Ankit passes it to `st.write_stream()` for treatment plans
- `summarize()` uses the smaller `llama3-8b-8192` model (faster, sufficient for summaries)
- `temperature=0.2` for `complete()` (structured output needs low randomness)
- `temperature=0.3` for `stream()` (treatment plans benefit from slightly higher variability)

To run with a real API key:
```bash
export GROQ_API_KEY=gsk_your_key_here
python -c "from chatbot.groq_client import complete; print(complete([{'role':'user','content':'hello'}], 'You are helpful.'))"
```

---

## Prompt Engineering (`chatbot/prompts.py`) — already written, tune as needed

All prompts are in `chatbot/prompts.py`. You tune these; Ankit never edits this file.

### Critical rules encoded in the prompts (non-negotiable):

1. **TREATMENT_SYSTEM_PROMPT**: instructs Groq to ONLY use medications from the data block provided in the user message. If no data block, it must say: "No approved treatment data is available for this result."
2. **CLARIFICATION_SYSTEM_PROMPT**: forces JSON-only output. The model must never write text outside the JSON object.
3. **INCONCLUSIVE_RESPONSE**: a canned string — no Groq call is made for inconclusive detections.

### Prompt tuning tips:
- If Groq adds markdown fences around the clarification JSON, the `_strip_fences()` function in `clarification.py` handles it. But check: some models reliably output clean JSON when you add "Respond with only the JSON object, no other text, no markdown." to the system prompt.
- If treatment plans are too long, add "Keep your response to 300 words or fewer."
- If Groq is inventing medications, strengthen the constraint: "The ONLY medications you may mention are those listed under 'APPROVED MEDICATION DATA'. Do not name any other product."

---

## Clarification Loop (`chatbot/clarification.py`) — already written

The loop collects 5 pieces of information before resolving:
1. Crop type
2. Which plant part is affected
3. Symptom description (colour, pattern, texture)
4. Duration
5. Percentage of crop affected

When all 5 are collected, Groq returns:
```json
{"has_enough_info": true, "crop_type": "...", "symptoms_summary": "..."}
```

Until then:
```json
{"has_enough_info": false, "question": "Single question here"}
```

### Failure handling (already implemented):
- `_strip_fences()` removes markdown code fences
- `json.JSONDecodeError` → tries to extract first `{...}` block with regex
- If both fail → `_failure_result()` — the caller tracks `consecutive_failures`
- After 2 consecutive failures → canned fallback question, no Groq call

---

## Summarizer (`chatbot/summarizer.py`) — already written

### Thresholds (tune these):
```python
SUMMARIZE_THRESHOLD = 91_750   # chars — 70% of llama3-70b's 32k-token window
MESSAGES_TO_KEEP = 8
```

During development, temporarily lower `SUMMARIZE_THRESHOLD` to trigger summarization quickly:
```python
summarizer.SUMMARIZE_THRESHOLD = 200  # triggers after ~2 messages for testing
```

### What is never summarized:
- `session.chat_history[0]` — the first message (YOLO analysis data). Always the anchor.

### What `maybe_summarize()` does:
1. Calculates total character length of `chat_history`
2. If below threshold → returns `False` immediately
3. Otherwise: compresses `history[1:-8]` → calls `groq_client.summarize()` → replaces with one system message → persists summary to SQLite via `persistence.save_session()`

---

## Medication Database (`data/medications.json`) — already seeded, needs completion

The file at `data/medications.json` has a full schema and entries for all 5 diseases. Verify the data is accurate against these sources:

- **Corn Rust**: [Crop Protection Network](https://cropprotectionnetwork.org/), [UMN Extension](https://extension.umn.edu/corn-pest-management)
- **Corn Gray Leaf Spot**: [UMN Extension — Gray Leaf Spot](https://extension.umn.edu/corn-pest-management)
- **Corn Northern Blight**: [UMN Extension — Northern Corn Leaf Blight](https://extension.umn.edu/corn-pest-management)
- **Grape Black Rot**: [Penn State Extension](https://extension.psu.edu/forage-and-food-crops/fruit/grapes)
- **Grape Downy Mildew/Blight**: [Penn State Extension](https://extension.psu.edu/forage-and-food-crops/fruit/grapes)

### Schema for each medication entry:
```json
{
  "id": "unique_id",
  "trade_name": "...",
  "active_ingredient": "...",
  "class": "...",
  "application_method": "foliar_spray | soil_drench | ...",
  "dosage_rate": "...",
  "water_volume": "...",
  "timing": "...",
  "reapplication_interval_days": 14,
  "preharvest_interval_days": 14,
  "max_applications_per_season": 3,
  "notes": "...",
  "research_source": "...",
  "severity_threshold": "..."
}
```

---

## Inconclusiveness Thresholds (`chatbot/handlers.py`) — review and tune

The thresholds are in `chatbot/handlers.py` (Ankit's file, but Suhaan tunes the values):

```python
_INCONCLUSIVENESS_TOP_CONF_THRESHOLD = 0.50
_INCONCLUSIVENESS_GAP_THRESHOLD = 0.15
_DETECTION_DISPLAY_THRESHOLD = 0.15
```

| Constant | Meaning | Effect if raised |
|----------|---------|-----------------|
| `TOP_CONF_THRESHOLD` | Top class must be above this | More images flagged inconclusive |
| `GAP_THRESHOLD` | Gap between top-2 must exceed this | More images flagged inconclusive |
| `DISPLAY_THRESHOLD` | Classes below this hidden from Groq | Fewer noisy classes sent to LLM |

If the models are high-confidence, lower `TOP_CONF_THRESHOLD`. If the gap is rarely > 15%, lower `GAP_THRESHOLD`. Coordinate with Ankit before changing since it's his file.

---

## Testing

```bash
# All tests, no model loading needed
python -m pytest tests/test_groq_client.py tests/test_clarification.py tests/test_summarizer.py -v

# Full suite
python -m pytest tests/ -v
```

The test files mock all Groq API calls. You never need real API credits to run unit tests.

---

## Verification Checklist (your responsibility)

- [ ] `python -m pytest tests/test_predictor.py -v` — all pass including `all_disease_detections` tests
- [ ] `python -m pytest tests/test_groq_client.py tests/test_clarification.py tests/test_summarizer.py -v` — all pass
- [ ] With a real `GROQ_API_KEY`: `complete()` returns a string, `stream()` yields tokens
- [ ] Clarification JSON parse: test `_parse_response()` on raw responses from the real model; adjust `_strip_fences()` if needed
- [ ] Summarization: set `SUMMARIZE_THRESHOLD = 200` temporarily, run 5 chat turns, verify history is compressed
- [ ] `data/medications.json` — all 5 diseases have at least 1 medication entry with correct schema
- [ ] Groq treatment plan: verify no medication names appear that are not in `medications.json`
- [ ] Verify prompt: if response mentions an unlisted medication, strengthen the constraint in `TREATMENT_SYSTEM_PROMPT`
