import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cli(env, *args):
    return subprocess.run(
        [sys.executable, str(ROOT / "cli" / "main.py"), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    ).stdout


class Step4E2ETest(unittest.TestCase):
    def test_e2e_all_scenarios_cli_chinese(self):
        with tempfile.TemporaryDirectory(prefix="meituan_e2e_") as tmp:
            env = os.environ.copy()
            env["MEITUAN_SESSION_PATH"] = str(Path(tmp) / "session.json")
            env["MEITUAN_RUNS_DIR"] = str(Path(tmp) / "runs")
            env["MEITUAN_LEARNED_PATH"] = str(Path(tmp) / "learned" / "learned_signals.json")

            family = run_cli(env, "plan", "weekend family energy release", "--scenario", "family")
            self.assertIn("S1", family)
            self.assertIn("安排依据", family)
            self.assertIn("安心保障", family)
            self.assertIn("退改说明", family)
            self.assertIn("已确定 / 可调整", family)
            self.assertIn("方案A", family)
            self.assertIn("资源校验触发兜底", family)
            self.assertIn("行程已生成", family)
            self.assertIn("搞定了", family)

            replan = run_cli(env, "replan", "companion wants a lighter dinner")
            history = run_cli(env, "history", "--verbose")
            reflect = run_cli(env, "reflect", "--verbose")
            self.assertIn("已更新方案", replan)
            self.assertIn("历史记录", history)
            self.assertIn("反思信息", reflect)

            for scenario in ["friend", "date", "solo"]:
                output = run_cli(env, "demo", scenario)
                self.assertIn("方案A", output)
                self.assertIn("方案B", output)
                self.assertIn("资源校验触发兜底", output)

    def test_two_session_flywheel_cli_chinese(self):
        with tempfile.TemporaryDirectory(prefix="meituan_flywheel_") as tmp:
            env = os.environ.copy()
            env["MEITUAN_SESSION_PATH"] = str(Path(tmp) / "session.json")
            env["MEITUAN_RUNS_DIR"] = str(Path(tmp) / "runs")
            env["MEITUAN_LEARNED_PATH"] = str(Path(tmp) / "learned" / "learned_signals.json")

            first = run_cli(env, "plan", "weekend family energy release", "--scenario", "family", "--verbose")
            run_cli(env, "replan", "prefer quieter dinner and less walking")
            second = run_cli(env, "plan", "weekend family energy release", "--scenario", "family", "--verbose")

            self.assertIn("方案A", first)
            self.assertIn("方案A", second)
            self.assertIn("注入信号", second)
            self.assertIn("基于历史记录调整", second)
            self.assertIn("用户偏好变化", second)


if __name__ == "__main__":
    unittest.main()
