"""AstrBot command entry point for the Bilibili intimacy calculator."""

from __future__ import annotations

import re

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register

from .calculator import MAX_BUDGET, plan_budget, render_plan

COMMAND_HELP = """用法：
/电池收益 <电池数> [普通|冻干|鲜食|自动] [提醒] [不抢首赠] [不跑旅程] [确定性]

示例：
/电池收益 1000
/电池收益 5639 鲜食 不抢首赠
/电池收益 38064 鲜食 提醒

选项说明：提醒=加入主播提醒回礼计划；不抢首赠=粉丝手幅不优先拿每日首赠；不跑旅程=不安排亲密之旅；确定性=不分配盲盒。"""

QUALITY_ALIASES = {
    "普通": "normal", "普通猫粮": "normal", "冻干": "freeze", "鲜食": "fresh", "自动": "auto",
}


def parse_options(message: str) -> tuple[int | None, dict[str, object]]:
    """Extract a battery amount and supported Chinese options from a command."""
    match = re.search(r"(?<!\d)(\d{1,9})(?!\d)", message.replace(",", ""))
    if not match:
        return None, {}
    options: dict[str, object] = {
        "quality": "auto",
        "reminder_enabled": "提醒" in message,
        "daily_banner_first": "不抢首赠" not in message,
        "journey_mode": "none" if "不跑旅程" in message else "single",
        "allocation": "intimacy" if "确定性" in message else "auto",
    }
    for text, quality in QUALITY_ALIASES.items():
        if text in message:
            options["quality"] = quality
            break
    return int(match.group(1)), options


@register(
    "astrbot_plugin_bilibili_intimacy",
    "paizi",
    "计算哔哩哔哩直播活动电池可获得的亲密度收益。",
    "1.0.0",
)
class BilibiliIntimacyPlugin(Star):
    """Chat command wrapper around the tested, dependency-free calculator."""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

    @filter.command("电池收益")
    async def battery_return(self, event: AstrMessageEvent):
        """计算预算：/电池收益 1000 鲜食 提醒。"""
        budget, options = parse_options(event.message_str)
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

    @filter.command("电池收益帮助")
    async def battery_return_help(self, event: AstrMessageEvent):
        """显示电池收益计算器的使用方法。"""
        yield event.plain_result(COMMAND_HELP)

    async def terminate(self):
        """AstrBot calls this hook when the plugin is disabled or unloaded."""
