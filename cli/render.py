def yellow(text):
    return f"\033[33m{text}\033[0m"


def soft_purple(text):
    return f"\033[95m{text}\033[0m"


def _money(value):
    return f"CNY {value:.0f}"


def _constraint_reasons(plan):
    return [_zh_text(constraint.reason) for constraint in plan.constraints]


def _zh_text(value):
    text = str(value)
    replacements = {
        "easy and predictable": "轻松、可预期",
        "nearby indoor-first route": "就近，优先室内路线",
        "low": "低",
        "moderate": "适中",
        "not too spicy": "不要太辣",
        "half day": "半天",
        "one adult and one child": "一位大人和一位孩子",
        "one person": "一个人",
        "two people": "两个人",
        "rain": "下雨",
        "crowding": "拥挤",
        "family outing": "亲子出行",
        "friends meetup": "朋友聚会",
        "date plan": "约会安排",
        "solo reset": "独处放松",
        "route stays under 60 minutes": "路上总耗时控制在 60 分钟内",
        "new paid deltas need confirmation": "新增付费差额需要确认",
        "indoor backup is available under rain": "下雨时有室内备选",
        "short transfer": "短距离换乘",
        "payment confirmation": "付款确认",
        "weather backup": "天气备选",
        "prefer_refundable": "优先可退改",
        "cap_route_minutes": "限制路上耗时",
        "keep_backup": "保留备选",
        "repo:weather=rain": "仓库信号：天气=下雨",
        "repo:merchant:M102 crowd risk": "仓库信号：商户 M102 有拥挤风险",
        "risk": "风险",
        "distance": "距离",
        "price": "价格",
        "parent-child cafe": "亲子咖啡馆",
        "quiet cafe": "安静咖啡馆",
        "bookstore activity": "书店活动",
        "hotpot dinner": "火锅晚餐",
        "Cantonese claypot dinner": "粤式煲仔饭",
        "mall activity": "商场活动",
        "noodle dinner": "面馆晚餐",
        "tea room": "茶室",
        "nearby noodle dinner": "附近面馆",
        "low-risk route with indoor backup": "低风险室内备选路线",
        "low-risk route with Cantonese claypot dinner fallback": "低风险粤式煲仔饭兜底路线",
        "cheaper route with longer transfer": "更省钱但换乘更久的路线",
        "start time": "出发时间",
        "route direction": "路线方向",
        "dinner merchant": "晚餐商户",
        "delivery dessert": "配送甜品",
        "budget cap": "预算上限",
        "activity merchant": "活动商户",
        "ride mode": "出行方式",
        "feedback-adjusted meal": "按反馈调整的餐厅",
        "arrival buffer": "到达缓冲",
        "M201 too crowded": "M201 太拥挤",
        "M305 no refund window": "M305 无可退窗口",
        "M118 expired coupon": "M118 团购券过期",
        "reserve": "已预约",
        "hold bookstore seat": "保留书店座位",
        "queue ticket": "排队取号",
        "position": "排位",
        "wait": "等位",
        "cancel surprise delivery": "取消惊喜配送",
        "groupbuy": "团购券",
        "claypot dinner coupon": "煲仔饭套餐券",
        "family set coupon": "家庭套餐券",
        "surprise delivery": "惊喜配送",
        "cake": "蛋糕",
        "open_hours=pass": "营业时间=通过",
        "inventory=fail": "库存=失败",
        "inventory=pass": "库存=通过",
        "crowd=fail": "拥挤=失败",
        "crowd=pass": "拥挤=通过",
        "reserve=fail": "预约=失败",
        "reserve=pass": "预约=通过",
        "groupbuy=pass": "团购券=通过",
        "groupbuy=fail": "团购券=失败",
        "queue=number_taken": "排队=已取号",
        "weather=rain": "天气=下雨",
        "use 35min queue window for nearby activity": "利用 35 分钟等位窗口完成附近活动",
        "M102 key resource unavailable during real repository check": "M102 关键资源在实时校验中不可用",
        "hotpot dinner at M102": "M102 火锅晚餐",
        "Cantonese claypot dinner at M218": "M218 粤式煲仔饭",
        "Grandparent prefers less spicy dinner.": "长辈希望晚餐清淡一点。",
        "companion preference lowers spice risk while preserving route": "同行人偏好降低了辣味风险，同时保留原路线",
        "adjusted by feedback": "（已按反馈调整）",
        "please make dinner lighter": "请把晚餐调清淡一点",
        "fee 12": "配送费 12",
        "companion": "同行人",
        "adult": "大人",
        "child": "孩子",
        "solo": "本人",
        "leave with buffer": "预留缓冲后出发",
        "arrive directly at first stop": "直接到首站集合",
        "join bookstore activity": "加入书店活动",
        "ride home together": "一起回家",
        "umbrella": "雨伞",
        "reservation QR": "预约二维码",
        "refundable groupbuy confirmation": "可退团购确认",
        "no merchant change": "无商户变更",
        "unavailable": "不可用",
    }
    for source in sorted(replacements, key=len, reverse=True):
        text = text.replace(source, replacements[source])
    return text


