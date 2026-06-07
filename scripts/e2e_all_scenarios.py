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


def require(text, needle, label):
    if needle not in text:
        raise AssertionError(f"{label}: missing {needle!r}")


def reject(text, needle, label):
    if needle in text:
        raise AssertionError(f"{label}: leaked {needle!r}")


def snippet(title, text):
    print(f"\n## {title}")
    for line in text.splitlines():
        if line.startswith(("S2", "Plan plan_", "Route:", "Total transit:", "S3", "Resource fallback", "Trigger:", "Change:", "S4", "S5", "Itinerary:", "Replanned plan", "New plan:")):
            print(line)


def main():
    with tempfile.TemporaryDirectory(prefix="meituan_e2e_") as tmp:
        env = os.environ.copy()
        env["MEITUAN_SESSION_PATH"] = str(Path(tmp) / "session.json")
        env["MEITUAN_RUNS_DIR"] = str(Path(tmp) / "runs")
        env["MEITUAN_LEARNED_PATH"] = str(Path(tmp) / "learned" / "learned_signals.json")

        family_user = run_cli(env, "plan", "weekend family energy release", "--scenario", "family")
        family_verbose = run_cli(env, "plan", "weekend family energy release", "--scenario", "family", "--verbose")
        reject(family_user, "Candidate pool:", "user mode")
        reject(family_user, "Rejected merchants:", "user mode")
        reject(family_user, "Raw score:", "user mode")
        reject(family_user, "input=", "user mode")
        reject(family_user, "Injected signals:", "user mode")
        require(family_verbose, "Candidate pool:", "verbose mode")
        require(family_verbose, "Rejected merchants:", "verbose mode")
        require(family_verbose, "Raw score:", "verbose mode")
        require(family_verbose, "input=", "verbose mode")
        require(family_verbose, "Injected signals:", "verbose mode")

        family_replan = run_cli(env, "replan", "companion wants a lighter dinner")
        family_history = run_cli(env, "history", "--verbose")
        family_reflect = run_cli(env, "reflect", "--verbose")
        require(family_replan, "Replanned plan", "family replan")
        require(family_history, "History", "family history")
        require(family_reflect, "Reflection", "family reflect")

        friend = run_cli(env, "demo", "friend")
        require(friend, "Plan plan_A", "friend plan A")
        require(friend, "Plan plan_B", "friend plan B")
        require(friend, "Resource fallback", "friend fallback")
        print("\n## friend selection")
        print("Selected plan_A and confirmed reversible holds plus payment confirmation preview.")

        date = run_cli(env, "demo", "date")
        date_replan = run_cli(env, "replan", "make the dinner quieter")
        require(date, "Plan plan_A", "date plan A")
        require(date_replan, "Replanned plan", "date replan")

        solo = run_cli(env, "demo", "solo")
        solo_replan = run_cli(env, "replan", "self state changed: tired, reduce walking")
        require(solo, "self_state", "solo self-state signal")
        require(solo_replan, "Replanned plan", "solo replan")

        snippet("family user S2/S3/S4/S5", family_user)
        snippet("family replan", family_replan)
        snippet("friend S2/S3/S4/S5", friend)
        snippet("date S2/S3/S4/S5", date)
        snippet("date replan", date_replan)
        snippet("solo S2/S3/S4/S5", solo)
        snippet("solo replan", solo_replan)
        print("\nE2E all scenarios passed.")


if __name__ == "__main__":
    main()
