"""
Local smoke test for the four Lambda Docker handlers.

Run from repo root:
    python lambda/test_docker_handlers.py

This script does not change the handler files. It monkeypatches unfinished
database/S3/model functions and uses local txt files as a tiny fake server.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import sys
import types
from pathlib import Path
from typing import Any
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"

sys.dont_write_bytecode = True


class FakeContext:
    def __init__(self, remaining_ms: int = 5 * 60 * 1000):
        self.remaining_ms = remaining_ms

    def get_remaining_time_in_millis(self) -> int:
        return self.remaining_ms


class FakeImage:
    def __init__(self, image_id: str):
        self.image_id = image_id


class FakeClsProcessor:
    def predict(self, image: FakeImage) -> str:
        return "cat"

    def if_need_question(self, label: str) -> str:
        return "Do you know this cat's name?" if label == "cat" else ""

    def getlocation(self, image: FakeImage) -> tuple[float, float]:
        return (34.0219, -118.4814)


def import_py(module_name: str, file_path: Path, fake_modules: dict[str, Any] | None = None):
    fake_modules = fake_modules or {}
    old_modules = {}
    missing = object()

    for name, module in fake_modules.items():
        old_modules[name] = sys.modules.get(name, missing)
        sys.modules[name] = module

    old_path = list(sys.path)
    sys.path.insert(0, str(file_path.parent))
    try:
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot import {file_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path = old_path
        for name, old_module in old_modules.items():
            if old_module is missing:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = old_module


def append_txt(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def assert_ok(name: str, reply: dict[str, Any]) -> None:
    if not reply.get("run_success"):
        raise AssertionError(f"{name} failed: {reply}")


def make_fake_cls_modules() -> dict[str, Any]:
    processor_module = types.ModuleType("processor")
    processor_module.processor = FakeClsProcessor

    pil_module = types.ModuleType("PIL")
    image_module = types.ModuleType("PIL.Image")
    image_module.Image = FakeImage
    pil_module.Image = image_module

    return {
        "processor": processor_module,
        "PIL": pil_module,
        "PIL.Image": image_module,
    }


def test_cls(work_dir: Path) -> dict[str, Any]:
    module = import_py(
        "local_test_docker_cls_handler",
        LAMBDA_DIR / "docker_cls" / "handler.py",
        fake_modules=make_fake_cls_modules(),
    )

    def loadimages(self, image_list: list[str]) -> list[tuple[str, FakeImage]]:
        append_txt(work_dir / "server_read.txt", "cls loadimages " + json.dumps(image_list))
        return [(image_id, FakeImage(image_id)) for image_id in image_list]

    def write_database(self) -> bool:
        for image_id in self.wait_to_write:
            row = {
                "docker": "cls",
                "task_id": self.task_id,
                "image_id": image_id,
                "result": self.finished.get(image_id, {}),
            }
            append_txt(work_dir / "database.txt", json.dumps(row, default=str))
        return True

    module.handler.loadimages = loadimages
    module.handler.write_database = write_database

    pro = module.handler(
        {"task_id": "cls-test", "images": ["img1", "img2", "img3"]},
        FakeContext(),
    )
    pro.run()
    reply = pro.reply()
    assert_ok("docker_cls", reply)
    if reply["not_finished"]:
        raise AssertionError(f"docker_cls has unfinished images: {reply}")
    return reply


def test_name(work_dir: Path) -> dict[str, Any]:
    module = import_py(
        "local_test_docker_name_handler",
        LAMBDA_DIR / "docker_name" / "handler.py",
    )

    def write_database(self) -> bool:
        for image_id in self.wait_to_write:
            row = {
                "docker": "name",
                "taskid": self.taskid,
                "image_id": image_id,
                "name": self.tasks.get(image_id, ""),
            }
            append_txt(work_dir / "database.txt", json.dumps(row))
        return True

    module.processor.write_database = write_database

    pro = module.processor(
        {"taskid": "name-test", "images": {"img1": "Mimi", "img2": "Lucky"}},
        FakeContext(),
    )
    pro.run()
    reply = pro.reply()
    assert_ok("docker_name", reply)
    if reply["not_finished"]:
        raise AssertionError(f"docker_name has unfinished images: {reply}")
    return reply


def test_upload(work_dir: Path) -> dict[str, Any]:
    module = import_py(
        "local_test_docker_upload_handler",
        LAMBDA_DIR / "docker_upload" / "handler.py",
    )

    fake_zip_files = [
        work_dir / "upload_zip" / "a.txt",
        work_dir / "upload_zip" / "b.txt",
    ]
    for file_path in fake_zip_files:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text("fake image data: " + file_path.name, encoding="utf-8")

    def load_zip(self) -> list[Path]:
        append_txt(work_dir / "server_read.txt", "upload load_zip " + self.zip_link)
        return fake_zip_files

    def write_s3(self, image_id: str, image_file: Path) -> bool:
        append_txt(work_dir / "s3.txt", f"upload {image_id} <- {image_file}")
        return True

    def write_database(self, image_id: str, image_file: Path) -> bool:
        row = {
            "docker": "upload",
            "task_id": self.task_id,
            "user_id": self.user_id,
            "image_id": image_id,
            "file": str(image_file),
        }
        append_txt(work_dir / "database.txt", json.dumps(row))
        return True

    module.handler.load_zip = load_zip
    module.handler.write_s3 = write_s3
    module.handler.write_database = write_database

    pro = module.handler(
        {"task_id": "upload-test", "zip_link": "txt://fake-upload.zip", "user_id": "user1"},
        FakeContext(),
    )
    pro.run()
    reply = pro.reply()
    assert_ok("docker_upload", reply)
    if len(reply["images"]) != len(fake_zip_files):
        raise AssertionError(f"docker_upload image count is wrong: {reply}")
    return reply


def test_download(work_dir: Path) -> dict[str, Any]:
    module = import_py(
        "local_test_docker_download_handler",
        LAMBDA_DIR / "docker_download" / "handler.py",
    )

    def load_images(self, image_list: list[str]) -> list[Path]:
        append_txt(work_dir / "server_read.txt", "download load_images " + json.dumps(image_list))
        files = []
        for image_id in image_list:
            file_path = work_dir / "download_source" / f"{image_id}.txt"
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text("fake image data: " + image_id, encoding="utf-8")
            files.append(file_path)
        return files

    def make_zip(self, files: list[Path]) -> Path:
        zip_txt = work_dir / "download_zip.txt"
        lines = [file_path.read_text(encoding="utf-8") for file_path in files]
        zip_txt.write_text("\n".join(lines), encoding="utf-8")
        append_txt(work_dir / "server_write.txt", "download make_zip " + str(zip_txt))
        return zip_txt

    def write_s3(self, zip_file: Path) -> str:
        s3_path = work_dir / "s3_download_zip.txt"
        shutil.copyfile(zip_file, s3_path)
        append_txt(work_dir / "s3.txt", f"download {zip_file} -> {s3_path}")
        return "txt://" + str(s3_path)

    module.handler.load_images = load_images
    module.handler.make_zip = make_zip
    module.handler.write_s3 = write_s3

    pro = module.handler(
        {"task_id": "download-test", "images": ["img1", "img2"]},
        FakeContext(),
    )
    pro.run()
    reply = pro.reply()
    assert_ok("docker_download", reply)
    if not reply["zip_link"]:
        raise AssertionError(f"docker_download did not return zip_link: {reply}")
    return reply


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test Lambda Docker handlers locally.")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Directory for fake txt server files. Default uses a temporary directory.",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the temporary work directory after the test.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    temp_dir = None
    if args.work_dir is None:
        temp_dir = ROOT / ("lambda_docker_test_" + uuid4().hex[:8])
        temp_dir.mkdir(parents=True, exist_ok=False)
        work_dir = temp_dir
    else:
        work_dir = args.work_dir.resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

    replies = {}
    try:
        replies["docker_cls"] = test_cls(work_dir)
        replies["docker_name"] = test_name(work_dir)
        replies["docker_upload"] = test_upload(work_dir)
        replies["docker_download"] = test_download(work_dir)

        print("All docker handler smoke tests passed.")
        print(json.dumps(replies, indent=2))
        if args.keep or args.work_dir is not None:
            print("Fake txt server files:", work_dir)
        else:
            print("Fake txt server files were cleaned. Use --keep to inspect them.")
        return 0
    except Exception as e:
        print("Smoke test failed:", e)
        if args.keep or args.work_dir is not None:
            print("Fake txt server files:", work_dir)
        else:
            print("Use --keep to keep fake txt server files for debugging.")
        return 1
    finally:
        if temp_dir is not None and not args.keep:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