def _plan_label(plan_id):
    suffix = str(plan_id).split("_")[-1]
    if suffix in {"A", "B"}:
        return f"方案{suffix}"
    return f"方案{plan_id}"


def _touchpoint_highlight(text):
    return str(text)


def _locked_items(items):
    plain_items = [_zh_text(item) for item in items]
    return ", ".join(plain_items)


def _zh_join(items):
    return _zh_text(", ".join(items))


def render_share(plan):
    if not plan.slots:
        return "搞定了，方案先留个可调版本，你们看看～"
    first = plan.slots[0]
    last = plan.slots[-1]
    start = first.window.split("-", 1)[0] if first.window else "约定时间"
    end = last.window.split("-", 1)[-1] if last.window and "-" in last.window else "结束时间再看现场"
    stops = "".join(f"，再去{_zh_text(slot.name)}" for slot in plan.slots[1:-1])
    return f"搞定了，{start}出发，先去{_zh_text(first.name)}{stops}，再去{_zh_text(last.name)}。预计{end}结束。随时可调，你们看看～"


def render_intent(intent, scenario_template, planner_output, mode):
    reasons = _constraint_reasons(planner_output.chosen_plan)
    if mode != "verbose":
        return "\n".join(
            [
                "安排依据",
                yellow(f"意图解析：{intent.raw_goal}"),
                f"场景：{scenario_template.id}",
                f"氛围偏好：{_zh_text(intent.vibe)}",
                f"同行人：{_zh_text(intent.party)}",
                f"依据：{'; '.join(reasons)}",
                "安心保障",
                _touchpoint_highlight("可逆操作会和付款确认分开处理，临时变化可局部调整。"),
                "退改说明",
                _touchpoint_highlight("已预约、已取号、配送等可取消动作优先保留退改空间；资金项需单独确认。"),
                "已确定 / 可调整",
                f"已锁定：{_locked_items(planner_output.chosen_plan.locked_items)}",
                f"可调整：{_zh_join(planner_output.chosen_plan.flexible_items)}",
            ]
        )

    lines = [
        "安排依据",
        yellow(f"意图解析：{intent.raw_goal}"),
        f"场景：{scenario_template.id}",
        f"氛围偏好：{_zh_text(intent.vibe)}",
        f"地点偏好：{_zh_text(intent.setting)}",
        f"体力偏好：{_zh_text(intent.effort)}",
        f"预算偏好：{_zh_text(intent.spend)}",
        f"餐饮偏好：{_zh_text(intent.meal_focus)}",
        f"时长：{_zh_text(intent.duration_hint)}",
        f"同行人：{_zh_text(intent.party)}",
        f"安排依据：{'; '.join(reasons)}",
        "安心保障",
        _touchpoint_highlight("安心保障：可逆操作会和付款确认分开处理"),
        "退改说明",
        _touchpoint_highlight("已预约、已取号、配送中、可取消、可退、团购等触点会单独列出，资金项需确认。"),
        "已确定 / 可调整",
        f"已锁定：{_locked_items(planner_output.chosen_plan.locked_items)}",
        f"可调整：{_zh_join(planner_output.chosen_plan.flexible_items)}",
    ]
    if intent.sensitivities:
        lines.append(f"敏感因素：{_zh_join(intent.sensitivities)}")
    lines.extend(
        [
            f"模板标签：{_zh_text(scenario_template.label)}",
            f"候选方案数：{planner_output.candidate_count}",
            f"约束项：{_zh_join(planner_output.constraint_labels)}",
            f"命中规则：{_zh_join(intent.fired_rules)}",
            f"注入信号：{_zh_join(planner_output.injected_signals)}",
            f"权重覆盖：{_zh_text(scenario_template.weight_overrides)}",
            f"风险补充：{_zh_join(scenario_template.risk_extras)}",
        ]
    )
    return "\n".join(lines)


