"""AstrBot command entry point for the Bilibili intimacy calculator."""

from __future__ import annotations

import re

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .chart import render_benefit_curve
from .calculator import MAX_BUDGET, find_minimum_budget_for_target, plan_budget, render_plan

COMMAND_HELP = """用法：
/电池收益 <电池数> [普通|冻干|鲜食|自动] [舰长|提督|总督] [首赠1|首赠2|首赠3] [提醒] [不跑旅程] [确定性]

示例：
/电池收益 1000
/电池收益 5639 鲜食 不抢首赠
/电池收益 38064 鲜食 提醒
/电池收益 220000 总督 首赠3

选项说明：舰长/提督/总督=将该礼物作为每日第一笔；首赠1/2/3=当日首赠倍率；总督按 ¥19,998（199,980 电池）计算；提醒=加入主播提醒回礼计划；不跑旅程=不安排亲密之旅；确定性=不分配盲盒。"""

QUALITY_ALIASES = {
    "普通": "normal", "普通猫粮": "normal", "冻干": "freeze", "鲜食": "fresh", "自动": "auto",
}
FIRST_GIFT_ALIASES = {"舰长": "captain", "提督": "admiral", "总督": "governor"}


def parse_options(
    message: str, default_daily_first_multiplier: int = 3
) -> tuple[int | None, dict[str, object]]:
    """Extract a battery amount and supported Chinese options from a command."""
    match = re.search(r"(?<!\d)(\d{1,9})(?!\d)", message.replace(",", ""))
    if not match:
        return None, {}
    options: dict[str, object] = {
        "quality": "auto",
        "reminder_enabled": "提醒" in message,
        "daily_first_gift": "auto",
        "daily_first_multiplier": default_daily_first_multiplier,
        "journey_mode": "none" if "不跑旅程" in message else "single",
        "allocation": "intimacy" if "确定性" in message else "auto",
    }
    for text, quality in QUALITY_ALIASES.items():
        if text in message:
            options["quality"] = quality
            break
    for text, gift in FIRST_GIFT_ALIASES.items():
        if text in message:
            options["daily_first_gift"] = gift
            break
    multiplier_match = re.search(r"首赠\s*[x×]?\s*([123])", message, flags=re.IGNORECASE)
    if multiplier_match:
        options["daily_first_multiplier"] = int(multiplier_match.group(1))
    return int(match.group(1)), options


@register(
    "astrbot_plugin_bilibili_intimacy",
    "paizi",
    "计算哔哩哔哩直播活动电池可获得的亲密度收益。",
    "1.5.0",
)
class BilibiliIntimacyPlugin(Star):
    """Chat command wrapper around the tested, dependency-free calculator."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    @filter.command("电池收益")
    async def battery_return(self, event: AstrMessageEvent):
        """计算预算：/电池收益 1000 鲜食 提醒。"""
        default_multiplier = int(self.config.get("daily_first_multiplier", 3))
        default_multiplier = default_multiplier if default_multiplier in {1, 2, 3} else 3
        budget, options = parse_options(event.message_str, default_multiplier)
        if budget is None:
            yield event.plain_result(COMMAND_HELP)
            return

        max_budget = int(self.config.get("max_budget", MAX_BUDGET))
        if budget > max_budget:
            yield event.plain_result(f"单次预算上限为 {max_budget:,} 电池。\n\n{COMMAND_HELP}")
            return
        try:
            plan = plan_budget(budget, max_budget=max_budget, **options)
        except (TypeError, ValueError) as exc:
            logger.warning("电池收益计算参数无效：%s", exc)
            yield event.plain_result("参数无法识别，请检查后重试。\n\n" + COMMAND_HELP)
            return
        yield event.plain_result(render_plan(plan))

    @filter.command("\u4eb2\u5bc6\u5ea6\u53cd\u63a8")
    async def intimacy_reverse(self, event: AstrMessageEvent):
        """Find the least battery budget that meets an intimacy target."""
        default_multiplier = int(self.config.get("daily_first_multiplier", 3))
        default_multiplier = default_multiplier if default_multiplier in {1, 2, 3} else 3
        target, options = parse_options(event.message_str, default_multiplier)
        if target is None:
            yield event.plain_result("\u7528\u6cd5\uff1a/\u4eb2\u5bc6\u5ea6\u53cd\u63a8 <\u76ee\u6807\u4eb2\u5bc6\u5ea6> [\u53ef\u9009\u89c4\u5219]")
            return
        max_budget = int(self.config.get("max_budget", MAX_BUDGET))
        try:
            plan, maximum_plan = find_minimum_budget_for_target(
                target, max_budget=max_budget, **options
            )
        except (TypeError, ValueError) as exc:
            logger.warning("intimacy reverse calculation has invalid options: %s", exc)
            yield event.plain_result("\\u53c2\\u6570\\u65e0\\u6cd5\\u8bc6\\u522b\\uff0c\\u8bf7\\u68c0\\u67e5\\u540e\\u91cd\\u8bd5\\u3002")
            return
        if plan is None:
            yield event.plain_result(
                f"\u5728 {max_budget:,} \u7535\u6c60\u4e0a\u9650\u5185\u65e0\u6cd5\u8fbe\u5230 {target:,} \u4eb2\u5bc6\u5ea6\uff1b"
                f"\u6700\u9ad8\u9884\u8ba1\u4e3a {maximum_plan.expected_total:,}\u3002"
            )
            return
        yield event.plain_result(
            f"\u76ee\u6807 {target:,} \u4eb2\u5bc6\u5ea6\uff1a\u6700\u5c11\u9700\u8981 {plan.budget:,} \u7535\u6c60\u3002\n\n{render_plan(plan)}"
        )

    @filter.command("\u6536\u76ca\u66f2\u7ebf")
    async def benefit_curve(self, event: AstrMessageEvent):
        """Draw the RMB-investment to expected-intimacy curve."""
        default_multiplier = int(self.config.get("daily_first_multiplier", 3))
        default_multiplier = default_multiplier if default_multiplier in {1, 2, 3} else 3
        _, parsed_options = parse_options(event.message_str, default_multiplier)
        options = {
            "quality": "auto",
            "reminder_enabled": False,
            "daily_first_gift": "auto",
            "daily_first_multiplier": default_multiplier,
            "journey_mode": "single",
            "allocation": "auto",
        }
        options.update(parsed_options)
        max_budget = int(self.config.get("max_budget", MAX_BUDGET))
        try:
            image_path = render_benefit_curve(max_budget, **options)
            maximum_plan = plan_budget(max_budget, max_budget=max_budget, **options)
        except (OSError, TypeError, ValueError) as exc:
            logger.warning("benefit curve generation failed: %s", exc)
            yield event.plain_result("\u6536\u76ca\u66f2\u7ebf\u751f\u6210\u5931\u8d25\uff0c\u8bf7\u7a0d\u540e\u91cd\u8bd5\u3002")
            return
        yield event.plain_result(
            f"\u6536\u76ca\u66f2\u7ebf\uff1a\u4eba\u6c11\u5e01\u6295\u5165 0 \u81f3 {max_budget / 10:,.0f}\u5143\uff0c"
            f"\u9884\u8ba1\u4eb2\u5bc6\u5ea6\u6700\u9ad8 {maximum_plan.expected_total:,}\u3002"
        )
        yield event.image_result(str(image_path))

    @filter.command("电池收益帮助")
    async def battery_return_help(self, event: AstrMessageEvent):
        """显示电池收益计算器的使用方法。"""
        yield event.plain_result(COMMAND_HELP)

    async def terminate(self):
        """AstrBot calls this hook when the plugin is disabled or unloaded."""
