"""Pure calculation logic for the Bilibili livestream event planner.

This module deliberately has no AstrBot dependency so it can be tested without
starting an AstrBot instance.
"""

from __future__ import annotations

from dataclasses import dataclass

MAX_BUDGET = 300_000
START_GROWTH = 1_050
DAILY_SIGNIN_FOOD = 21
BANNER_LIMIT = 21
BANNER_COST = 1
JOURNEY_COST = 500
BOX_COST = 330
BOX_CONTRACT_RATE = 0.4008
FOOD_PER_CONTRACT = 3
BASE_GIFT_MULTIPLIER = 1.0
CAMPAIGN_FIRST_GIFT_BONUS = 1.0
NAVY_FIRST_GIFT_BONUS = 0.5


@dataclass(frozen=True)
class FoodQuality:
    key: str
    label: str
    cost: int
    growth: int


QUALITIES = {
    "normal": FoodQuality("normal", "普通", 0, 100),
    "freeze": FoodQuality("freeze", "冻干", 60, 120),
    "fresh": FoodQuality("fresh", "鲜食", 660, 150),
}

DAILY_FIRST_GIFTS = {
    "auto": {"label": "自动收益最优", "cost": 0, "rmb": 0},
    "none": {"label": "不指定", "cost": 0, "rmb": 0},
    "banner": {"label": "粉丝手幅", "cost": 0, "rmb": 0},
    "captain": {"label": "舰长", "cost": 1_980, "rmb": 198},
    "admiral": {"label": "提督", "cost": 19_980, "rmb": 1_998},
    "governor": {"label": "总督", "cost": 199_980, "rmb": 19_998},
}

LEVELS = (
    (1, 0, 0, 0), (2, 100, 0, 0), (3, 300, 0, 0),
    (4, 600, 0, 0), (5, 900, 0, 0), (6, 1200, 0, 0),
    (7, 1600, 0, 0), (8, 2100, 0, 0), (9, 3000, 1000, 2000),
    (10, 6000, 5000, 10000), (11, 10000, 8000, 16000),
    (12, 16000, 20000, 40000), (13, 24000, 80000, 160000),
)

STRATEGIES = {
    "low": {"label": "普通粉丝", "journey_target": 1, "journey_multiplier": 5.3, "deterministic_multiplier": 4.0},
    "medium": {"label": "续航计划", "journey_target": 4, "journey_multiplier": 3.675, "deterministic_multiplier": 4.5},
    "high": {"label": "八月提醒回礼计划", "journey_target": 3, "journey_multiplier": 4.136, "deterministic_multiplier": 4.5},
}


@dataclass(frozen=True)
class Plan:
    budget: int
    used: int
    quality: FoodQuality
    first_gift: str
    first_gift_paid: int
    daily_first_multiplier: int
    strategy: str
    banner_count: int
    journey_count: int
    box_count: int
    expected_box_contracts: float
    cat_food: float
    growth: float
    level: int
    gift_intimacy: int
    total_min: int
    total_max: int
    expected_total: int
    host_score: int


def clamp_budget(value: int | float | str, max_budget: int = MAX_BUDGET) -> int:
    """Convert a user supplied budget to a safe, integer battery amount."""
    try:
        number = int(float(value))
    except (TypeError, ValueError):
        return 0
    return min(max(0, number), max(0, int(max_budget)))


def _level_for(growth: float) -> tuple[int, int, int]:
    result = (1, 0, 0)
    for level, threshold, gift_min, gift_max in LEVELS:
        if growth >= threshold:
            result = (level, gift_min, gift_max)
    return result


def _choose_strategy(budget: int, quality_cost: int, reminder_enabled: bool, journey_mode: str, first_gift_cost: int = 0) -> str:
    journey_cost = 0 if journey_mode == "none" else JOURNEY_COST
    if reminder_enabled and budget >= quality_cost + first_gift_cost + 21 + 19_800 + 15_800 + journey_cost:
        return "high"
    if budget >= quality_cost + first_gift_cost + 21 + 1_380 + journey_cost:
        return "medium"
    return "low"


def _daily_first_gift_multiplier(first_gift: str, daily_first_multiplier: int) -> float:
    """Stack base, campaign, reward-day, and Great Navigation bonuses additively."""
    navy_bonus = NAVY_FIRST_GIFT_BONUS if first_gift in {"captain", "admiral", "governor"} else 0
    return BASE_GIFT_MULTIPLIER + CAMPAIGN_FIRST_GIFT_BONUS + daily_first_multiplier + navy_bonus


