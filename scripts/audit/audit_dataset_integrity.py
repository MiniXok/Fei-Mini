#!/usr/bin/env python3
"""Audit 6: Dataset Integrity and Data Leakage Audit."""

import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.generator.schema import ALL_FAMILIES, SchemaGenerator
from feimini.generator.tasks import TaskGenerator


def audit_dataset_integrity():
    # 1. Manifest Hash Verification
    manifest_path = "datasets/test_manifest.json"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    print("Verifying test manifest SHA-256 integrity...")
    test_dir = "datasets/test"
    test_files = sorted([f for f in os.listdir(test_dir) if f.endswith(".json")])
    assert len(test_files) == manifest["task_count"], f"Mismatch in test files count: {len(test_files)} vs {manifest['task_count']}"

    hasher = hashlib.sha256()
    for item in manifest["tasks"]:
        tid = item["task_id"]
        tpath = os.path.join(test_dir, f"{tid}.json")
        with open(tpath, "r", encoding="utf-8") as f:
            task_dict = json.load(f)
        task_bytes = json.dumps(task_dict, sort_keys=True).encode("utf-8")
        h = hashlib.sha256(task_bytes).hexdigest()
        assert h == item["sha256"], f"Task {tid} hash mismatch: {h} vs {item['sha256']}"
        hasher.update(h.encode("utf-8"))

    computed_manifest_hash = hasher.hexdigest()
    assert computed_manifest_hash == manifest["manifest_hash"], f"Manifest hash mismatch: {computed_manifest_hash} vs {manifest['manifest_hash']}"
    print(f"Manifest Verified: OK ({computed_manifest_hash})")

    # 2. Check Schema Separation between splits
    schema_gen = SchemaGenerator()
    train_fams = {f.family_name for f in schema_gen.train_dev_families}
    test_fams = {f.family_name for f in schema_gen.test_families}
    print(f"Train/Dev schema families: {train_fams}")
    print(f"Test-only schema families: {test_fams}")
    assert train_fams.isdisjoint(test_fams), "Train and Test schema families overlap!"

    # 3. Check for task duplication across train, dev, test
    def load_task_fingerprints(split_dir):
        fps = {}
        for fname in sorted(os.listdir(split_dir)):
            if fname.endswith(".json"):
                with open(os.path.join(split_dir, fname), "r", encoding="utf-8") as f:
                    data = json.load(f)
                fp = json.dumps(data["gold_ast"], sort_keys=True)
                fps[fname] = fp
        return fps

    train_fps = load_task_fingerprints("datasets/train")
    dev_fps = load_task_fingerprints("datasets/dev")
    test_fps = load_task_fingerprints("datasets/test")

    print(f"Loaded tasks count: train={len(train_fps)}, dev={len(dev_fps)}, test={len(test_fps)}")

    # Check overlaps between dev and test
    dev_fp_set = set(dev_fps.values())
    test_fp_set = set(test_fps.values())
    train_fp_set = set(train_fps.values())

    dev_test_overlap = dev_fp_set.intersection(test_fp_set)
    train_test_overlap = train_fp_set.intersection(test_fp_set)
    print(f"Exact Gold AST overlaps between Train and Test: {len(train_test_overlap)}")
    print(f"Exact Gold AST overlaps between Dev and Test: {len(dev_test_overlap)}")
    assert len(train_test_overlap) == 0, "Train and Test share identical gold ASTs!"
    assert len(dev_test_overlap) == 0, "Dev and Test share identical gold ASTs!"

    # 4. Gold AST and Hidden Instances Isolation in TaskSpec
    print("Verifying public TaskSpec isolation...")
    with open("datasets/dev/dev_0000.json") as f:
        dev_sample = json.load(f)
    assert "task_spec" in dev_sample
    spec = dev_sample["task_spec"]
    assert "gold_ast" not in spec
    assert "hidden_instances" not in spec

    results = {
        "manifest_valid": True,
        "manifest_hash": computed_manifest_hash,
        "train_families": list(train_fams),
        "test_families": list(test_fams),
        "train_count": len(train_fps),
        "dev_count": len(dev_fps),
        "test_count": len(test_fps),
        "train_test_overlap_count": len(train_test_overlap),
        "dev_test_overlap_count": len(dev_test_overlap),
    }

    os.makedirs("results/audit", exist_ok=True)
    with open("results/audit/audit6_dataset_integrity.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print("Audit 6 Complete: All integrity checks passed successfully!")


if __name__ == "__main__":
    audit_dataset_integrity()
