import argparse
import dataclasses
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cli.render import (
    render_exec_preview,
    render_exec_progress,
    render_flywheel_emit,
    render_history,
    render_intent,
    render_itinerary,
    render_plans,
    render_profile,
    render_reflection,
    render_replanned_plan,
    render_replan_diff,
    render_resource_fallback,
    render_resource_actions,
    render_run_detail,
    render_share,
    soft_purple,
)
from cli.session import (
    append_run,
    edit_profile,
    find_run_record,
    latest_run_record,
    list_run_records,
    load_session,
    load_transcript,
    save_session,
)
from core.executor import Executor, Feedback, LearnedSignals, Planner, Replanner, planner_output_from_dict, plan_from_dict
from core.itinerary_generator import ItineraryGenerator
from core.resource_checker import ResourceChecker


def _print_blocks(blocks):
    print("\n\n".join(block for block in blocks if block))


def _execute_flow(goal, scenario):
    session = load_session()
    planner = Planner()
    resource_checker = ResourceChecker()
    replanner = Replanner()
    executor = Executor()
    itinerary_generator = ItineraryGenerator()

    planning = planner.plan(goal, scenario)
    _apply_learned_profile(planning, session.get("profile", {}))
    resource_result = resource_checker.check_plan(planning.chosen_plan)
    chosen_plan = planning.chosen_plan
    replanned = False
    if resource_result.fallback_event:
        chosen_plan = replanner.replan_for_fallback(chosen_plan, resource_result.fallback_event)
        replanned = True

    execution = executor.execute(chosen_plan)
    execution = _attach_resource_actions(execution, resource_result)
    resource_checker.confirm_execution(execution)
    itinerary = itinerary_generator.generate(chosen_plan, scenario)
    feedback = Feedback("", "plan")
    replan_diff = None
    signals = _plan_signals(resource_result.fallback_event)
    run_record = executor.build_run_record(
        planning=planning,
        chosen_plan=chosen_plan,
        feedback=feedback,
        replanned=replanned,
        signals=signals,
        fallback_triggered=bool(resource_result.fallback_event),
    )
    transcript = {
        "planning": planning.to_dict(),
        "chosen_plan": dataclasses.asdict(chosen_plan),
        "resource_result": resource_result.to_dict(),
        "execution": execution.to_dict(),
        "feedback_replan": None,
        "itinerary": itinerary.to_dict(),
        "signals": signals.to_dict(),
    }
    return planning, chosen_plan, execution, resource_result, feedback, replan_diff, itinerary, signals, run_record, transcript


