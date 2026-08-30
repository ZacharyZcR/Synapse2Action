from __future__ import annotations

from statistics import mean
from math import sqrt
from typing import Any, Iterable, Mapping


STAGES = (
    "gripper_contact",
    "grasped",
    "lifted",
    "contacted_plate",
    "released_after_contact",
    "stable_on_plate",
    "remained_standing",
)


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> list[float]:
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = z * sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def summarize_groot_episodes(
    episodes: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(episode) for episode in episodes]
    if not rows:
        raise ValueError("GR00T benchmark requires at least one episode")
    seeds = [int(row["seed"]) for row in rows]
    if len(set(seeds)) != len(seeds):
        raise ValueError("GR00T benchmark seeds must be unique")
    successes = {stage: sum(row.get(stage) is True for row in rows) for stage in STAGES}
    rates = {stage: count / len(rows) for stage, count in successes.items()}
    strict_successes = sum(all(row.get(stage) is True for stage in STAGES) for row in rows)
    return {
        "schema_version": 1,
        "benchmark": "groot_g1_apple_to_plate_stages",
        "episodes": len(rows),
        "seeds": seeds,
        "stage_success_rate": rates,
        "stage_success_95ci": {
            stage: wilson_interval(count, len(rows)) for stage, count in successes.items()
        },
        "strict_success_rate": strict_successes / len(rows),
        "strict_success_95ci": wilson_interval(strict_successes, len(rows)),
        "mean_maximum_lift_m": mean(float(row["maximum_lift_m"]) for row in rows),
        "mean_apple_plate_progress_m": mean(
            float(row["apple_plate_progress_m"]) for row in rows
        ),
        "mean_minimum_apple_plate_xy_distance_m": mean(
            float(row["minimum_apple_plate_xy_distance_m"]) for row in rows
        ),
        "results": rows,
    }


def compare_groot_counterfactuals(
    variants: Mapping[str, Iterable[Mapping[str, Any]]],
    *,
    baseline: str = "baseline",
) -> dict[str, Any]:
    rows = {
        name: [dict(episode) for episode in episodes]
        for name, episodes in variants.items()
    }
    if baseline not in rows:
        raise ValueError("GR00T counterfactuals require the named baseline")
    if len(rows) < 2:
        raise ValueError("GR00T counterfactuals require at least two variants")
    baseline_seeds = [int(row["seed"]) for row in rows[baseline]]
    if not baseline_seeds:
        raise ValueError("GR00T counterfactual baseline must not be empty")
    summaries: dict[str, dict[str, Any]] = {}
    for name, episodes in rows.items():
        seeds = [int(row["seed"]) for row in episodes]
        if seeds != baseline_seeds:
            raise ValueError(
                f"variant {name} must use the baseline seeds in the same order"
            )
        summaries[name] = summarize_groot_episodes(episodes)
    reference = summaries[baseline]
    effects = {}
    for name, summary in summaries.items():
        if name == baseline:
            continue
        paired = []
        for reference_row, variant_row in zip(rows[baseline], rows[name], strict=True):
            paired.append(
                {
                    "seed": int(reference_row["seed"]),
                    "grasped_changed": variant_row.get("grasped")
                    != reference_row.get("grasped"),
                    "lifted_changed": variant_row.get("lifted")
                    != reference_row.get("lifted"),
                    "maximum_lift_m_delta": float(variant_row["maximum_lift_m"])
                    - float(reference_row["maximum_lift_m"]),
                }
            )
        effects[name] = {
            "grasp_rate_delta": summary["stage_success_rate"]["grasped"]
            - reference["stage_success_rate"]["grasped"],
            "lift_rate_delta": summary["stage_success_rate"]["lifted"]
            - reference["stage_success_rate"]["lifted"],
            "strict_success_rate_delta": summary["strict_success_rate"]
            - reference["strict_success_rate"],
            "mean_maximum_lift_m_delta": summary["mean_maximum_lift_m"]
            - reference["mean_maximum_lift_m"],
            "paired_results": paired,
        }
    return {
        "schema_version": 1,
        "benchmark": "groot_g1_lift_counterfactuals",
        "baseline": baseline,
        "paired_seeds": baseline_seeds,
        "variants": summaries,
        "effects_vs_baseline": effects,
    }
