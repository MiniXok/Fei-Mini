#!/usr/bin/env python3
"""全量数据集生成脚本。

生成指定种子与规模的训练集 (1,000)、开发集 (200) 与测试集 (200)，
并输出 SHA-256 锁定清单 datasets/test_manifest.json。
"""

import argparse
import os
import sys
import time

# 确保 src 在模块搜索路径中
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from feimini.generator.tasks import TaskGenerator


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reproducible datasets for Fei-Mini")
    parser.add_argument("--train-count", type=int, default=1000, help="Number of training tasks")
    parser.add_argument("--dev-count", type=int, default=200, help="Number of dev tasks")
    parser.add_argument("--test-count", type=int, default=200, help="Number of test tasks")
    parser.add_argument("--data-dir", type=str, default="datasets", help="Root datasets directory")
    args = parser.parse_args()

    generator = TaskGenerator(num_visible_examples=3, num_hidden_instances=3)
    start_time = time.time()

    print(f"Generating train set ({args.train_count} tasks)...")
    train_dir = os.path.join(args.data_dir, "train")
    generator.generate_dataset("train", args.train_count, seed=42, output_dir=train_dir)

    print(f"Generating dev set ({args.dev_count} tasks)...")
    dev_dir = os.path.join(args.data_dir, "dev")
    generator.generate_dataset("dev", args.dev_count, seed=142, output_dir=dev_dir)

    print(f"Generating test set ({args.test_count} tasks)...")
    test_dir = os.path.join(args.data_dir, "test")
    test_tasks = generator.generate_dataset("test", args.test_count, seed=242, output_dir=test_dir)

    manifest_path = os.path.join(args.data_dir, "test_manifest.json")
    print(f"Locking test manifest at {manifest_path}...")
    manifest = generator.create_test_manifest(test_tasks, dataset_seed=242, manifest_path=manifest_path)

    elapsed = time.time() - start_time
    print(f"Done in {elapsed:.2f}s!")
    print(f"Test Manifest Hash: {manifest['manifest_hash']}")


if __name__ == "__main__":
    main()
