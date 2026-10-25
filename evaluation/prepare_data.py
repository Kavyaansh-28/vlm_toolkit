"""Prepare POPE and CHAIR benchmark files (paper Sec. V-A).

    python -m evaluation.prepare_data --out data/benchmarks --images data/images \
        --pope-images 450 --chair-images 500 --tune-images 50 --seed 42 [--only pope|chair|smoke]

POPE questions come from the official POPE release (github.com/AoiDragon/POPE,
COCO random/popular/adversarial; fallback: the ``lmms-lab/POPE`` HF dataset).
Images are fetched individually from images.cocodataset.org.  50 POPE images
form a held-out tuning split that never appears in reported numbers.  CHAIR
ground truth is the COCO val2014 instance annotation set of each image.
"""
from __future__ import annotations

import argparse
import io
import json
import random
import re
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from claims.vocab import to_class

POPE_URL = "https://raw.githubusercontent.com/AoiDragon/POPE/main/output/coco/coco_pope_{split}.json"
COCO_IMAGE_URL = "http://images.cocodataset.org/val2014/{name}"
COCO_ANN_URL = "http://images.cocodataset.org/annotations/annotations_trainval2014.zip"
SPLITS = ("random", "popular", "adversarial")
POPE_PROMPT = "{question} Answer the question using a single word or phrase."
CHAIR_PROMPT = "Describe this image in detail."


def _get(url: str, timeout: int = 60) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "vlm-reliability-toolkit"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _image_id(name: str) -> int:
    return int(re.search(r"(\d{6,})", name).group(1))


def load_pope_questions() -> dict[str, list[dict]]:
    """{split: [{"image": "COCO_val2014_....jpg", "text": question, "label": "yes"|"no"}]}"""
    try:
        return {split: [json.loads(line) for line in _get(POPE_URL.format(split=split)).decode().splitlines() if line.strip()]
                for split in SPLITS}
    except Exception as exc:
        print(f"POPE GitHub release unavailable ({exc}); falling back to lmms-lab/POPE")
        from datasets import load_dataset
        rows = load_dataset("lmms-lab/POPE", split="test")
        out: dict[str, list[dict]] = {split: [] for split in SPLITS}
        for row in rows.remove_columns(["image"]):
            if row["category"] in out:
                out[row["category"]].append({"question_id": row["question_id"], "image": f"{row['image_source']}.jpg", "text": row["question"], "label": row["answer"]})
        return out


def download_images(names: list[str], image_dir: Path, workers: int = 16) -> list[str]:
    image_dir.mkdir(parents=True, exist_ok=True)

    def fetch(name: str) -> str | None:
        target = image_dir / name
        if target.exists() and target.stat().st_size > 0:
            return None
        try:
            target.write_bytes(_get(COCO_IMAGE_URL.format(name=name)))
            return None
        except Exception as exc:
            return f"{name}: {exc}"

    with ThreadPoolExecutor(workers) as pool:
        return [error for error in pool.map(fetch, names) if error]


def coco_instances(cache_dir: Path) -> tuple[dict[int, set[str]], dict[int, str]]:
    """image_id -> set of CHAIR classes, image_id -> file name (val2014)."""
    cache = cache_dir / "instances_val2014_objects.json"
    if cache.exists():
        data = json.loads(cache.read_text())
        return {int(k): set(v) for k, v in data["objects"].items()}, {int(k): v for k, v in data["files"].items()}
    print("Downloading COCO 2014 annotations (~240 MB, once)...")
    with zipfile.ZipFile(io.BytesIO(_get(COCO_ANN_URL, timeout=600))) as archive:
        annotations = json.loads(archive.read("annotations/instances_val2014.json"))
    categories = {c["id"]: to_class(c["name"], include_extra=False) or c["name"] for c in annotations["categories"]}
    objects: dict[int, set[str]] = {}
    for ann in annotations["annotations"]:
        objects.setdefault(ann["image_id"], set()).add(categories[ann["category_id"]])
    files = {img["id"]: img["file_name"] for img in annotations["images"]}
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"objects": {k: sorted(v) for k, v in objects.items()}, "files": {k: files[k] for k in objects}}))
    return objects, files


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))
    print(f"wrote {len(rows):5d} rows -> {path}")


