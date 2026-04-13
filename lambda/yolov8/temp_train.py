from contextlib import contextmanager
import os
from pathlib import Path
import shutil
import sys

from ultralytics import YOLO
from tqdm import tqdm


DATASET_DIR = Path(r"D:\Github\EE510project\datasets\mini-imagenet")
RUNS_PROJECT = Path(__file__).resolve().parent / "runs"
RUN_NAME = "mini_imagenet_yolov8n_temp"
WEIGHTS_DIR = Path(__file__).resolve().parent / "weights"


@contextmanager
def _suppress_stderr():
    stderr_fd = sys.stderr.fileno()
    saved_stderr = os.dup(stderr_fd)
    try:
        with open(os.devnull, "w") as devnull:
            os.dup2(devnull.fileno(), stderr_fd)
            yield
    finally:
        os.dup2(saved_stderr, stderr_fd)
        os.close(saved_stderr)


def main() -> None:
    model = YOLO("yolov8n-cls.pt")
    progress = {"bar": None}

    def _on_train_start(trainer):
        progress["bar"] = tqdm(total=trainer.epochs, desc="train", unit="epoch", file=sys.stdout)

    def _on_fit_epoch_end(trainer):
        if progress["bar"] is not None:
            progress["bar"].update(1)

    def _on_train_end(trainer):
        if progress["bar"] is not None:
            progress["bar"].close()
            progress["bar"] = None

    model.add_callback("on_train_start", _on_train_start)
    model.add_callback("on_fit_epoch_end", _on_fit_epoch_end)
    model.add_callback("on_train_end", _on_train_end)

    with _suppress_stderr():
        results = model.train(
            data=str(DATASET_DIR),
            epochs=100,
            imgsz=224,
            device=0,
            project=str(RUNS_PROJECT),
            name=RUN_NAME,
            exist_ok=True,
        )

    run_dir = Path(results.save_dir)
    best_pt = run_dir / "weights" / "best.pt"
    last_pt = run_dir / "weights" / "last.pt"

    WEIGHTS_DIR.mkdir(parents=True, exist_ok=True)

    if best_pt.exists():
        shutil.copy2(best_pt, WEIGHTS_DIR / "yolov8n-cls-miniimagenet-best.pt")
        print(f"Saved: {WEIGHTS_DIR / 'yolov8n-cls-miniimagenet-best.pt'}")

    if last_pt.exists():
        shutil.copy2(last_pt, WEIGHTS_DIR / "yolov8n-cls-miniimagenet-last.pt")
        print(f"Saved: {WEIGHTS_DIR / 'yolov8n-cls-miniimagenet-last.pt'}")


if __name__ == "__main__":
    main()
