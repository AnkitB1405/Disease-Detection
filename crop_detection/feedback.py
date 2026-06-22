"""Live-learning feedback capture and immediate YOLOv5 fine-tuning.

This module is pure Python — it imports no Streamlit symbols so it stays usable
from a future FastAPI backend or a plain script (see ``docs/MULTI_USER_UPGRADE.md``).

The flow it backs (two-stage feedback in ``app.py``):

* Stage 1 — crop confirmation/correction -> a label for the single-class crop
  detector (``crop_detector.pt``). "Corn" writes a full-frame box; "Grape" (no
  corn present) writes an empty label, i.e. a background image.
* Stage 2 — disease confirmation/correction -> a label for the relevant disease
  model (``corn_disease.pt`` / ``grape_disease.pt``).

Every saved correction triggers an immediate, bounded fine-tune of the affected
model. Safety against catastrophic forgetting comes from three constraints that
must not be relaxed: the backbone is frozen (``--freeze 10`` — only the detection
head learns), training is short (``--epochs 5``), and each run mixes the new
example with a replay buffer of up to 50 past corrections.
"""

from __future__ import annotations

import json
import logging
import random
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
from uuid import uuid4

from PIL import Image

LOGGER = logging.getLogger(__name__)

# --- Live-learning knobs -------------------------------------------------- #
# Fine-tune after *every* correction. Safe only because of the frozen backbone,
# short schedule, and replay buffer below — do not raise the threshold expecting
# those to compensate; they are independent safeguards.
RETRAIN_THRESHOLD = 1
RETRAIN_EPOCHS = 5
RETRAIN_BATCH = 4
RETRAIN_FREEZE = 10          # freeze the backbone; only the head updates
REPLAY_BUFFER_SIZE = 50      # past corrections mixed into each run
INFERENCE_IMAGE_SIZE = 640

# Human-confirmed labels are certain; they fill (almost) the whole frame.
_FULL_FRAME_BOX = (0.5, 0.5, 0.98, 0.98)


@dataclass(frozen=True)
class _TrainTarget:
    """Resolved settings for one fine-tune run."""

    key: str                       # "crop" | "corn" | "grape"
    weights: Path                  # the .pt being updated in place
    class_names: tuple[str, ...]   # dataset names; must match the model head
    label_source: Path             # durable label store to assemble from


