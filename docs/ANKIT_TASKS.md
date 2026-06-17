# Ankit's Tasks — Developer B (State Machine, UI, app.py)

## Your Ownership

| File | Status |
|------|--------|
| `chatbot/state.py` | Yours to own and extend |
| `chatbot/handlers.py` | Yours to own and extend |
| `app.py` | Yours to own and extend |

You do **not** edit `crop_detection/predictor.py`, `tracking/models.py`, or any file inside `chatbot/groq_client.py`, `chatbot/prompts.py`, `chatbot/clarification.py`, or `chatbot/summarizer.py`. If you need a change in those, raise it with Suhaan (Groq layer) or Ishaan (persistence).

---

## Interface Contracts

### With Suhaan (Developer A)
```python
# chatbot/groq_client.py — call signatures you depend on
from chatbot.groq_client import complete, stream

complete(messages: list[dict], system_prompt: str, model: str = "llama3-70b-8192") -> str
stream(messages: list[dict], system_prompt: str, model: str = "llama3-70b-8192") -> Iterator[str]
```

**During development:** stub these by monkeypatching in your test or by temporarily replacing the import with a lambda that returns a hardcoded string. Remove stubs before merging to main.

### With Ishaan (Developer C)
```python
# tracking/tracker_ui.py — one function you call in app.py
from tracking.tracker_ui import render_tracking_panel

render_tracking_panel(session_id: str, disease_name: str | None) -> None
```

Call this inside a `st.expander` in app.py when `session.disease_name` is not None.

### With Suhaan and Ishaan — shared data type
```python
from tracking.models import CropSession
```
`CropSession` is defined in `tracking/models.py` (Ishaan's file). If you need a new field, ask Ishaan to add it — you never edit that file directly.

---

## Day 1 Prerequisites (before you write any code)

1. Wait for Ishaan's PR #1: skeleton `tracking/models.py` with `CropSession` and `MedicineEntry`.
2. Wait for Suhaan's PR #2: `all_disease_detections` field added to `AnalysisResult` in `predictor.py`.
3. Once both are merged, branch off `main` and start your work.

---

## Task Breakdown

### Task 1 — Verify `chatbot/state.py` (already implemented, review and extend)

The file is at `chatbot/state.py`. Review:

- `init_session_state()` — called once per Streamlit rerun at the top of `streamlit_main()`
- `active_session()` — returns the currently selected `CropSession` or None
- `create_new_session(display_name)` — creates, persists, and activates a new session
- `append_message(session, role, content)` — appends to in-memory chat history
- `set_chat_mode(mode)` — changes `st.session_state.chat_mode`

If you add new session state keys, add them to `init_session_state()` so they are always initialised before use.

### Task 2 — Verify `chatbot/handlers.py` (already implemented, review and extend)

The file is at `chatbot/handlers.py`. Three public entry points:

```python
handle_image_analysis(result: AnalysisResult, user_message: str, session: CropSession)
    -> str | Iterator[str]  # str = inconclusive; Iterator = streaming Groq response

handle_camera_analysis(result: AnalysisResult, user_message: str, session: CropSession)
    -> str | Iterator[str]

handle_text_message(user_text: str, session: CropSession)
    -> ClarificationResult | Iterator[str]
```

In `app.py`, check the return type before rendering:
```python
response = handlers.handle_image_analysis(result, note, session)
if isinstance(response, str):
    # inconclusive — display canned message
    with st.chat_message("assistant"):
        st.markdown(response)
else:
    # streaming treatment plan
    with st.chat_message("assistant"):
        full = st.write_stream(response)
    append_message(session, "assistant", full)
```

### Task 3 — `app.py` state machine (already implemented, test each mode)

The chatbot has 5 modes. Test each manually:

| Mode | What renders | Transition to |
|------|-------------|--------------|
| `ONBOARDING` | Three buttons | `AWAITING_UPLOAD`, `AWAITING_CAPTURE`, or `CLARIFYING` |
| `AWAITING_UPLOAD` | File uploader | `ACTIVE_TREATMENT` (or stays on inconclusive) |
| `AWAITING_CAPTURE` | WebRTC streamer | `ACTIVE_TREATMENT` (or stays on inconclusive) |
| `CLARIFYING` | `st.chat_input` | `ACTIVE_TREATMENT` when Groq resolves |
| `ACTIVE_TREATMENT` | `st.chat_input` + medicine panel | Stays here for ongoing chat |

### Task 4 — Sidebar session management

Located in the sidebar block of `app.py`. Verify:
- Creating a new session switches to it and shows ONBOARDING
- Switching sessions renders the correct chat history
- Deleting a session removes it from SQLite and switches to another session (or None)

### Task 5 — `@st.fragment` (optional performance upgrade)

Once the basic flow works, wrap the chat render + `st.chat_input` in `@st.fragment` to prevent the WebRTC streamer from resetting on every chat message:

```python
@st.fragment
def _chat_panel(session: CropSession) -> None:
    for msg in session.chat_history:
        if msg["role"] == "system":
            continue
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Type your message...", disabled=st.session_state.groq_thinking)
    if user_input:
        # ... handle input ...
        st.rerun(scope="fragment")
```

The WebRTC streamer must remain **outside** the fragment.

---

## Running the App During Development

```bash
# Groq API key must be set
export GROQ_API_KEY=your_key_here

# From the project root
streamlit run app.py
```

To stub Groq during UI development (so you don't need API credits while testing layout):

```python
# Temporary stub at the top of app.py — remove before merging
import chatbot.groq_client as _gc
_gc.stream = lambda msgs, sys, **kw: iter(["Stubbed response from Groq."])
_gc.complete = lambda msgs, sys, **kw: '{"has_enough_info": false, "question": "What crop?"}'
```

---

## What Not to Touch

- `crop_detection/` — read-only for you; call `analyze_image()` but don't modify it
- `tracking/models.py` — Ishaan's file; request changes via PR review
- `chatbot/groq_client.py`, `chatbot/prompts.py`, `chatbot/clarification.py`, `chatbot/summarizer.py` — Suhaan's files
- `data/medications.json` — Suhaan's file

---

## Verification Checklist (your responsibility)

- [ ] `streamlit run app.py` starts without errors
- [ ] Creating a new session and switching between sessions works
- [ ] All 5 chat modes transition correctly
- [ ] Upload path: image → analysis expander → Groq treatment plan appears in chat
- [ ] Camera path: capture → analysis expander → Groq treatment plan appears in chat
- [ ] Describe path: opens clarification, questions appear, resolves into treatment plan
- [ ] Inconclusive detection: "please resend image" message appears, no Groq call made
- [ ] Medicine tracker panel appears after diagnosis and entries save across browser close
- [ ] Deleting a session removes it from the sidebar and from SQLite
