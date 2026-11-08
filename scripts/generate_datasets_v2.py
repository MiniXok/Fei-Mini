#!/usr/bin/env python3
"""全量数据集 v2 (feimini-mini-rel-v2) 生成脚本。

在统一统一语法与离散化字面量词表后，生成独立种子的训练集 (1,000)、开发集 (200) 与测试集 (200)，
并输出 SHA-256 锁定清单 datasets/v2/test_manifest.json。
"""

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from feimini.generator.tasks import TaskGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reproducible v2 datasets for Fei-Mini")
    parser.add_argument("--train-count", type=int, default=1000, help="Number of training tasks")
    parser.add_argument("--dev-count", type=int, default=200, help="Number of dev tasks")
    parser.add_argument("--test-count", type=int, default=200, help="Number of test tasks")
    parser.add_argument("--data-dir", type=str, default="datasets/v2", help="Root v2 datasets directory")
    args = parser.parse_args()

    generator = TaskGenerator(num_visible_examples=3, num_hidden_instances=3)
    start_time = time.time()

    print(f"Generating v2 train set ({args.train_count} tasks, seed 1042)...")
    train_dir = os.path.join(args.data_dir, "train")
    generator.generate_dataset("train", args.train_count, seed=1042, output_dir=train_dir)

    print(f"Generating v2 dev set ({args.dev_count} tasks, seed 1142)...")
    dev_dir = os.path.join(args.data_dir, "dev")
    generator.generate_dataset("dev", args.dev_count, seed=1142, output_dir=dev_dir)

    print(f"Generating v2 test set ({args.test_count} tasks, seed 1242)...")
    test_dir = os.path.join(args.data_dir, "test")
    test_tasks = generator.generate_dataset("test", args.test_count, seed=1242, output_dir=test_dir)

    manifest_path = os.path.join(args.data_dir, "test_manifest.json")
    print(f"Locking v2 test manifest at {manifest_path}...")
    manifest = generator.create_test_manifest(
        test_tasks,
        dataset_seed=1242,
        manifest_path=manifest_path,
        dataset_version="feimini-mini-rel-v2",
    )

    elapsed = time.time() - start_time
    print(f"v2 Dataset Generation Done in {elapsed:.2f}s!")
    print(f"v2 Test Manifest Hash: {manifest['manifest_hash']}")


if __name__ == "__main__":
    main()