class FeedbackManager:
    """Persist user corrections and fine-tune the affected model on each one."""

    def __init__(self, project_root: Path) -> None:
        self.project_root = Path(project_root).resolve()
        self.models_dir = self.project_root / "models"
        self.yolov5_repo = self.project_root / "yolov5"

        self.feedback_dir = self.project_root / "feedback"
        self.images_dir = self.feedback_dir / "images"
        self.crop_labels_dir = self.feedback_dir / "labels"
        self.disease_labels_dir = self.feedback_dir / "disease_labels"
        self.runs_dir = self.feedback_dir / "_runs"
        self.log_path = self.feedback_dir / "feedback_log.jsonl"

        for directory in (
            self.images_dir,
            self.crop_labels_dir,
            self.disease_labels_dir / "corn",
            self.disease_labels_dir / "grape",
            self.runs_dir,
        ):
            directory.mkdir(parents=True, exist_ok=True)

        # Only one fine-tune may run at a time. A correction that arrives while a
        # run is in flight is still saved to disk; the next correction picks it up.
        self._retrain_lock = threading.Lock()
        # Set by the background worker after a successful hot-swap so the UI thread
        # can clear Streamlit's resource cache and reload the new weights.
        self._cache_clear_pending = threading.Event()

    # ------------------------------------------------------------------ #
    # Public API                                                          #
    # ------------------------------------------------------------------ #
    @property
    def is_retraining(self) -> bool:
        return self._retrain_lock.locked()

    def total_count(self) -> int:
        """Number of feedback entries recorded so far (append-only log)."""
        if not self.log_path.is_file():
            return 0
        with self.log_path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())

    def consume_cache_clear_pending(self) -> bool:
        """True once after a hot-swap completes; resets the flag. UI-thread only."""
        if self._cache_clear_pending.is_set():
            self._cache_clear_pending.clear()
            return True
        return False

    def save(
        self,
        image: Image.Image,
        correct_crop: str,
        predicted_crop: str,
        correct_disease: str | None = None,
        predicted_disease: str | None = None,
        disease_unknown: bool = False,
        disease_class_index: int | None = None,
    ) -> int:
        """Persist one correction and return the new total feedback count.

        Crop-label behaviour is unchanged from the original contract: Corn writes
        a full-frame detection box, Grape writes an empty (background) label.

        When ``correct_disease`` is given and ``disease_unknown`` is False, a
        disease label is additionally written under ``feedback/disease_labels/``.
        Nothing is ever overwritten — every call appends a new image, labels, and
        log line keyed by a unique stem.

        ``disease_class_index`` is the index of ``correct_disease`` within the
        disease model's ``.names`` (derived from the loaded model by the caller).
        """
        stem = f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}_{uuid4().hex[:8]}"
        image_name = f"{stem}.jpg"

        # 1. Persist the image (originals fill the frame in these close-ups).
        image.convert("RGB").save(self.images_dir / image_name, format="JPEG", quality=92)

        # 2. Crop-detector label (single class). Corn -> box, Grape -> empty file.
        crop_label_path = self.crop_labels_dir / f"{stem}.txt"
        if correct_crop == "Corn":
            cx, cy, w, h = _FULL_FRAME_BOX
            crop_label_path.write_text(f"0 {cx} {cy} {w} {h}\n", encoding="utf-8")
        else:
            crop_label_path.write_text("", encoding="utf-8")  # background image

        # 3. Disease-model label (only for confirmed/corrected, known diseases).
        if correct_disease is not None and not disease_unknown and disease_class_index is not None:
            crop_dir = "corn" if correct_crop == "Corn" else "grape"
            disease_label_path = self.disease_labels_dir / crop_dir / f"{stem}.txt"
            cx, cy, w, h = _FULL_FRAME_BOX
            # Spec record format: class_index confidence cx cy w h (confidence=1.0,
            # human-confirmed). The training workspace later drops the confidence
            # column to produce standard 5-column YOLO labels.
            disease_label_path.write_text(
                f"{disease_class_index} 1.0 {cx} {cy} {w} {h}\n", encoding="utf-8"
            )

        # 4. Append to the log — never overwrite an existing entry.
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "image": image_name,
            "crop": correct_crop,
            "predicted_crop": predicted_crop,
            "correct_crop": correct_crop,
            "predicted_disease": predicted_disease,
            "correct_disease": correct_disease,
            "disease_unknown": disease_unknown,
            "disease_class_index": disease_class_index,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")

        return self.total_count()

    def maybe_trigger_retrain(
        self,
        target: str,
        *,
        disease_crop: str | None = None,
        class_names: Sequence[str] | None = None,
    ) -> str:
        """Kick off a fine-tune of the affected model in the background.

        ``target`` is ``"crop"`` (crop detector) or ``"disease"`` (the disease
        model for ``disease_crop``). Returns one of:

        * ``"started"``      — a background fine-tune has begun.
        * ``"in_progress"``  — a run is already going; this correction is saved
                               on disk and will be folded into the next run.
        * ``"skipped"``      — below the retrain threshold or nothing to train on.
        """
        if RETRAIN_THRESHOLD <= 0 or self.total_count() % RETRAIN_THRESHOLD != 0:
            return "skipped"

        resolved = self._resolve_target(target, disease_crop, class_names)
        if resolved is None:
            return "skipped"

        # Non-blocking: if a run is live, keep the saved data and bail out.
        if not self._retrain_lock.acquire(blocking=False):
            return "in_progress"

        worker = threading.Thread(
            target=self._finetune_worker, args=(resolved,), daemon=True
        )
        worker.start()
        return "started"

    # ------------------------------------------------------------------ #
    # Internals                                                           #
    # ------------------------------------------------------------------ #
    def _resolve_target(
        self,
        target: str,
        disease_crop: str | None,
        class_names: Sequence[str] | None,
    ) -> _TrainTarget | None:
        if target == "crop":
            return _TrainTarget(
                key="crop",
                weights=self.models_dir / "crop_detector.pt",
                class_names=("Corn",),
                label_source=self.crop_labels_dir,
            )
        if target == "disease":
            if disease_crop == "Corn":
                return _TrainTarget(
                    key="corn",
                    weights=self.models_dir / "corn_disease.pt",
                    class_names=tuple(class_names or ()),
                    label_source=self.disease_labels_dir / "corn",
                )
            if disease_crop == "Grape":
                return _TrainTarget(
                    key="grape",
                    weights=self.models_dir / "grape_disease.pt",
                    class_names=tuple(class_names or ()),
                    label_source=self.disease_labels_dir / "grape",
                )
        return None

    def _finetune_worker(self, target: _TrainTarget) -> None:
        """Background entry point — always releases the lock when finished."""
        try:
            self._run_finetune(target)
        except Exception:  # never let a training failure kill the thread silently
            LOGGER.exception("Fine-tune run failed for target %s", target.key)
        finally:
            self._retrain_lock.release()

    def _run_finetune(self, target: _TrainTarget) -> None:
        train_script = self.yolov5_repo / "train.py"
        if not train_script.is_file():
            LOGGER.warning(
                "Skipping fine-tune: %s not found. Clone ultralytics/yolov5 into %s.",
                train_script,
                self.yolov5_repo,
            )
            return
        if not target.weights.is_file():
            LOGGER.warning("Skipping fine-tune: weights missing at %s", target.weights)
            return

        run_stamp = f"{target.key}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        workspace = self.runs_dir / run_stamp
        data_yaml = self._write_augmented_yaml(target, workspace)
        if data_yaml is None:
            LOGGER.info("Nothing to train on yet for target %s", target.key)
            return

        # Subprocess command structure is fixed; only --epochs / --batch are tuned
        # for single-example live learning, plus the mandatory --freeze.
        command = [
            sys.executable,
            str(train_script),
            "--img", str(INFERENCE_IMAGE_SIZE),
            "--batch", str(RETRAIN_BATCH),
            "--epochs", str(RETRAIN_EPOCHS),
            "--data", str(data_yaml),
            "--weights", str(target.weights),
            "--freeze", str(RETRAIN_FREEZE),
            "--project", str(workspace),
            "--name", "train",
            "--exist-ok",
        ]
        LOGGER.info("Starting fine-tune: %s", " ".join(command))
        log_file = workspace / "train_console.log"
        with log_file.open("w", encoding="utf-8") as handle:
            completed = subprocess.run(
                command,
                cwd=str(self.yolov5_repo),
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False,
            )

        if completed.returncode != 0:
            LOGGER.error(
                "Fine-tune exited with code %s. See %s", completed.returncode, log_file
            )
            return

        self._hot_swap(target, workspace)

    def _hot_swap(self, target: _TrainTarget, workspace: Path) -> None:
        """Back up the live weights, overwrite with the fresh best.pt, flag reload."""
        best = workspace / "train" / "weights" / "best.pt"
        if not best.is_file():
            LOGGER.warning("Fine-tune produced no best.pt at %s", best)
            return

        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = target.weights.with_name(f"{target.weights.stem}.bak_{stamp}.pt")
        shutil.copy2(target.weights, backup)
        shutil.copy2(best, target.weights)
        LOGGER.info(
            "Hot-swapped %s (backup at %s). Flagging model-cache reload.",
            target.weights.name,
            backup.name,
        )
        # The UI thread clears Streamlit's resource cache on its next run so the
        # updated weights load without restarting the app.
        self._cache_clear_pending.set()

    def _write_augmented_yaml(self, target: _TrainTarget, workspace: Path) -> Path | None:
        """Assemble a training workspace (new example + replay buffer) + data.yaml.

        Builds ``<workspace>/{images,labels}`` from the newest correction plus up
        to ``REPLAY_BUFFER_SIZE`` randomly sampled past corrections, writes a
        ``train.txt`` image list (the replay buffer paths live here alongside the
        new one), and returns the path to the generated ``data.yaml``.
        """
        stems = self._labelled_stems(target)
        if not stems:
            return None

        newest = stems[-1]
        older = stems[:-1]
        replay = random.sample(older, min(REPLAY_BUFFER_SIZE, len(older))) if older else []
        selected = replay + [newest]  # always include the just-saved correction

        ws_images = workspace / "images"
        ws_labels = workspace / "labels"
        ws_images.mkdir(parents=True, exist_ok=True)
        ws_labels.mkdir(parents=True, exist_ok=True)

        train_list: list[str] = []
        for stem in selected:
            src_image = self.images_dir / f"{stem}.jpg"
            if not src_image.is_file():
                continue
            label = self._yolo_label_for(target, stem)
            if label is None:
                continue
            shutil.copy2(src_image, ws_images / f"{stem}.jpg")
            (ws_labels / f"{stem}.txt").write_text(label, encoding="utf-8")
            train_list.append(str((ws_images / f"{stem}.jpg").resolve()))

        if not train_list:
            return None

        train_txt = workspace / "train.txt"
        train_txt.write_text("\n".join(train_list) + "\n", encoding="utf-8")

        names = list(target.class_names) or ["object"]
        data_yaml = workspace / "data.yaml"
        names_block = "\n".join(f"  {i}: {name}" for i, name in enumerate(names))
        data_yaml.write_text(
            "# Auto-generated live-learning dataset (new correction + replay buffer)\n"
            f"train: {train_txt.resolve()}\n"
            f"val: {train_txt.resolve()}\n"
            f"nc: {len(names)}\n"
            "names:\n"
            f"{names_block}\n",
            encoding="utf-8",
        )
        return data_yaml

    def _labelled_stems(self, target: _TrainTarget) -> list[str]:
        """Stems that have a usable label for this target, oldest -> newest."""
        if not target.label_source.is_dir():
            return []
        files = sorted(target.label_source.glob("*.txt"))
        return [f.stem for f in files]

    def _yolo_label_for(self, target: _TrainTarget, stem: str) -> str | None:
        """Return standard 5-column YOLO label text for one example, or None."""
        label_path = target.label_source / f"{stem}.txt"
        if not label_path.is_file():
            return None
        raw = label_path.read_text(encoding="utf-8").strip()

        if target.key == "crop":
            # Crop labels are already standard (empty for Grape backgrounds).
            return raw + ("\n" if raw else "")

        # Disease records are 6-column (class conf cx cy w h); drop the confidence.
        lines: list[str] = []
        for line in raw.splitlines():
            parts = line.split()
            if len(parts) == 6:
                cls, _conf, cx, cy, w, h = parts
                lines.append(f"{cls} {cx} {cy} {w} {h}")
            elif len(parts) == 5:
                lines.append(line)
        return ("\n".join(lines) + "\n") if lines else None