def render_plans(plans, mode):
    lines = []
    for index, plan in enumerate(plans):
        title_line = f"{_plan_label(plan.id)}：{_zh_text(plan.title)}；路线：{' -> '.join(_zh_text(slot.name) for slot in plan.slots)}；总耗时：{plan.route_minutes} 分钟"
        lines.append(yellow(title_line) if index == 0 else title_line)
        lines.append(f"路线：{' -> '.join(_zh_text(slot.name) for slot in plan.slots)}")
        lines.append(f"总耗时：{plan.route_minutes} 分钟")
        lines.append(f"已锁定：{_locked_items(plan.locked_items)}")
        lines.append(f"可调整：{_zh_join(plan.flexible_items)}")
        if mode == "verbose":
            lines.append(f"原始评分：{plan.score}")
            lines.append(f"淘汰商户：{_zh_join(plan.rejected_merchants)}")
            for constraint in plan.constraints:
                lines.append(f"  约束 {constraint.id}：{_zh_text(constraint.reason)}")
            for slot in plan.slots:
                lines.append(f"  {slot.id} geo={slot.geo} window={slot.window}")
        lines.append("")
    return "\n".join(lines).strip()


def render_exec_preview(execution, mode):
    lines = [
        "执行状态",
        f"可逆动作：{_touchpoint_highlight(_zh_join(execution.reversible_actions))}",
        f"资金确认：{_touchpoint_highlight(_zh_join(execution.payment_confirmations))}",
    ]
    if mode == "verbose":
        lines.append(f"工具调用数：{len(execution.tool_calls)}")
    return "\n".join(lines)


def render_exec_progress(execution, mode):
    lines = ["工具进度"]
    for call in execution.tool_calls:
        lines.append(f"- {call.name}：{call.status}")
        if mode == "verbose":
            lines.append(f"  入参={call.tool_input}")
            lines.append(f"  出参={call.tool_output}")
    return "\n".join(lines)


def render_resource_fallback(fallback_event, mode):
    if not fallback_event:
        return "资源校验\n无需兜底。"
    lines = [
        "资源校验触发兜底",
        f"触发原因：{_zh_text(fallback_event.reason)}",
        f"影响时段：{fallback_event.affected_slot_id}",
        f"变更：{_zh_text(fallback_event.from_item)} -> {_zh_text(fallback_event.to_item)}",
        f"已锁定：{_locked_items(fallback_event.locked_items)}",
    ]
    lines[3] = yellow(lines[3])
    if fallback_event.money_delta:
        lines.append(f"费用差额需确认：{_money(fallback_event.money_delta)}")
    if mode == "verbose":
        lines.extend(
            [
                f"校验项：{_touchpoint_highlight(_zh_join(fallback_event.checks))}",
                f"兜底编号：{fallback_event.id}",
            ]
        )
    return "\n".join(lines)


def render_resource_actions(resource_result, mode):
    lines = []
    if resource_result.reversible_actions:
        lines.append(f"资源侧可逆动作：{_touchpoint_highlight(_zh_join(resource_result.reversible_actions))}")
    if resource_result.payment_confirmations:
        lines.append(f"资源侧资金确认：{_touchpoint_highlight(_zh_join(resource_result.payment_confirmations))}")
    if resource_result.slot_window_updates:
        for update in resource_result.slot_window_updates:
            lines.append(f"等位窗口：{update['slot_id']} {_zh_text(update['window'])}")
    if mode == "verbose":
        lines.append(f"资源校验项：{_touchpoint_highlight(_zh_join(resource_result.checks))}")
    return "\n".join(lines)


def render_replan_diff(feedback, replan, mode):
    title = "自身状态触发重规划" if feedback.source == "self_state" else "反馈触发重规划"
    lines = [
        title,
        f"反馈：{_zh_text(feedback.text)}",
        yellow(f"变更：{_zh_text(replan.from_item)} -> {_zh_text(replan.to_item)}"),
        f"已锁定：{_locked_items(replan.locked_items)}",
    ]
    if mode == "verbose":
        lines.extend(
            [
                f"反馈来源：{_zh_text(feedback.source)}",
                f"原因：{_zh_text(replan.reason)}",
                f"评分变化：{replan.score_delta:+.2f}",
            ]
        )
    return "\n".join(lines)


