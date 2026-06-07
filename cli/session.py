import dataclasses
import json
import os
import time
from pathlib import Path


SESSION_PATH = Path(os.environ.get("MEITUAN_SESSION_PATH", str(Path("var") / "session.json")))
RUNS_DIR = Path(os.environ.get("MEITUAN_RUNS_DIR", str(Path("data") / "runs")))
LEARNED_PATH = Path(os.environ.get("MEITUAN_LEARNED_PATH", str(Path("data") / "learned" / "learned_signals.json")))


def _default_session():
    return {
        "profile": _default_profile(),
        "runs": [],
    }


def _default_profile():
    return {
        "user_pref_deltas": [],
        "merchant_signals": [],
        "scenario_overrides": {},
        "last_updated": "",
    }


def load_session(path=SESSION_PATH):
    if not path.exists():
        return _default_session()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    data["profile"] = _coerce_profile(data.get("profile", {}))
    learned = load_learned_signals()
    if learned:
        data["profile"] = _merge_profiles(data["profile"], learned)
    data.setdefault("runs", [])
    data["runs"] = [_coerce_run_record(run) for run in data["runs"]]
    return data


def save_session(session, path=SESSION_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(session, handle, ensure_ascii=False, indent=2)


def append_run(session, run_record, transcript, runs_dir=RUNS_DIR):
    record = _frozen_run_record(run_record)
    runs_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = runs_dir / f"{record['id']}.json"
    with transcript_path.open("w", encoding="utf-8") as handle:
        json.dump(transcript, handle, ensure_ascii=False, indent=2)
    session.setdefault("runs", []).append(record)
    if transcript.get("signals"):
        merge_profile_signals(session, transcript["signals"])


def list_run_records(session):
    return session.get("runs", [])


def latest_run_record(session):
    runs = list_run_records(session)
    return runs[-1] if runs else None


def find_run_record(session, run_id):
    for run in list_run_records(session):
        if run["id"] == run_id:
            return run
    return None


def load_transcript(run_id, runs_dir=RUNS_DIR):
    path = runs_dir / f"{run_id}.json"
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_learned_signals(path=LEARNED_PATH):
    if not path.exists():
        return None
    with path.open("r", encoding="utf-8") as handle:
        return _coerce_profile(json.load(handle))


def merge_profile_signals(session, signals):
    profile = session.setdefault("profile", _default_profile())
    for delta in signals.get("user_pref_deltas", []):
        if delta not in profile["user_pref_deltas"]:
            profile["user_pref_deltas"].append(delta)
    for signal in signals.get("merchant_signals", []):
        if signal not in profile["merchant_signals"]:
            profile["merchant_signals"].append(signal)
    profile["scenario_overrides"].update(signals.get("scenario_overrides", {}))
    profile["last_updated"] = signals.get("last_updated") or _now()
    save_learned_signals(profile)


def edit_profile(session, user_pref_delta=None, scenario_override=None):
    profile = session.setdefault("profile", _default_profile())
    if user_pref_delta:
        profile["user_pref_deltas"].append(user_pref_delta)
    if scenario_override:
        key, value = _parse_override(scenario_override)
        profile["scenario_overrides"][key] = value
    profile["last_updated"] = _now()
    save_learned_signals(profile)


def save_learned_signals(profile, path=LEARNED_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(_coerce_profile(profile), handle, ensure_ascii=False, indent=2)


def _frozen_run_record(run_record):
    payload = dataclasses.asdict(run_record) if dataclasses.is_dataclass(run_record) else dict(run_record)
    allowed = {
        "id",
        "ts",
        "intent",
        "chosen_plan_id",
        "feedback",
        "replanned",
        "signals_emitted",
        "fallback_triggered",
    }
    return {key: payload[key] for key in allowed}


def _coerce_run_record(run):
    allowed_defaults = {
        "id": run.get("id", "legacy"),
        "ts": run.get("ts", ""),
        "intent": run.get("intent", {}),
        "chosen_plan_id": run.get("chosen_plan_id", ""),
        "feedback": run.get("feedback", {}),
        "replanned": bool(run.get("replanned", False)),
        "signals_emitted": bool(run.get("signals_emitted", False)),
        "fallback_triggered": bool(run.get("fallback_triggered", False)),
    }
    return allowed_defaults


def _coerce_profile(profile):
    default = _default_profile()
    if "budget_policy" in profile or "default_scenario" in profile:
        return default
    default.update({key: profile.get(key, default[key]) for key in default})
    return default


def _merge_profiles(base, learned):
    merged = _coerce_profile(base)
    for key in ["user_pref_deltas", "merchant_signals"]:
        for item in learned.get(key, []):
            if item not in merged[key]:
                merged[key].append(item)
    merged["scenario_overrides"].update(learned.get("scenario_overrides", {}))
    merged["last_updated"] = learned.get("last_updated") or merged["last_updated"]
    return merged


def _parse_override(value):
    if "=" not in value:
        raise ValueError("scenario override must use key=value")
    key, raw = value.split("=", 1)
    lowered = raw.lower()
    if lowered in {"true", "false"}:
        parsed = lowered == "true"
    else:
        parsed = raw
    return key, parsed


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")