def first_gift_schedule(first_gift: str, daily_first_multiplier: int) -> str:
    """Describe the one qualifying first-gift order without confusing a multiplier for a quantity."""
    if first_gift not in {"captain", "admiral", "governor"}:
        return "未安排舰船礼物首赠"
    reward_days = {
        3: ("9/13", "+300%"),
        2: ("8/26", "+200%"),
        1: ("普通奖励日", "+100%"),
    }
    date, bonus = reward_days.get(daily_first_multiplier, reward_days[1])
    total_multiplier = _daily_first_gift_multiplier(first_gift, daily_first_multiplier)
    return (
        f"{DAILY_FIRST_GIFTS[first_gift]['label']} 1 个，放在 {date} {bonus} 首赠窗口"
        f"（总倍率 {total_multiplier:.1f}×；同一奖励日仅首笔礼物享受该加成）"
    )


def _build_plan(
    budget: int,
    quality: FoodQuality,
    *,
    reminder_enabled: bool,
    daily_banner_first: bool,
    journey_mode: str,
    actual_contracts: int,
    allocation: str,
    daily_first_gift: str,
    daily_first_multiplier: int,
) -> Plan:
    first_gift = DAILY_FIRST_GIFTS.get(daily_first_gift, DAILY_FIRST_GIFTS["banner"])
    strategy_key = _choose_strategy(budget, quality.cost, reminder_enabled, journey_mode, first_gift["cost"])
    strategy = STRATEGIES[strategy_key]
    remaining = budget

    def spend(amount: int) -> int:
        nonlocal remaining
        paid = min(remaining, max(0, int(amount)))
        remaining -= paid
        return paid

    quality_paid = spend(quality.cost) if remaining >= quality.cost else 0
    first_gift_paid = spend(first_gift["cost"]) if first_gift["cost"] and remaining >= first_gift["cost"] else 0
    banner_count = min(BANNER_LIMIT, remaining // BANNER_COST)
    banner_paid = spend(banner_count * BANNER_COST)

    reminder_paid = 0
    navy_paid = 0
    if strategy_key == "high":
        reminder_paid = spend(19_800)
        navy_paid = spend(15_800)
    elif strategy_key == "medium":
        navy_paid = spend(1_380)

    requested_journeys = 0
    if journey_mode != "none":
        requested_journeys = 1 if journey_mode == "single" and strategy_key == "low" else strategy["journey_target"]
    journey_count = min(requested_journeys, remaining // JOURNEY_COST)
    spend(journey_count * JOURNEY_COST)

    box_count = 0 if allocation == "intimacy" else min(10, remaining // BOX_COST)
    box_paid = spend(box_count * BOX_COST)
    remainder_paid = spend(remaining)

    expected_box_contracts = box_count * BOX_CONTRACT_RATE
    banner_multiplier = 2.67 if first_gift["label"] == "粉丝手幅" else 2.55
    cat_food = (
        DAILY_SIGNIN_FOOD + banner_count + (10 if navy_paid else 0)
        + journey_count * 3 + actual_contracts * FOOD_PER_CONTRACT
        + expected_box_contracts * FOOD_PER_CONTRACT
    )
    growth = START_GROWTH + cat_food * quality.growth
    level, gift_min, gift_max = _level_for(growth)
    gift_mid = (gift_min + gift_max) / 2

    first_gift_multiplier = _daily_first_gift_multiplier(daily_first_gift, daily_first_multiplier)
    gift_intimacy = round(
        banner_paid * banner_multiplier
        + first_gift_paid * first_gift_multiplier
        + reminder_paid * 4.5
        + journey_count * JOURNEY_COST * strategy["journey_multiplier"]
        + navy_paid * 5.5
        + remainder_paid * strategy["deterministic_multiplier"]
        + box_paid * 4.9344
    )
    total_min = gift_intimacy + gift_min
    total_max = gift_intimacy + gift_max
    host_score = round(
        banner_count * 5 + reminder_paid + journey_count * 750 + navy_paid
        + remainder_paid + box_count * 356.75
    )

    return Plan(
        budget=budget, used=budget - remaining, quality=quality, strategy=strategy_key,
        first_gift=daily_first_gift, first_gift_paid=first_gift_paid,
        daily_first_multiplier=daily_first_multiplier,
        banner_count=banner_count, journey_count=journey_count, box_count=box_count,
        expected_box_contracts=expected_box_contracts, cat_food=cat_food, growth=growth,
        level=level, gift_intimacy=gift_intimacy, total_min=total_min,
        total_max=total_max, expected_total=round(gift_intimacy + gift_mid),
        host_score=host_score,
    )


def plan_budget(
    budget: int | float | str,
    *,
    quality: str = "auto",
    reminder_enabled: bool = False,
    daily_banner_first: bool = True,
    journey_mode: str = "single",
    actual_contracts: int = 0,
    allocation: str = "auto",
    daily_first_gift: str = "banner",
    daily_first_multiplier: int = 1,
    max_budget: int = MAX_BUDGET,
) -> Plan:
    """Create the same battery plan as the original web calculator."""
    safe_budget = clamp_budget(budget, max_budget)
    settings = {
        "reminder_enabled": reminder_enabled,
        "daily_banner_first": daily_banner_first,
        "journey_mode": journey_mode if journey_mode in {"single", "all", "none"} else "single",
        "actual_contracts": max(0, int(actual_contracts)),
        "allocation": "intimacy" if allocation == "intimacy" else "auto",
        "daily_first_gift": (
            "none" if daily_first_gift == "banner" and not daily_banner_first
            else daily_first_gift if daily_first_gift in DAILY_FIRST_GIFTS else "banner"
        ),
        "daily_first_multiplier": int(daily_first_multiplier) if int(daily_first_multiplier) in {1, 2, 3} else 1,
    }
    if quality in QUALITIES:
        if settings["daily_first_gift"] == "auto":
            return max(
                (
                    _build_plan(
                        safe_budget,
                        QUALITIES[quality],
                        **{**settings, "daily_first_gift": gift},
                    )
                    for gift in DAILY_FIRST_GIFTS
                    if gift != "auto" and DAILY_FIRST_GIFTS[gift]["cost"] <= safe_budget
                ),
                key=lambda item: (item.expected_total, item.growth, item.first_gift_paid),
            )
        return _build_plan(safe_budget, QUALITIES[quality], **settings)

    candidates = []
    for candidate in QUALITIES.values():
        if candidate.cost > safe_budget:
            continue
        gifts = (
            (gift for gift in DAILY_FIRST_GIFTS if gift != "auto")
            if settings["daily_first_gift"] == "auto"
            else (settings["daily_first_gift"],)
        )
        candidates.extend(
            _build_plan(
                safe_budget,
                candidate,
                **{**settings, "daily_first_gift": gift},
            )
            for gift in gifts
            if DAILY_FIRST_GIFTS[gift]["cost"] <= safe_budget
        )
    return max(candidates, key=lambda item: (item.expected_total, item.growth))


def find_minimum_budget_for_target(
    target_intimacy: int | float | str,
    *,
    max_budget: int = MAX_BUDGET,
    **options: object,
) -> tuple[Plan | None, Plan]:
    """Return the least budgeted plan meeting a target and the maximum plan.

    The automatic plan is monotonic with budget: each additional battery can
    remain in the prior best allocation, while level rewards are nonnegative.
    This lets binary search find the exact integer battery threshold.
    """
    try:
        target = max(0, int(float(target_intimacy)))
    except (TypeError, ValueError):
        target = 0
    safe_max_budget = clamp_budget(max_budget)
    settings = {**options, "daily_first_gift": options.get("daily_first_gift", "auto")}
    maximum_plan = plan_budget(safe_max_budget, max_budget=safe_max_budget, **settings)
    if maximum_plan.expected_total < target:
        return None, maximum_plan

    low, high = 0, safe_max_budget
    while low < high:
        middle = (low + high) // 2
        if plan_budget(middle, max_budget=safe_max_budget, **settings).expected_total >= target:
            high = middle
        else:
            low = middle + 1
    return plan_budget(low, max_budget=safe_max_budget, **settings), maximum_plan


def render_plan(plan: Plan) -> str:
    """Render a concise chat-friendly result without platform-specific markup."""
    multiplier = plan.expected_total / plan.budget if plan.budget else 0
    schedule = first_gift_schedule(plan.first_gift, plan.daily_first_multiplier)
    return (
        "哔哩哔哩直播活动电池规划\n"
        f"预算：{plan.budget:,} 电池｜实际分配：{plan.used:,} 电池\n"
        + (f"首赠安排：{schedule}｜支出 {plan.first_gift_paid:,} 电池\n" if plan.first_gift_paid else "")
        + f"推荐：{plan.quality.label}猫粮 + {plan.box_count} 盒冲猫（{STRATEGIES[plan.strategy]['label']}）\n"
        f"预计亲密度：{plan.expected_total:,}\n"
        f"亲密度范围：{plan.total_min:,} ～ {plan.total_max:,}\n"
        f"礼物产生亲密度：{plan.gift_intimacy:,}｜综合倍率：{multiplier:.2f}×\n"
        f"猫粮：{plan.cat_food:.4f} 份｜成长值：{plan.growth:,.0f}｜Lv.{plan.level}\n"
        f"粉丝手幅：{plan.banner_count}｜亲密之旅：{plan.journey_count}｜主播榜亲密值：{plan.host_score:,}\n\n"
        "说明：盲盒契约与主播榜数值基于参考计算器样例估算，结果仅作活动规划参考。\n"
        "舰船礼物时点建议：优先 9/13 +300% 窗口，总督/提督/舰长三选一各上 1 个；\n"
        "预算或资格不足时再用 8/26 +200% 窗口补 1 个。倍率数字表示加成档位，不表示购买数量。"
    )