def render_itinerary(itinerary, mode):
    lines = [yellow(f"行程已生成：{_zh_text(itinerary.title)}")]
    for member, events in itinerary.member_timelines.items():
        lines.append(_zh_text(member))
        for event in events:
            lines.append(f"- {event['time']} {_zh_text(event['text'])}")
    lines.append(f"准备事项：{_touchpoint_highlight(_zh_join(itinerary.prep_list))}")
    if mode == "verbose":
        lines.append(f"来源方案：{itinerary.plan_id}")
    return "\n".join(lines)


def render_flywheel_emit(learned_signals, mode):
    lines = [
        "学习回路",
        f"用户偏好变化：{_zh_join(learned_signals.user_pref_deltas)}",
        f"商户信号：{_zh_text(', '.join(learned_signals.merchant_signals))}",
    ]
    if mode == "verbose":
        lines.extend(
            [
                f"场景覆盖：{_zh_text(learned_signals.scenario_overrides)}",
                f"最后更新：{learned_signals.last_updated}",
            ]
        )
    return "\n".join(lines)


def render_history(runs, mode):
    if not runs:
        return "暂无历史记录。"
    lines = ["历史记录"]
    for run in runs:
        lines.append(
            f"- {run['id']} | 时间={run['ts']} | 方案={run['chosen_plan_id']} | 兜底={run['fallback_triggered']}"
        )
        if mode == "verbose":
            feedback = run.get("feedback", {})
            lines.append(f"  反馈={_zh_text(feedback.get('text', ''))}")
            lines.append(f"  已发出信号={run.get('signals_emitted', False)}")
    return "\n".join(lines)


def render_run_detail(run, transcript, mode):
    lines = [
        f"会话：{run['id']}",
        f"时间戳：{run['ts']}",
        f"选中方案：{run['chosen_plan_id']}",
        f"是否触发兜底：{run['fallback_triggered']}",
        f"是否发出信号：{run['signals_emitted']}",
        f"反馈：{_zh_text(run.get('feedback', {}).get('text', ''))}",
    ]
    if transcript and mode == "verbose":
        planning = transcript.get("planning", {})
        lines.append(f"候选方案数：{planning.get('candidate_count', '')}")
        lines.append(f"记录段落：{', '.join(transcript.keys())}")
        resource = transcript.get("resource_result", {})
        fallback = resource.get("fallback_event") or {}
        if fallback:
            lines.append(f"兜底变更：{_zh_text(fallback.get('from_item'))} -> {_zh_text(fallback.get('to_item'))}")
    return "\n".join(lines)


def render_reflection(run, transcript, profile, mode):
    if not run:
        return "暂无会话可反思。"
    lines = [
        "反思信息",
        f"会话：{run['id']}",
        f"是否触发兜底：{run['fallback_triggered']}",
        f"是否发出信号：{run['signals_emitted']}",
        f"反馈摘要：{_zh_text(run.get('feedback', {}).get('text', ''))}",
    ]
    if transcript:
        signals = transcript.get("signals", {})
        lines.append(f"用户偏好变化：{_zh_join(signals.get('user_pref_deltas', []))}")
    if mode == "verbose":
        lines.append(f"画像最后更新：{profile.get('last_updated', '')}")
        lines.append(f"商户信号：{_zh_text(', '.join(profile.get('merchant_signals', [])))}")
        lines.append(f"场景覆盖：{_zh_text(profile.get('scenario_overrides', {}))}")
    return "\n".join(lines)


def render_profile(profile):
    return "\n".join(
        [
            "偏好画像",
            f"用户偏好变化：{_zh_join(profile.get('user_pref_deltas', []))}",
            f"商户信号：{_zh_text(', '.join(profile.get('merchant_signals', [])))}",
            f"场景覆盖：{_zh_text(profile.get('scenario_overrides', {}))}",
            f"最后更新：{profile.get('last_updated', '')}",
        ]
    )


def render_replanned_plan(old_plan_id, new_plan, diff, mode):
    lines = [
        "已更新方案",
        f"原方案：{old_plan_id}",
        f"新方案：{new_plan.id}",
        f"变更：{_zh_text(diff.from_item)} -> {_zh_text(diff.to_item)}",
        f"继续锁定：{_locked_items(new_plan.locked_items)}",
        f"新的可调整项：{_zh_join(new_plan.flexible_items)}",
    ]
    if mode == "verbose":
        lines.append(f"原因：{_zh_text(diff.reason)}")
        lines.append(f"路线：{' -> '.join(_zh_text(slot.name) for slot in new_plan.slots)}")
    return "\n".join(lines)