def _plan_signals(fallback_event):
    merchant_signals = []
    if fallback_event:
        merchant_signals.append(f"{fallback_event.from_item} unavailable: {fallback_event.reason}")
    return LearnedSignals(
        user_pref_deltas=[],
        merchant_signals=merchant_signals or ["no merchant change"],
        scenario_overrides={"prefer_refundable": True, "avoid_crowded_dinner": bool(fallback_event)},
        last_updated=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def _apply_learned_profile(planning, profile):
    deltas = profile.get("user_pref_deltas", [])
    overrides = profile.get("scenario_overrides", {})
    if not deltas and not overrides:
        return
    planning.injected_signals.append(
        f"基于历史记录调整：偏好={len(deltas)}，场景覆盖={len(overrides)}"
    )
    adjusted_plans = []
    for index, plan in enumerate(planning.plans):
        if index == 0:
            adjusted = dataclasses.replace(
                plan,
                title=f"{plan.title}（已结合学习偏好）",
                flexible_items=list(dict.fromkeys(plan.flexible_items + ["学习偏好缓冲"])),
                score=round(plan.score + 0.02, 2),
            )
        else:
            adjusted = plan
        adjusted_plans.append(adjusted)
    planning.plans = adjusted_plans
    planning.chosen_plan = adjusted_plans[0]


def _attach_resource_actions(execution, resource_result):
    reversible = list(dict.fromkeys(execution.reversible_actions + resource_result.reversible_actions))
    payments = list(dict.fromkeys(execution.payment_confirmations + resource_result.payment_confirmations))
    return dataclasses.replace(execution, reversible_actions=reversible, payment_confirmations=payments)


def _render_five_acts(flow, mode):
    planning, _chosen_plan, execution, resource_result, feedback, replan_diff, itinerary, signals, _record, _transcript = flow
    return [
        soft_purple("S1") + "\n" + render_intent(planning.intent, planning.scenario_template, planning, mode),
        soft_purple("S2") + "\n" + render_plans(planning.plans, mode),
        soft_purple("S3")
        + "\n"
        + "\n\n".join(
            [
                render_exec_preview(execution, mode),
                render_exec_progress(execution, mode),
                render_resource_actions(resource_result, mode),
                render_resource_fallback(resource_result.fallback_event, mode),
            ]
        ),
        soft_purple("S5") + "\n" + "\n\n".join([render_itinerary(itinerary, mode), render_flywheel_emit(signals, mode)]),
    ]


def cmd_plan(args):
    session = load_session()
    flow = _execute_flow(args.goal, args.scenario)
    append_run(session, flow[8], flow[9])
    save_session(session)
    blocks = _render_five_acts(flow, "verbose" if args.verbose else "user")
    blocks.append("转发文案\n" + render_share(flow[1]))
    _print_blocks(blocks)
    return 0


def cmd_replan(args):
    session = load_session()
    latest = latest_run_record(session)
    if not latest:
        print("暂无可调整的方案，请先运行 plan。")
        return 1
    transcript = load_transcript(latest["id"])
    if not transcript:
        print(f"未找到会话记录：{latest['id']}。")
        return 1

    planner_output = planner_output_from_dict(transcript["planning"])
    old_plan = plan_from_dict(transcript.get("chosen_plan") or transcript["planning"]["chosen_plan"])
    scenario = planner_output.scenario_template.id
    executor = Executor()
    replanner = Replanner()
    resource_checker = ResourceChecker()
    itinerary_generator = ItineraryGenerator()

    feedback = Feedback(args.feedback, "self_state" if scenario == "solo" else "user")
    diff = replanner.replan_for_feedback(old_plan, feedback)
    new_plan = replanner.replan_plan_for_feedback(old_plan, feedback)
    execution = executor.execute(new_plan)
    resource_result = resource_checker.check_plan(new_plan)
    execution = _attach_resource_actions(execution, resource_result)
    resource_checker.confirm_execution(execution)
    itinerary = itinerary_generator.generate(new_plan, scenario)
    signals = executor.emit_signals(feedback, resource_result.fallback_event)
    run_record = executor.build_run_record(
        planning=planner_output,
        chosen_plan=new_plan,
        feedback=feedback,
        replanned=True,
        signals=signals,
        fallback_triggered=bool(resource_result.fallback_event),
    )
    new_transcript = {
        "previous_run_id": latest["id"],
        "planning": planner_output.to_dict(),
        "chosen_plan": dataclasses.asdict(new_plan),
        "resource_result": resource_result.to_dict(),
        "execution": execution.to_dict(),
        "feedback_replan": diff.to_dict(),
        "itinerary": itinerary.to_dict(),
        "signals": signals.to_dict(),
    }
    append_run(session, run_record, new_transcript)
    save_session(session)
    _print_blocks(
        [
            soft_purple("S4") + "\n" + render_replan_diff(feedback, diff, "user"),
            render_replanned_plan(old_plan.id, new_plan, diff, "user"),
            soft_purple("S5") + "\n" + render_itinerary(itinerary, "user"),
            "转发文案\n" + render_share(new_plan),
        ]
    )
    return 0


def cmd_demo(args):
    goals = {
        "family": "周末带娃放电",
        "friend": "和闺蜜下午茶",
        "date": "约会夜",
        "solo": "一个人看书喝咖啡",
    }
    session = load_session()
    flow = _execute_flow(goals[args.scenario], args.scenario)
    append_run(session, flow[8], flow[9])
    save_session(session)
    _print_blocks(_render_five_acts(flow, "user"))
    return 0


def cmd_reflect(args):
    session = load_session()
    run = find_run_record(session, args.id) if args.id else latest_run_record(session)
    transcript = load_transcript(run["id"]) if run else None
    _print_blocks([render_reflection(run, transcript, session.get("profile", {}), "verbose" if args.verbose else "user")])
    return 0


def cmd_history(args):
    session = load_session()
    if args.id:
        run = find_run_record(session, args.id)
        if not run:
            print(f"未找到会话：{args.id}")
            return 1
        _print_blocks([render_run_detail(run, load_transcript(args.id), "verbose" if args.verbose else "user")])
        return 0
    _print_blocks([render_history(list_run_records(session), "verbose" if args.verbose else "user")])
    return 0


def cmd_profile(args):
    session = load_session()
    if args.profile_cmd == "show":
        _print_blocks([render_profile(session.get("profile", {}))])
        return 0
    try:
        edit_profile(session, args.user_pref_delta, args.scenario_override)
    except ValueError as exc:
        print(str(exc))
        return 1
    save_session(session)
    _print_blocks(["偏好画像已更新。", render_profile(session.get("profile", {}))])
    return 0


def build_parser():
    parser = argparse.ArgumentParser(prog="python cli/main.py", description="美团安排命令行")
    subparsers = parser.add_subparsers(required=True)

    plan = subparsers.add_parser("plan", help="输入一句话，生成完整安排方案（S1-S5）", description="输入一句话，生成完整安排方案（S1-S5）")
    plan.add_argument("goal")
    plan.add_argument("--verbose", action="store_true", help="显示详细调试信息")
    plan.add_argument("--scenario", choices=["family", "friend", "date", "solo"], default="family", help="指定场景类型")
    plan.set_defaults(func=cmd_plan)

    replan = subparsers.add_parser("replan", help="根据反馈局部调整最近一次方案", description="根据反馈局部调整最近一次方案")
    replan.add_argument("feedback", help="用于局部调整的反馈文本")
    replan.set_defaults(func=cmd_replan)

    reflect = subparsers.add_parser("reflect", help="查看指定会话的反思信息", description="查看指定会话的反思信息")
    reflect.add_argument("--id", help="会话 ID；默认查看最近一次")
    reflect.add_argument("--verbose", action="store_true", help="显示详细调试信息")
    reflect.set_defaults(func=cmd_reflect)

    history = subparsers.add_parser("history", help="列出历史记录或查看某次详情", description="列出历史记录或查看某次详情")
    history.add_argument("--id", help="查看指定会话详情")
    history.add_argument("--verbose", action="store_true", help="显示详细调试信息")
    history.set_defaults(func=cmd_history)

    profile = subparsers.add_parser("profile", help="查看或编辑已学习的偏好", description="查看或编辑已学习的偏好")
    profile.add_argument("profile_cmd", choices=["show", "edit"])
    profile.add_argument("--user-pref-delta", help="追加一条用户偏好变化")
    profile.add_argument("--scenario-override", help="设置一条场景覆盖，格式为 key=value")
    profile.set_defaults(func=cmd_profile)

    demo = subparsers.add_parser("demo", help="运行预设场景（family/friend/date/solo）", description="运行预设场景（family/friend/date/solo）")
    demo.add_argument("scenario", choices=["family", "friend", "date", "solo"])
    demo.set_defaults(func=cmd_demo)
    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