def prepare(out: Path, images: Path, pope_images: int, chair_images: int, tune_images: int, seed: int, only: str = "all") -> None:
    rng = random.Random(seed)
    questions = load_pope_questions()
    pool = sorted({q["image"] for q in questions["random"]})
    rng.shuffle(pool)
    tune_set, eval_set = pool[:tune_images], pool[tune_images:tune_images + pope_images]
    assert not set(tune_set) & set(eval_set), "tuning and evaluation images must be disjoint"
    rel = lambda name: (images / name).as_posix()

    if only in {"all", "pope", "smoke"}:
        errors = download_images(tune_set + eval_set, images)
        failed = {e.split(":")[0] for e in errors}
        for split in SPLITS:
            rows = []
            for q in (x for x in questions[split] if x["image"] in eval_set and x["image"] not in failed):
                obj = re.search(r"is there an? (.+?) in the image", q["text"], flags=re.I).group(1).lower()
                rows.append({"sample_id": f"pope-{split}-{q['question_id']}", "benchmark": "pope", "split": split,
                             "image_id": _image_id(q["image"]), "image_path": rel(q["image"]), "object": obj,
                             "query": POPE_PROMPT.format(question=q["text"]), "label": q["label"].strip().lower() == "yes"})
            _write(out / f"pope_{split}.jsonl", rows)
        tune = []
        for q in (x for x in questions["random"] if x["image"] in tune_set and x["image"] not in failed):
            obj = re.search(r"is there an? (.+?) in the image", q["text"], flags=re.I).group(1).lower()
            tune.append({"sample_id": f"pope-tune-{q['question_id']}", "benchmark": "pope", "split": "tune",
                         "image_id": _image_id(q["image"]), "image_path": rel(q["image"]), "object": obj,
                         "query": POPE_PROMPT.format(question=q["text"]), "label": q["label"].strip().lower() == "yes"})
        _write(out / "pope_tune.jsonl", tune)
        if errors: print(f"{len(errors)} POPE image downloads failed (skipped): {errors[:3]}")

    if only in {"all", "chair", "smoke"}:
        objects, files = coco_instances(out.parent / "coco")
        chosen = [name for name in eval_set if _image_id(name) in objects][:chair_images]
        if len(chosen) < chair_images:  # top up with other val2014 images, never tuning ones
            excluded = {_image_id(n) for n in tune_set} | {_image_id(n) for n in chosen}
            extra = sorted(i for i in objects if i not in excluded)
            rng.shuffle(extra)
            chosen += [files[i] for i in extra[:chair_images - len(chosen)]]
        errors = download_images(chosen, images)
        failed = {e.split(":")[0] for e in errors}
        rows = [{"sample_id": f"chair-{_image_id(name)}", "benchmark": "chair", "split": "all", "image_id": _image_id(name),
                 "image_path": rel(name), "query": CHAIR_PROMPT, "gt_objects": sorted(objects[_image_id(name)])}
                for name in chosen if name not in failed]
        assert not {r["image_id"] for r in rows} & {_image_id(n) for n in tune_set}
        _write(out / "chair.jsonl", rows)
        if errors: print(f"{len(errors)} CHAIR image downloads failed (skipped): {errors[:3]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default="data/benchmarks"); parser.add_argument("--images", default="data/images")
    parser.add_argument("--pope-images", type=int, default=450); parser.add_argument("--chair-images", type=int, default=500)
    parser.add_argument("--tune-images", type=int, default=50); parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--only", choices=["all", "pope", "chair", "smoke"], default="all")
    args = parser.parse_args()
    if args.only == "smoke":  # tiny, fast set for laptops and the infra check
        args.pope_images, args.chair_images, args.tune_images = 2, 3, 1
    prepare(Path(args.out), Path(args.images), args.pope_images, args.chair_images, args.tune_images, args.seed, args.only)
