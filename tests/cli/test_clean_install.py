"""Fei-Mini 干净虚拟环境分发安装与独立运行集成测试 (Phase 1 & 7)."""

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest


class TestCleanInstallation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.wheel_path = os.path.abspath("dist/feimini-0.1.0-py3-none-any.whl")
        cls.sdist_path = os.path.abspath("dist/feimini-0.1.0.tar.gz")

        # 确保发行包存在
        if not (os.path.exists(cls.wheel_path) and os.path.exists(cls.sdist_path)):
            subprocess.run([sys.executable, "-m", "pip", "wheel", ".", "--no-deps", "-w", "dist/"], check=True)
            subprocess.run([sys.executable, "-c", "import setuptools.build_meta; setuptools.build_meta.build_sdist('dist')"], check=True)

    def test_wheel_and_sdist_checksums_exist(self) -> None:
        """测试 wheel 与 sdist 文件完整且可计算 SHA-256。"""
        with open(self.wheel_path, "rb") as f:
            w_hash = hashlib.sha256(f.read()).hexdigest()
        with open(self.sdist_path, "rb") as f:
            s_hash = hashlib.sha256(f.read()).hexdigest()

        self.assertEqual(len(w_hash), 64)
        self.assertEqual(len(s_hash), 64)

    def test_clean_venv_installation_and_isolated_execution(self) -> None:
        """测试在干净隔离虚拟环境中安装 wheel，并在外部目录无 PYTHONPATH 下正常运行。"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            venv_dir = os.path.join(tmp_dir, "clean_env")
            subprocess.run([sys.executable, "-m", "venv", venv_dir], check=True)

            pip_bin = os.path.join(venv_dir, "bin", "pip")
            feimini_bin = os.path.join(venv_dir, "bin", "feimini")

            # 1. pip install wheel outside project root
            clean_env_vars = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
            install_proc = subprocess.run(
                [pip_bin, "install", "--no-cache-dir", self.wheel_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=tmp_dir,
                env=clean_env_vars,
            )
            self.assertEqual(install_proc.returncode, 0, f"Wheel install failed: {install_proc.stderr}")
            self.assertTrue(os.path.exists(feimini_bin), "feimini binary was not installed to venv bin")

            # 2. 从临时工作目录运行，完全脱离源码目录且清空 PYTHONPATH
            v_proc = subprocess.run([feimini_bin, "--version"], stdout=subprocess.PIPE, text=True, cwd=tmp_dir, env=clean_env_vars)
            self.assertEqual(v_proc.returncode, 0)
            self.assertIn("feimini", v_proc.stdout)

            # 测试 feimini --help
            h_proc = subprocess.run([feimini_bin, "--help"], stdout=subprocess.PIPE, text=True, cwd=tmp_dir, env=clean_env_vars)
            self.assertEqual(h_proc.returncode, 0)
            self.assertIn("feimini", h_proc.stdout)

            # 3. 测试在外部目录卸载
            uninst_proc = subprocess.run([pip_bin, "uninstall", "-y", "feimini"], cwd=tmp_dir, env=clean_env_vars, check=True)
            self.assertEqual(uninst_proc.returncode, 0)
            self.assertFalse(os.path.exists(feimini_bin))

            # 4. 从 sdist 重新安装
            sdist_proc = subprocess.run([pip_bin, "install", "--no-cache-dir", self.sdist_path], cwd=tmp_dir, env=clean_env_vars, check=True)
            self.assertEqual(sdist_proc.returncode, 0)
            self.assertTrue(os.path.exists(feimini_bin))


if __name__ == "__main__":
    unittest.main()
