import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "cli" / "main.py"


def run_cli(env, *args):
    proc = subprocess.run(
        [sys.executable, str(CLI), *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr)
        raise SystemExit(proc.returncode)
    return proc.stdout


def plan_title(output):
    for line in output.splitlines():
        if line.startswith("Plan plan_A:"):
            return line
    return ""


def main():
    with tempfile.TemporaryDirectory(prefix="meituan_flywheel_") as tmp:
        learned_path = Path(tmp) / "learned" / "learned_signals.json"
        env = os.environ.copy()
        env["MEITUAN_SESSION_PATH"] = str(Path(tmp) / "session.json")
        env["MEITUAN_RUNS_DIR"] = str(Path(tmp) / "runs")
        env["MEITUAN_LEARNED_PATH"] = str(learned_path)

        first = run_cli(env, "plan", "weekend family energy release", "--scenario", "family", "--verbose")
        run_cli(env, "replan", "prefer quieter dinner and less walking")
        if not learned_path.exists():
            raise AssertionError("learned signals file was not created")
        learned = json.loads(learned_path.read_text(encoding="utf-8"))

        second = run_cli(env, "plan", "weekend family energy release", "--scenario", "family", "--verbose")
        if "based on history adjustment" not in second:
            raise AssertionError("second session did not inject LearnedSignals")
        first_title = plan_title(first)
        second_title = plan_title(second)
        if first_title == second_title:
            raise AssertionError("second session plan did not differ from first session")

        print("First session plan:")
        print(first_title)
        print("\nLearnedSignals file:")
        print(f"user_pref_deltas={learned.get('user_pref_deltas', [])}")
        print(f"scenario_overrides={learned.get('scenario_overrides', {})}")
        print("\nSecond session plan:")
        print(second_title)
        print("\nInjection evidence:")
        for line in second.splitlines():
            if "based on history adjustment" in line or line.startswith("Injected signals:"):
                print(line)
        print("\nTwo-session flywheel passed.")


if __name__ == "__main__":
    main()
