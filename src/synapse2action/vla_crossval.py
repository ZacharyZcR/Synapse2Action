from __future__ import annotations

from pathlib import Path

from .vla_baseline import train_knn_baseline
from .vla_benchmark import benchmark_vla_baseline
from .vla_dataset import export_dataset
from .vla_ridge import train_ridge_baseline


def run_leave_one_scenario_out(
    episode_paths: list[Path],
    scenario_directory: Path,
    output_directory: Path,
    algorithm: str = "ridge",
) -> dict[str, object]:
    if algorithm not in {"knn", "ridge"}:
        raise ValueError("unsupported VLA cross-validation algorithm")
    if len(episode_paths) < 2:
        raise ValueError("VLA cross-validation requires at least two episodes")
    sources = [path.name for path in episode_paths]
    if len(set(sources)) != len(sources):
        raise ValueError("VLA cross-validation requires unique episode source names")

    output_directory.mkdir(parents=True, exist_ok=True)
    folds = []
    for fold_index, validation_source in enumerate(sorted(sources)):
        fold_name = _fold_name(validation_source)
        fold_directory = output_directory / fold_name
        dataset_directory = fold_directory / "dataset"
        checkpoint_path = fold_directory / f"{algorithm}.json"
        export_dataset(
            episode_paths,
            dataset_directory,
            validation_sources={validation_source},
        )
        if algorithm == "ridge":
            train_ridge_baseline(dataset_directory, checkpoint_path)
        else:
            train_knn_baseline(dataset_directory, checkpoint_path)
        benchmark = benchmark_vla_baseline(
            dataset_directory,
            checkpoint_path,
            scenario_directory,
        )
        if len(benchmark["results"]) != 1:
            raise ValueError("leave-one-scenario-out fold must contain one validation result")
        if not benchmark["validation_samples"]:
            raise ValueError("leave-one-scenario-out validation episode has no samples")
        folds.append(
            {
                "fold": fold_index,
                "validation_source": validation_source,
                "dataset": f"{fold_name}/dataset",
                "checkpoint": f"{fold_name}/{algorithm}.json",
                "training_episodes": benchmark["training_episodes"],
                "validation_samples": benchmark["validation_samples"],
                "validation_velocity_mae": benchmark["validation_velocity_mae"],
                "validation_duration_accuracy": benchmark["validation_duration_accuracy"],
                **benchmark["results"][0],
            }
        )

    samples = sum(fold["validation_samples"] for fold in folds)
    passed = sum(fold["passed"] for fold in folds)
    return {
        "schema_version": 1,
        "benchmark": f"{algorithm}_vla_leave_one_scenario_out",
        "algorithm": algorithm,
        "episode_count": len(episode_paths),
        "fold_count": len(folds),
        "validation_samples": samples,
        "validation_velocity_mae": sum(
            fold["validation_velocity_mae"] * fold["validation_samples"] for fold in folds
        )
        / samples,
        "validation_duration_accuracy": sum(
            fold["validation_duration_accuracy"] * fold["validation_samples"] for fold in folds
        )
        / samples,
        "closed_loop_passed": passed,
        "closed_loop_failed": len(folds) - passed,
        "closed_loop_success_rate": passed / len(folds),
        "failed": len(folds) - passed,
        "folds": folds,
    }


def _fold_name(source: str) -> str:
    suffix = ".episode.json"
    if not source.endswith(suffix) or source == suffix:
        raise ValueError("cross-validation episode source is not a suite episode")
    return source[: -len(suffix)]
