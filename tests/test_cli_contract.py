import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cli import render
from cli.session import append_run, load_session, save_session
from core.executor import Executor, Planner
from core.resource_checker import ResourceChecker


ROOT = Path(__file__).resolve().parents[1]
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")


def strip_ansi(text):
    return ANSI_RE.sub("", text)


class CliContractTest(unittest.TestCase):
    def test_cli_main_is_only_entry(self):
        self.assertTrue((ROOT / "cli" / "main.py").exists())
        self.assertFalse((ROOT / "cli.py").exists())

    def test_frozen_intent_and_signal_fields_render(self):
        planning = Planner().plan("周末带娃出去", "family")
        s1 = render.render_intent(planning.intent, planning.scenario_template, planning, "verbose")
        self.assertIn("意图解析：周末带娃出去", s1)
        self.assertIn("场景：family", s1)
        self.assertIn("候选方案数：8", s1)

        signals = Executor().emit_signals(Executor().feedback_for("family"), None)
        flywheel = render.render_flywheel_emit(signals, "verbose")
        self.assertIn("用户偏好变化", flywheel)
        self.assertIn("最后更新", flywheel)

    def test_real_resource_checker_triggers_fallback(self):
        planning = Planner().plan("周末带娃出去", "family")
        result = ResourceChecker().check_plan(planning.chosen_plan)
        self.assertIsNotNone(result.fallback_event)
        self.assertIn("M102", result.fallback_event.reason)

    def test_session_persists_frozen_record_and_transcript(self):
        planning = Planner().plan("周末带娃出去", "family")
        feedback = Executor().feedback_for("family")
        signals = Executor().emit_signals(feedback, None)
        record = Executor().build_run_record(planning, planning.chosen_plan, feedback, False, signals, True)
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp) / "session.json"
            runs_dir = Path(tmp) / "runs"
            session = load_session(session_path)
            append_run(session, record, {"hello": "world"}, runs_dir)
            save_session(session, session_path)
            loaded = load_session(session_path)
            transcript = json.loads((runs_dir / f"{record.id}.json").read_text(encoding="utf-8"))
        self.assertEqual(
            set(loaded["runs"][0]),
            {
                "id",
                "ts",
                "intent",
                "chosen_plan_id",
                "feedback",
                "replanned",
                "signals_emitted",
                "fallback_triggered",
            },
        )
        self.assertEqual(transcript["hello"], "world")

    def test_cli_plan_verbose_runs_s1_to_s5(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "cli" / "main.py"), "plan", "周末带娃出去", "--verbose"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        stdout = strip_ansi(proc.stdout)
        self.assertIn("S1", proc.stdout)
        self.assertIn("S5", proc.stdout)
        self.assertIn("资源校验触发兜底", stdout)
        self.assertIn("兜底编号", stdout)

    def test_step3_replan_command(self):
        subprocess.run(
            [sys.executable, str(ROOT / "cli" / "main.py"), "plan", "weekend family route"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        proc = subprocess.run(
            [sys.executable, str(ROOT / "cli" / "main.py"), "replan", "please make dinner lighter"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        stdout = strip_ansi(proc.stdout)
        self.assertIn("新方案：plan_A_fallback_feedback", stdout)
        self.assertIn("继续锁定：出发时间, 书店活动, 路线方向", stdout)
        self.assertIn("新的可调整项：按反馈调整的餐厅, 到达缓冲", stdout)

    def test_step3_history_command(self):
        subprocess.run(
            [sys.executable, str(ROOT / "cli" / "main.py"), "plan", "history seed"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        history = subprocess.run(
            [sys.executable, str(ROOT / "cli" / "main.py"), "history", "--verbose"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("历史记录", history.stdout)
        self.assertIn("兜底=True", history.stdout)

    def test_step3_reflect_command(self):
        subprocess.run(
            [sys.executable, str(ROOT / "cli" / "main.py"), "plan", "reflect seed"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        reflect = subprocess.run(
            [sys.executable, str(ROOT / "cli" / "main.py"), "reflect", "--verbose"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("反思信息", reflect.stdout)
        self.assertIn("是否发出信号", reflect.stdout)

    def test_step3_profile_show_command(self):
        subprocess.run(
            [
                sys.executable,
                str(ROOT / "cli" / "main.py"),
                "profile",
                "edit",
                "--user-pref-delta",
                "show seed preference",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        show = subprocess.run(
            [sys.executable, str(ROOT / "cli" / "main.py"), "profile", "show"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("偏好画像", show.stdout)
        self.assertIn("用户偏好变化", show.stdout)

    def test_step3_profile_edit_command(self):
        edit = subprocess.run(
            [
                sys.executable,
                str(ROOT / "cli" / "main.py"),
                "profile",
                "edit",
                "--user-pref-delta",
                "prefer quiet seats",
                "--scenario-override",
                "avoid_late_dinner=true",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertIn("偏好画像已更新。", edit.stdout)
        self.assertIn("prefer quiet seats", edit.stdout)
        self.assertIn("avoid_late_dinner", edit.stdout)

    def test_step3_demo_command(self):
        for scenario in ["family", "friend", "date", "solo"]:
            proc = subprocess.run(
                [sys.executable, str(ROOT / "cli" / "main.py"), "demo", scenario],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=True,
            )
            self.assertIn("方案A", proc.stdout)
            self.assertIn("方案B", proc.stdout)


if __name__ == "__main__":
    unittest.main()
