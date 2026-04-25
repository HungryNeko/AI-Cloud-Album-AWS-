"""
Local realistic integration test for the four Lambda handlers without AWS.

Run from repo root:
    python lambda/test_docker_handlers.py

This script simulates DynamoDB and S3 locally and executes a full flow:
upload -> class -> name -> download.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import io
import json
import os
import shutil
import sys
import types
import zipfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "lambda"
DEFAULT_DATASET_ROOT = ROOT / "data" / "mini-imagenet-test"
ALLOWED_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

sys.dont_write_bytecode = True


class FakeContext:
    def __init__(self, remaining_ms: int = 5 * 60 * 1000):
        self.remaining_ms = remaining_ms

    def get_remaining_time_in_millis(self) -> int:
        return self.remaining_ms


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


def _split_update_clauses(expr: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in expr:
        if ch == "," and depth == 0:
            segment = "".join(buf).strip()
            if segment:
                parts.append(segment)
            buf = []
            continue
        if ch == "(":
            depth += 1
        elif ch == ")" and depth > 0:
            depth -= 1
        buf.append(ch)
    segment = "".join(buf).strip()
    if segment:
        parts.append(segment)
    return parts


def make_fake_aws_modules():
    state: dict[str, Any] = {
        "tables": {},
        "s3": {},
    }

    boto3_module = types.ModuleType("boto3")
    dynamodb_module = types.ModuleType("boto3.dynamodb")
    conditions_module = types.ModuleType("boto3.dynamodb.conditions")

    class FakeAttr:
        def __init__(self, name: str):
            self.name = name

        def eq(self, value: Any):
            return ("eq", self.name, value)

    class FakeTable:
        def __init__(self, table_name: str):
            self.table_name = table_name
            self._table = state["tables"].setdefault(table_name, {})

        def _item_key_from_item(self, item: dict[str, Any]) -> tuple[str, str]:
            if "user_id" in item and "image_id" in item:
                return (str(item["user_id"]), str(item["image_id"]))
            if "user_id" in item:
                return (str(item["user_id"]), "")
            raise ValueError("FakeTable only supports user_id or (user_id, image_id) keys")

        def _item_key_from_key(self, key: dict[str, Any]) -> tuple[str, str]:
            if "user_id" in key and "image_id" in key:
                return (str(key["user_id"]), str(key["image_id"]))
            if "user_id" in key:
                return (str(key["user_id"]), "")
            raise ValueError("FakeTable key requires user_id or user_id and image_id")

        def put_item(self, **kwargs):
            item = copy.deepcopy(kwargs["Item"])
            k = self._item_key_from_item(item)
            self._table[k] = item
            return {}

        def get_item(self, **kwargs):
            key = kwargs.get("Key", {})
            k = self._item_key_from_key(key)
            item = self._table.get(k)
            if item is None:
                return {}
            return {"Item": copy.deepcopy(item)}

        def scan(self, **kwargs):
            items = list(self._table.values())
            filt = kwargs.get("FilterExpression")
            if isinstance(filt, tuple) and len(filt) == 3 and filt[0] == "eq":
                _, attr, value = filt
                items = [item for item in items if item.get(attr) == value]

            proj = kwargs.get("ProjectionExpression")
            if proj:
                names = kwargs.get("ExpressionAttributeNames", {}) or {}
                proj_fields = [p.strip() for p in str(proj).split(",") if p.strip()]
                projected = []
                for item in items:
                    row = {}
                    for f in proj_fields:
                        attr = names.get(f, f)
                        if attr in item:
                            row[attr] = copy.deepcopy(item[attr])
                    projected.append(row)
                items = projected
            else:
                items = [copy.deepcopy(item) for item in items]

            limit = kwargs.get("Limit")
            if isinstance(limit, int) and limit >= 0:
                items = items[:limit]
            return {"Items": items, "LastEvaluatedKey": None}

        def update_item(self, **kwargs):
            key = kwargs.get("Key", {})
            k = self._item_key_from_key(key)
            item = copy.deepcopy(self._table.get(k, {}))
            if not item:
                item["user_id"] = k[0]
                item["image_id"] = k[1]

            expr = str(kwargs.get("UpdateExpression", "")).strip()
            names = kwargs.get("ExpressionAttributeNames", {}) or {}
            values = kwargs.get("ExpressionAttributeValues", {}) or {}
            if expr.startswith("SET "):
                expr = expr[4:]

            for clause in _split_update_clauses(expr):
                if "=" not in clause:
                    continue
                lhs, rhs = clause.split("=", 1)
                lhs = lhs.strip()
                rhs = rhs.strip()
                attr_name = names.get(lhs, lhs)

                if rhs.startswith("list_append("):
                    marker = "list_append(if_not_exists("
                    if not rhs.startswith(marker):
                        raise ValueError("unsupported update expression: " + rhs)
                    inner = rhs[len(marker):]
                    p = inner.find(")")
                    if p < 0:
                        raise ValueError("unsupported update expression: " + rhs)
                    if_not_exists_args = inner[:p]
                    rest = inner[p + 1:].strip()
                    if rest.startswith(","):
                        rest = rest[1:].strip()
                    if rest.endswith(")"):
                        rest = rest[:-1].strip()
                    a, b = [x.strip() for x in if_not_exists_args.split(",", 1)]
                    append_token = rest
                    base_attr = names.get(a, a)
                    base_default = copy.deepcopy(values[b])
                    append_val = copy.deepcopy(values[append_token])
                    current = copy.deepcopy(item.get(base_attr, base_default))
                    if current is None:
                        current = copy.deepcopy(base_default)
                    item[attr_name] = list(current) + list(append_val)
                    continue

                if rhs.startswith(":"):
                    item[attr_name] = copy.deepcopy(values[rhs])
                    continue

                raise ValueError("unsupported update expression rhs: " + rhs)

            self._table[k] = item
            return {}

    class FakeDynamoResource:
        def Table(self, name: str):
            return FakeTable(name)

    class FakeS3Client:
        def _bucket(self, bucket: str) -> dict[str, dict[str, Any]]:
            return state["s3"].setdefault(bucket, {})

        def upload_file(self, filename: str, bucket: str, key: str):
            p = Path(filename).resolve()
            if not p.exists():
                raise FileNotFoundError(str(p))
            self._bucket(bucket)[key] = {"source_path": str(p)}
            return None

        def upload_fileobj(self, fileobj, bucket: str, key: str):
            src_name = getattr(fileobj, "name", "")
            if isinstance(src_name, str) and src_name:
                p = Path(src_name).resolve()
                if p.exists():
                    self._bucket(bucket)[key] = {"source_path": str(p)}
                    return None
            pos = fileobj.tell()
            fileobj.seek(0)
            data = fileobj.read()
            fileobj.seek(pos)
            self._bucket(bucket)[key] = {"bytes": data}
            return None

        def download_fileobj(self, bucket: str, key: str, fileobj):
            obj = self._bucket(bucket).get(key)
            if obj is None:
                raise FileNotFoundError(f"s3 object not found: s3://{bucket}/{key}")
            if "source_path" in obj:
                data = Path(obj["source_path"]).read_bytes()
            else:
                data = obj.get("bytes", b"")
            fileobj.write(data)
            return None

    class FakeSession:
        def __init__(self, region_name: str | None = None):
            self.region_name = region_name

        def resource(self, name: str):
            if name == "dynamodb":
                return FakeDynamoResource()
            raise ValueError("unsupported resource: " + name)

        def client(self, name: str):
            if name == "s3":
                return FakeS3Client()
            raise ValueError("unsupported client: " + name)

    boto3_module.Session = FakeSession
    conditions_module.Attr = FakeAttr

    fake_modules = {
        "boto3": boto3_module,
        "boto3.dynamodb": dynamodb_module,
        "boto3.dynamodb.conditions": conditions_module,
    }
    return fake_modules, state


def set_env_for_test(work_dir: Path):
    temp_root = work_dir / "tmp_runtime"
    yolo_root = work_dir / "yolo_config"
    temp_root.mkdir(parents=True, exist_ok=True)
    yolo_root.mkdir(parents=True, exist_ok=True)
    overrides = {
        "AWS_REGION": "us-west-1",
        "DYNAMODB_IMAGE_TABLE": "ImageMetadata",
        "DYNAMODB_USER_TABLE": "Users",
        "S3_BUCKET": "fake-bucket",
        "DOWNLOAD_ZIP_PREFIX": "downloads",
        "LAMBDA_TIME_GUARD_SECONDS": "30",
        "TMP": str(temp_root),
        "TEMP": str(temp_root),
        "TMPDIR": str(temp_root),
        "YOLO_CONFIG_DIR": str(yolo_root),
    }
    old = {k: os.environ.get(k) for k in overrides}
    for k, v in overrides.items():
        os.environ[k] = v
    return old


def restore_env(old: dict[str, str | None]) -> None:
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def pick_dataset_images(dataset_root: Path, image_count: int) -> list[Path]:
    if not dataset_root.exists():
        raise FileNotFoundError("dataset root not found: " + str(dataset_root))
    files = [
        p
        for p in dataset_root.rglob("*")
        if p.is_file() and p.suffix.lower() in ALLOWED_IMAGE_SUFFIXES
    ]
    files.sort()
    if len(files) < image_count:
        raise ValueError(f"dataset images not enough: need {image_count}, found {len(files)}")
    return files[:image_count]


def create_upload_zip(work_dir: Path, dataset_root: Path, image_count: int) -> tuple[Path, list[Path]]:
    selected = pick_dataset_images(dataset_root, image_count)
    src_dir = work_dir / "input_images"
    src_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for i, p in enumerate(selected, start=1):
        target = src_dir / f"{i:03d}_{p.parent.name}_{p.name}"
        shutil.copyfile(p, target)
        copied.append(target)

    zip_path = work_dir / "input_upload.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for p in copied:
            zf.write(p, arcname=p.name)
    return zip_path, copied


def patch_upload_for_local(upload_module, work_dir: Path) -> None:
    def load_zip(self) -> list[Path]:
        link = str(self.zip_link)
        zip_path = Path(link[7:]) if link.startswith("file://") else Path(link)
        if not zip_path.exists():
            raise FileNotFoundError("zip file not found: " + str(zip_path))

        extract_dir = work_dir / f"upload_extract_{self.task_id}"
        if extract_dir.exists():
            shutil.rmtree(extract_dir, ignore_errors=True)
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        return [p for p in extract_dir.rglob("*") if p.is_file()]

    def write_s3(self, image_id: str, image_file) -> bool:
        bucket = os.getenv("S3_BUCKET", "")
        if not bucket:
            self.msg = "Error when writing to s3: S3_BUCKET is required"
            self.run_success = False
            return False
        p = Path(str(image_file))
        safe_name = p.name.replace("/", "_").replace("\\", "_")
        if not safe_name:
            safe_name = image_id
        s3_key = f"{self.user_id}/{image_id}/{safe_name}"
        s3 = upload_module.boto3.Session(region_name=os.getenv("AWS_REGION", "us-west-1")).client("s3")
        s3.upload_file(str(p), bucket, s3_key)
        return True

    upload_module.handler.load_zip = load_zip
    upload_module.handler.write_s3 = write_s3


def patch_class_for_local(class_module) -> None:
    def loadimages(self, image_list: list[str]) -> list[tuple[str, Image.Image]]:
        table = class_module._image_table()
        s3 = class_module.boto3.Session(region_name=os.getenv("AWS_REGION", "us-west-1")).client("s3")
        bucket = os.getenv("S3_BUCKET", "")
        out: list[tuple[str, Image.Image]] = []
        for image_id in image_list:
            user_id = self._resolve_user_id(table, image_id)
            if not user_id:
                raise ValueError("user_id not found for image_id: " + image_id)
            item = table.get_item(Key={"user_id": user_id, "image_id": image_id}).get("Item")
            if not item:
                raise ValueError("image record not found for image_id: " + image_id)
            s3_key = str(item.get("s3_key", ""))
            if not s3_key:
                raise ValueError("s3_key missing for image_id: " + image_id)
            buf = io.BytesIO()
            s3.download_fileobj(bucket, s3_key, buf)
            buf.seek(0)
            img = Image.open(buf)
            img.load()
            out.append((image_id, img))
        return out

    class_module.handler.loadimages = loadimages


def patch_download_tmp_for_local(download_module, work_dir: Path) -> None:
    seq = {"n": 0}

    def fake_mkdtemp(prefix: str = "tmp") -> str:
        seq["n"] += 1
        path = work_dir / "tmp_runtime" / f"{prefix}{seq['n']:04d}"
        path.mkdir(parents=True, exist_ok=True)
        return str(path)

    download_module.tempfile.mkdtemp = fake_mkdtemp


def parse_s3_link(link: str) -> tuple[str, str]:
    if not link.startswith("s3://"):
        raise ValueError("invalid s3 link: " + link)
    rest = link[5:]
    p = rest.split("/", 1)
    if len(p) != 2:
        raise ValueError("invalid s3 link: " + link)
    return p[0], p[1]


def test_full_pipeline(work_dir: Path, dataset_root: Path, image_count: int) -> dict[str, Any]:
    fake_aws_modules, fake_state = make_fake_aws_modules()

    upload_module = import_py(
        "local_test_upload_handler_" + uuid4().hex,
        LAMBDA_DIR / "upload" / "handler.py",
        fake_modules=fake_aws_modules,
    )
    class_module = import_py(
        "local_test_class_handler_" + uuid4().hex,
        LAMBDA_DIR / "class" / "handler.py",
        fake_modules=fake_aws_modules,
    )
    name_module = import_py(
        "local_test_name_handler_" + uuid4().hex,
        LAMBDA_DIR / "name" / "handler.py",
        fake_modules=fake_aws_modules,
    )
    download_module = import_py(
        "local_test_download_handler_" + uuid4().hex,
        LAMBDA_DIR / "download" / "handler.py",
        fake_modules=fake_aws_modules,
    )

    patch_upload_for_local(upload_module, work_dir)
    patch_class_for_local(class_module)
    patch_download_tmp_for_local(download_module, work_dir)

    zip_path, copied_images = create_upload_zip(work_dir, dataset_root, image_count)
    upload_event = {
        "task_id": "upload-full",
        "zip_link": "file://" + str(zip_path),
        "user_id": "user1@example.com",
    }
    upload_pro = upload_module.handler(upload_event, FakeContext())
    upload_pro.run()
    upload_reply = upload_pro.reply()
    assert_ok("upload_full", upload_reply)
    if len(upload_reply["images"]) != len(copied_images):
        raise AssertionError(f"upload_full image count mismatch: {upload_reply}")
    image_ids = upload_reply["images"]
    append_txt(work_dir / "pipeline.txt", "upload " + json.dumps(upload_reply))

    class_event = {"task_id": "class-full", "images": image_ids}
    class_pro = class_module.handler(class_event, FakeContext())
    class_pro.run()
    class_reply = class_pro.reply()
    assert_ok("class_full", class_reply)
    if class_reply["not_finished"]:
        raise AssertionError(f"class_full has unfinished images: {class_reply}")
    if sorted(class_reply["questions"].keys()) != sorted(image_ids):
        raise AssertionError(f"class_full questions mismatch: {class_reply}")
    append_txt(work_dir / "pipeline.txt", "class " + json.dumps(class_reply))

    table_items = fake_state["tables"].get(os.getenv("DYNAMODB_IMAGE_TABLE", "ImageMetadata"), {})
    for item in table_items.values():
        status = item.get("status")
        if status != "done":
            raise AssertionError(f"expected class status done, got {status}: {item}")

    name_event = {
        "task_id": "name-full",
        "images": {image_id: f"name-{i+1}" for i, image_id in enumerate(image_ids)},
    }
    name_pro = name_module.processor(name_event, FakeContext())
    name_pro.run()
    name_reply = name_pro.reply()
    assert_ok("name_full", name_reply)
    if name_reply["not_finished"]:
        raise AssertionError(f"name_full has unfinished images: {name_reply}")
    append_txt(work_dir / "pipeline.txt", "name " + json.dumps(name_reply))

    download_event = {"task_id": "download-full", "images": image_ids}
    download_pro = download_module.handler(download_event, FakeContext())
    download_pro.run()
    download_reply = download_pro.reply()
    assert_ok("download_full", download_reply)
    if not download_reply.get("zip_link"):
        raise AssertionError(f"download_full missing zip_link: {download_reply}")
    append_txt(work_dir / "pipeline.txt", "download " + json.dumps(download_reply))

    if len(table_items) != len(copied_images):
        raise AssertionError(f"db row count mismatch: expected {len(copied_images)}, got {len(table_items)}")

    for item in table_items.values():
        status = item.get("status")
        if status != "complete":
            raise AssertionError(f"expected final status complete, got {status}: {item}")
        answers = item.get("followup_answers", [])
        if not isinstance(answers, list) or len(answers) != 1:
            raise AssertionError(f"expected one followup answer, got {answers}: {item}")

    dl_bucket, dl_key = parse_s3_link(download_reply["zip_link"])
    s3_bucket = fake_state["s3"].get(dl_bucket, {})
    if dl_key not in s3_bucket:
        raise AssertionError("download zip not uploaded to fake s3: " + download_reply["zip_link"])

    user_table = fake_state["tables"].get(os.getenv("DYNAMODB_USER_TABLE", "Users"), {})
    user_item = user_table.get(("user1@example.com", ""))
    if not user_item or user_item.get("zip_download") != dl_key:
        raise AssertionError(f"user zip_download mismatch: {user_item}, expected {dl_key}")

    return {
        "upload": upload_reply,
        "class": class_reply,
        "name": name_reply,
        "download": download_reply,
        "db_rows": len(table_items),
        "user_zip_download": user_item.get("zip_download"),
        "s3_objects": sum(len(v) for v in fake_state["s3"].values()),
        "dataset_root": str(dataset_root),
        "image_count": len(copied_images),
    }


def test_not_finished_semantics(work_dir: Path) -> dict[str, Any]:
    fake_aws_modules, _ = make_fake_aws_modules()

    class_module = import_py(
        "local_test_class_handler_timeout_" + uuid4().hex,
        LAMBDA_DIR / "class" / "handler.py",
        fake_modules=fake_aws_modules,
    )
    name_module = import_py(
        "local_test_name_handler_timeout_" + uuid4().hex,
        LAMBDA_DIR / "name" / "handler.py",
        fake_modules=fake_aws_modules,
    )

    class_pro = class_module.handler(
        ["img1", "img2"],
        FakeContext(remaining_ms=1_000),
    )
    class_pro.run()
    class_reply = class_pro.reply()
    assert_ok("class_timeout", class_reply)
    if class_reply.get("msg") != "not finished":
        raise AssertionError(f"class timeout should be not finished: {class_reply}")

    name_pro = name_module.processor(
        {"task_id": "name-timeout", "images": {"img1": "A", "img2": "B"}},
        FakeContext(remaining_ms=1_000),
    )
    name_pro.run()
    name_reply = name_pro.reply()
    assert_ok("name_timeout", name_reply)
    if name_reply.get("msg") != "not finished":
        raise AssertionError(f"name timeout should be not finished: {name_reply}")

    append_txt(work_dir / "timeout.txt", "class " + json.dumps(class_reply))
    append_txt(work_dir / "timeout.txt", "name " + json.dumps(name_reply))
    return {"class_timeout": class_reply, "name_timeout": name_reply}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Realistic local lambda integration test (no AWS).")
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=None,
        help="Directory for local artifacts. Default uses a temporary directory.",
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DEFAULT_DATASET_ROOT,
        help="Dataset directory used to build upload ZIP.",
    )
    parser.add_argument(
        "--image-count",
        type=int,
        default=8,
        help="Number of real images to include in upload ZIP.",
    )
    parser.add_argument(
        "--keep",
        action="store_true",
        help="Keep the temporary work directory after the test.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    temp_dir: Path | None = None

    if args.work_dir is None:
        temp_dir = ROOT / ("lambda_test_" + uuid4().hex[:8])
        temp_dir.mkdir(parents=True, exist_ok=False)
        work_dir = temp_dir
    else:
        work_dir = args.work_dir.resolve()
        work_dir.mkdir(parents=True, exist_ok=True)

    old_env = set_env_for_test(work_dir)
    replies: dict[str, Any] = {}
    try:
        replies["full_pipeline"] = test_full_pipeline(
            work_dir=work_dir,
            dataset_root=args.dataset_root.resolve(),
            image_count=max(1, int(args.image_count)),
        )
        replies["not_finished_semantics"] = test_not_finished_semantics(work_dir)

        print("All lambda local realistic integration tests passed (no AWS needed).")
        print(json.dumps(replies, indent=2, default=str))
        if args.keep or args.work_dir is not None:
            print("Local test artifacts:", work_dir)
        else:
            print("Local test artifacts were cleaned. Use --keep to inspect them.")
        return 0
    except Exception as e:
        print("Local realistic integration test failed:", e)
        if args.keep or args.work_dir is not None:
            print("Local test artifacts:", work_dir)
        else:
            print("Use --keep to keep local test artifacts for debugging.")
        return 1
    finally:
        restore_env(old_env)
        if temp_dir is not None and not args.keep:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
