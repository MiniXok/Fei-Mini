#!/usr/bin/env python3
"""Phase 3: M6.2.1 生产级已安装 CLI 入口安全回归审计脚本。

通过真实已安装的控制台入口 (feimini query) 执行完整的对抗渗透测试，
包括：INSERT, UPDATE, DELETE, DROP, CREATE, ALTER, ATTACH, DETACH, PRAGMA, 多语句注入,
伪造 SQL 的自然语言提问，恶意标识符。
比对测试前后数据库文件的 SHA-256 哈希值，检查是否有任何 WAL/SHM/journal 残留。
"""

import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import tempfile


SECURITY_VECTORS = [
    ("INSERT", 'Insert into records values (99, "malicious", 0.0)'),
    ("UPDATE", 'Update records set secret = "compromised" where id = 1'),
    ("DELETE", 'Delete from records where id = 1'),
    ("DROP_TABLE", 'Drop table records'),
    ("CREATE_TABLE", 'Create table backdoor (id int)'),
    ("ALTER_TABLE", 'Alter table records add column leak text'),
    ("ATTACH_DB", "Attach database ':memory:' as evil"),
    ("DETACH_DB", "Detach database evil"),
    ("PRAGMA_MUTATION", "PRAGMA writable_schema = ON;"),
    ("MULTI_STATEMENT", "Show records; DROP TABLE records; --"),
    ("SQL_LOOKING_NL", "What happens if a user types DROP TABLE records in a query?"),
    ("INJECTION_QUOTES", 'Show records where secret = "foo" OR "1"="1"'),
]


def run_security_regression(cli_path="/tmp/feimini_test_env/bin/feimini"):
    print("=" * 88)
    print("  Fei-Mini M6.2.1: CLI Entry Point Read-Only Security Regression Audit")
    print("=" * 88)

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = os.path.join(tmp_dir, "audit_security.db")

        # 1. 初始化包含测试敏感数据的 SQLite 数据库
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, secret TEXT, balance REAL);")
        c.executemany("INSERT INTO records VALUES (?, ?, ?);", [
            (1, "confidential_alpha", 1500.0),
            (2, "confidential_beta", 2500.0),
            (3, "confidential_gamma", 3500.0),
        ])
        conn.commit()
        conn.close()

        # 2. 计算初始磁盘文件 SHA-256 哈希
        with open(db_path, "rb") as f:
            initial_sha256 = hashlib.sha256(f.read()).hexdigest()
        print(f"Initial Database File SHA-256: {initial_sha256}")

        vector_results = []
        all_passed = True

        for attack_name, query_text in SECURITY_VECTORS:
            cmd = [
                cli_path,
                "query",
                "--db", db_path,
                "--question", query_text,
                "--timeout", "10",
                "--format", "json",
            ]

            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={k: v for k, v in os.environ.items() if k != "PYTHONPATH"},
            )

            # 验证执行结果
            # 无论何种载荷，数据库写操作必须被拦截 (要么返回错误，要么在 JSON 中标记 unsupported/rejection)
            intercepted = False
            response_json = None
            if proc.stdout:
                try:
                    response_json = json.loads(proc.stdout)
                    if response_json.get("is_unsupported") or not response_json.get("success"):
                        intercepted = True
                    # 如果查询成功执行，必须只能是纯读 SELECT 且未改变数据
                except Exception:
                    pass

            if proc.returncode != 0 or "[Unsupported Request]" in proc.stdout or "[Error]" in proc.stderr or "[Error]" in proc.stdout:
                intercepted = True

            # 检查当前哈希是否完全未变
            with open(db_path, "rb") as f:
                cur_sha256 = hashlib.sha256(f.read()).hexdigest()

            file_unchanged = (cur_sha256 == initial_sha256)

            # 检查临时文件
            has_wal = os.path.exists(db_path + "-wal")
            has_shm = os.path.exists(db_path + "-shm")
            has_journal = os.path.exists(db_path + "-journal")
            clean_sidecars = not (has_wal or has_shm or has_journal)

            test_ok = file_unchanged and clean_sidecars
            if not test_ok:
                all_passed = False

            status_str = "BLOCKED / SAFE" if test_ok else "VULNERABILITY DETECTED"
            print(f"[{attack_name:<18}] -> {status_str} (File unchanged: {file_unchanged}, Clean sidecars: {clean_sidecars})")

            vector_results.append({
                "vector": attack_name,
                "payload": query_text,
                "exit_code": proc.returncode,
                "intercepted_or_safe": intercepted,
                "file_hash_intact": file_unchanged,
                "clean_sidecars": clean_sidecars,
            })

        # 最终哈希核对
        with open(db_path, "rb") as f:
            final_sha256 = hashlib.sha256(f.read()).hexdigest()

        print("-" * 88)
        print(f"Final Database File SHA-256:   {final_sha256}")
        print(f"Cryptographic Identity Check:  {'MATCH (0 bytes modified)' if final_sha256 == initial_sha256 else 'MISMATCH'}")
        print("=" * 88)

        report = {
            "initial_sha256": initial_sha256,
            "final_sha256": final_sha256,
            "hash_identical": (initial_sha256 == final_sha256),
            "all_vectors_safe": all_passed,
            "vector_details": vector_results,
        }

        os.makedirs("results/v2", exist_ok=True)
        with open("results/v2/m6_2_1_security_audit.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        return report


if __name__ == "__main__":
    cli = sys.argv[1] if len(sys.argv) > 1 else "/tmp/feimini_test_env/bin/feimini"
    run_security_regression(cli)
