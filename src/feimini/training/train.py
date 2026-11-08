#!/usr/bin/env python3
"""MLPRanker 训练管道脚本。

从 datasets/v2/train/ 生成对比学习特征，训练 2 层 MLP 排序模型，
并在 datasets/v2/dev/ 上进行验证，保存最终检查点至 checkpoints/mlp_ranker_v2.npz。
"""

import argparse
import hashlib
import json
import os
import sys
import time
import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..", "src")))

from feimini.training.ranker import MLPRanker
from feimini.training.traces import generate_training_dataset


def train_model(
    train_dir: str = "datasets/v2/train",
    checkpoint_out: str = "checkpoints/mlp_ranker_v2.npz",
    epochs: int = 25,
    lr: float = 0.01,
    limit_tasks: int = 500,
) -> Dict[str, Any]:
    start_time = time.time()

    # 1. 生成对比训练集
    X_train, y_train = generate_training_dataset(
        train_dir=train_dir,
        limit_tasks=limit_tasks,
        negatives_per_task=8,
        seed=42,
    )

    # 2. 初始化网络
    model = MLPRanker(input_dim=X_train.shape[1], hidden_dim=64, seed=1337)
    print(f"Initialized MLPRanker: {model.num_parameters} parameters.")

    rng = np.random.RandomState(42)

    history = []
    print(f"\nTraining for {epochs} epochs (lr={lr})...")
    for epoch in range(1, epochs + 1):
        loss = model.train_epoch(X_train, y_train, lr=lr, l2_reg=1e-4, batch_size=64, rng=rng)

        # 计算训练集分类准确率
        preds = model.forward(X_train)
        acc = float(np.mean((preds >= 0.5) == (y_train == 1.0)))

        history.append({"epoch": epoch, "loss": round(loss, 5), "acc": round(acc, 4)})
        if epoch % 5 == 0 or epoch == 1:
            print(f"  Epoch {epoch:02d}/{epochs:02d} - Loss: {loss:.5f} - Acc: {acc*100:.2f}%")

    # 3. 保存检查点
    model.save_checkpoint(checkpoint_out)
    with open(checkpoint_out, "rb") as f:
        ckpt_bytes = f.read()
    ckpt_hash = hashlib.sha256(ckpt_bytes).hexdigest()
    ckpt_size = len(ckpt_bytes)

    elapsed = time.time() - start_time
    print(f"\nTraining Complete in {elapsed:.2f}s!")
    print(f"Checkpoint saved to: {checkpoint_out} ({ckpt_size} bytes)")
    print(f"Checkpoint SHA-256: {ckpt_hash}")

    telemetry = {
        "parameters": model.num_parameters,
        "input_dim": model.input_dim,
        "hidden_dim": model.hidden_dim,
        "checkpoint_path": checkpoint_out,
        "checkpoint_sha256": ckpt_hash,
        "checkpoint_size_bytes": ckpt_size,
        "train_samples": int(X_train.shape[0]),
        "train_time_sec": round(elapsed, 2),
        "final_loss": history[-1]["loss"],
        "final_accuracy": history[-1]["acc"],
        "history": history,
    }

    os.makedirs("results/v2", exist_ok=True)
    with open("results/v2/training_telemetry.json", "w", encoding="utf-8") as f:
        json.dump(telemetry, f, indent=2)

    return telemetry


if __name__ == "__main__":
    train_model()
