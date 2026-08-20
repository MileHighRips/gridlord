"""Trade analyzer: expected-value delta, season impact, risk, counteroffers."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TradeAsset:
    player_id: int
    name: str
    position: str
    ros_points: float  # rest-of-season projected points
    std_points: float
    vorp: float


@dataclass
class TradeSide:
    team: str
    gives: list[TradeAsset]
    needs: list[str]  # positions this team is starved at (for fit scoring)


def analyze_trade(side_a: TradeSide, side_b: TradeSide) -> dict:
    """Evaluate a two-sided trade from both perspectives."""
    a_out = sum(p.vorp for p in side_a.gives)
    b_out = sum(p.vorp for p in side_b.gives)

    a_net_vorp = b_out - a_out
    b_net_vorp = a_out - b_out

    a_fit = _positional_fit(side_b.gives, side_a.needs)
    b_fit = _positional_fit(side_a.gives, side_b.needs)

    return {
        "side_a": {
            "team": side_a.team,
            "net_vorp": round(a_net_vorp, 2),
            "ros_points_delta": round(
                sum(p.ros_points for p in side_b.gives)
                - sum(p.ros_points for p in side_a.gives),
                1,
            ),
            "positional_fit": a_fit,
            "risk_score": _risk_score(side_b.gives),
        },
        "side_b": {
            "team": side_b.team,
            "net_vorp": round(b_net_vorp, 2),
            "ros_points_delta": round(
                sum(p.ros_points for p in side_a.gives)
                - sum(p.ros_points for p in side_b.gives),
                1,
            ),
            "positional_fit": b_fit,
            "risk_score": _risk_score(side_a.gives),
        },
        "verdict": _verdict(a_net_vorp, a_fit),
        "fairness": _fairness(a_net_vorp),
        "counteroffers": _counteroffers(side_a, side_b, a_net_vorp),
    }


def _positional_fit(incoming: list[TradeAsset], needs: list[str]) -> float:
    if not incoming:
        return 0.0
    hits = sum(1 for p in incoming if p.position in needs)
    return round(hits / len(incoming), 2)


def _risk_score(incoming: list[TradeAsset]) -> float:
    """0 (safe) .. 1 (volatile). Based on coefficient of variation."""
    if not incoming:
        return 0.0
    cvs = [p.std_points / (p.ros_points + 1e-6) for p in incoming]
    return round(min(sum(cvs) / len(cvs), 1.0), 2)


def _verdict(net_vorp: float, fit: float) -> str:
    adj = net_vorp + fit * 5
    if adj > 8:
        return "Clear win"
    if adj > 2:
        return "Favorable"
    if adj > -2:
        return "Roughly even"
    if adj > -8:
        return "Unfavorable"
    return "Clear loss"


def _fairness(net_vorp: float) -> str:
    return "balanced" if abs(net_vorp) < 3 else "lopsided"


def _counteroffers(side_a: TradeSide, side_b: TradeSide, a_net: float) -> list[str]:
    suggestions: list[str] = []
    if a_net < -3:
        cheapest = min(side_a.gives, key=lambda p: p.vorp, default=None)
        if cheapest:
            suggestions.append(
                f"Ask {side_b.team} to add a bench piece — you're giving up "
                f"{abs(a_net):.1f} VORP"
            )
    if a_net > 3:
        suggestions.append("This favors you; expect a counter or sweeten to close it")
    return suggestions
