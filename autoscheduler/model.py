"""Decision-tree training and persistence."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from statistics import mean

from autoscheduler.evaluation import ALGORITHMS
from autoscheduler.features import FEATURE_NAMES


def _imports():
    import joblib
    from sklearn.metrics import accuracy_score
    from sklearn.tree import DecisionTreeClassifier

    return joblib, accuracy_score, DecisionTreeClassifier


def _score_column(algorithm: str) -> str:
    return f"score_{algorithm.lower().replace(' ', '_')}"


def _mean_regret(rows: list[dict], predictions: list[str]) -> float:
    return sum(
        row[_score_column(prediction)] - row[_score_column(row["label"])]
        for row, prediction in zip(rows, predictions)
    ) / len(rows)


def _candidate_key(metrics: dict, depth_rank: int) -> tuple:
    """Prefer lower regret; resolve ties with the simpler, more regularized tree."""
    return (metrics["validation_mean_regret"], depth_rank, -metrics["min_samples_leaf"])


def _split_indexes(rows: list[dict], random_state: int, group_key: str | None = None) -> tuple[list[int], list[int], list[int]]:
    from sklearn.model_selection import GroupShuffleSplit, train_test_split

    indexes = list(range(len(rows)))
    if group_key is not None:
        groups = [row[group_key] for row in rows]
        if len(set(groups)) < 4:
            raise ValueError("grouped training requires at least four distinct traces")
        train_positions, holdout_positions = next(
            GroupShuffleSplit(n_splits=1, test_size=0.30, random_state=random_state).split(indexes, groups=groups)
        )
        train_indexes = [indexes[position] for position in train_positions]
        holdout_indexes = [indexes[position] for position in holdout_positions]
        validation_positions, test_positions = next(
            GroupShuffleSplit(n_splits=1, test_size=0.50, random_state=random_state).split(
                holdout_indexes, groups=[groups[index] for index in holdout_indexes]
            )
        )
        validation_indexes = [holdout_indexes[position] for position in validation_positions]
        test_indexes = [holdout_indexes[position] for position in test_positions]
        train_groups, validation_groups, test_groups = (
            {groups[index] for index in split}
            for split in (train_indexes, validation_indexes, test_indexes)
        )
        assert not (train_groups & validation_groups or train_groups & test_groups or validation_groups & test_groups)
        return train_indexes, validation_indexes, test_indexes

    labels = [row["label"] for row in rows]
    stratify = labels if min(Counter(labels).values()) >= 2 else None
    train_indexes, holdout_indexes = train_test_split(
        indexes, test_size=0.30, random_state=random_state, stratify=stratify
    )
    holdout_labels = [labels[index] for index in holdout_indexes]
    holdout_stratify = holdout_labels if min(Counter(holdout_labels).values()) >= 2 else None
    validation_indexes, test_indexes = train_test_split(
        holdout_indexes, test_size=0.50, random_state=random_state, stratify=holdout_stratify
    )
    return train_indexes, validation_indexes, test_indexes


def train_model(
    rows: list[dict],
    model_path: str | Path,
    random_state: int = 42,
    priority_rr_config: dict | None = None,
    feature_names: tuple[str, ...] = FEATURE_NAMES,
    metadata: dict | None = None,
    group_key: str | None = None,
) -> dict:
    if len(rows) < 20:
        raise ValueError("at least 20 labeled workloads are required")
    joblib, accuracy_score, DecisionTreeClassifier = _imports()
    labels = [row["label"] for row in rows]
    train_indexes, validation_indexes, test_indexes = _split_indexes(rows, random_state, group_key)
    train_rows = [rows[index] for index in train_indexes]
    validation_rows = [rows[index] for index in validation_indexes]
    test_rows = [rows[index] for index in test_indexes]
    train_x = [[row[name] for name in feature_names] for row in train_rows]
    train_y = [row["label"] for row in train_rows]
    validation_x = [[row[name] for name in feature_names] for row in validation_rows]
    validation_y = [row["label"] for row in validation_rows]
    test_x = [[row[name] for name in feature_names] for row in test_rows]
    test_y = [row["label"] for row in test_rows]
    validation_static_scores = {
        algorithm: mean(row[_score_column(algorithm)] for row in validation_rows)
        for algorithm in ALGORITHMS
    }
    static_baseline = min(
        ALGORITHMS,
        key=lambda algorithm: (validation_static_scores[algorithm], tuple(ALGORITHMS).index(algorithm)),
    )

    best = None
    best_key = None
    best_settings = None
    best_metrics = None
    candidate_metrics = []
    for depth_rank, max_depth in enumerate((3, 5, 8, None)):
        for min_samples_leaf in (10, 5, 1):
            candidate = DecisionTreeClassifier(
                max_depth=max_depth,
                min_samples_leaf=min_samples_leaf,
                random_state=random_state,
            ).fit(train_x, train_y)
            predictions = list(candidate.predict(validation_x))
            accuracy = accuracy_score(validation_y, predictions)
            regret = _mean_regret(validation_rows, predictions)
            metrics = {
                "max_depth": max_depth,
                "min_samples_leaf": min_samples_leaf,
                "validation_accuracy": accuracy,
                "validation_mean_regret": regret,
            }
            candidate_metrics.append(metrics)
            key = _candidate_key(metrics, depth_rank)
            if best_key is None or key < best_key:
                best, best_key = candidate, key
                best_settings = (max_depth, min_samples_leaf)
                best_metrics = metrics

    test_predictions = list(best.predict(test_x))
    test_accuracy = accuracy_score(test_y, test_predictions)
    test_regret = _mean_regret(test_rows, test_predictions)
    final_model = DecisionTreeClassifier(
        max_depth=best_settings[0],
        min_samples_leaf=best_settings[1],
        random_state=random_state,
    ).fit(train_x + validation_x, train_y + validation_y)

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    bundle_metadata = {
        "policy_set": list(ALGORITHMS),
        "priority_rr_config": priority_rr_config or dict(ALGORITHMS["Priority RR"][1]),
        "static_baseline": static_baseline,
        **(metadata or {}),
    }
    joblib.dump({"model": final_model, "features": feature_names, "metadata": bundle_metadata}, model_path)
    report = {
        "rows": len(rows),
        "random_state": random_state,
        "split": {"train": 0.70, "validation": 0.15, "test": 0.15},
        "class_distribution": dict(Counter(labels)),
        "max_depth": best_settings[0],
        "min_samples_leaf": best_settings[1],
        "validation_accuracy": best_metrics["validation_accuracy"],
        "validation_mean_regret": best_metrics["validation_mean_regret"],
        "test_accuracy": test_accuracy,
        "test_mean_regret": test_regret,
        "validation_static_scores": validation_static_scores,
        "static_baseline": static_baseline,
        "priority_rr_config": bundle_metadata["priority_rr_config"],
        "policy_set": bundle_metadata["policy_set"],
        "feature_importance": {
            name: float(value) for name, value in zip(feature_names, final_model.feature_importances_)
        },
        "candidate_metrics": candidate_metrics,
    }
    if group_key is not None:
        report["split_group_key"] = group_key
        report["split_trace_counts"] = {
            name: len({rows[index][group_key] for index in split})
            for name, split in (
                ("train", train_indexes), ("validation", validation_indexes), ("test", test_indexes)
            )
        }
    return report


def load_model(path: str | Path, feature_names: tuple[str, ...] = FEATURE_NAMES):
    joblib, *_ = _imports()
    bundle = joblib.load(path)
    if tuple(bundle.get("features", ())) != tuple(feature_names):
        raise ValueError("model feature schema does not match current code")
    if bundle.get("metadata", {}).get("policy_set") != list(ALGORITHMS):
        raise ValueError("model policy set does not match current schedulers; retrain the model")
    return bundle["model"]


def load_model_metadata(path: str | Path) -> dict:
    joblib, *_ = _imports()
    return joblib.load(path).get("metadata", {})
