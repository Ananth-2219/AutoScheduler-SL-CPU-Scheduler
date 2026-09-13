"""Decision-tree training and persistence."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from autoscheduler.features import FEATURE_NAMES


def _imports():
    import joblib
    from sklearn.metrics import accuracy_score
    from sklearn.model_selection import train_test_split
    from sklearn.tree import DecisionTreeClassifier

    return joblib, accuracy_score, train_test_split, DecisionTreeClassifier


def train_model(rows: list[dict], model_path: str | Path, random_state: int = 42) -> dict:
    if len(rows) < 20:
        raise ValueError("at least 20 labeled workloads are required")
    joblib, accuracy_score, train_test_split, DecisionTreeClassifier = _imports()
    features = [[row[name] for name in FEATURE_NAMES] for row in rows]
    labels = [row["label"] for row in rows]
    stratify = labels if min(Counter(labels).values()) >= 2 else None

    train_x, holdout_x, train_y, holdout_y = train_test_split(
        features, labels, test_size=0.30, random_state=random_state, stratify=stratify
    )
    holdout_stratify = holdout_y if min(Counter(holdout_y).values()) >= 2 else None
    validation_x, test_x, validation_y, test_y = train_test_split(
        holdout_x,
        holdout_y,
        test_size=0.50,
        random_state=random_state,
        stratify=holdout_stratify,
    )

    best = None
    best_accuracy = -1.0
    best_settings = None
    for max_depth in (3, 5, 8, None):
        for min_samples_leaf in (1, 5, 10):
            candidate = DecisionTreeClassifier(
                max_depth=max_depth,
                min_samples_leaf=min_samples_leaf,
                random_state=random_state,
            ).fit(train_x, train_y)
            accuracy = accuracy_score(validation_y, candidate.predict(validation_x))
            if accuracy > best_accuracy:
                best, best_accuracy = candidate, accuracy
                best_settings = (max_depth, min_samples_leaf)

    test_accuracy = accuracy_score(test_y, best.predict(test_x))
    final_model = DecisionTreeClassifier(
        max_depth=best_settings[0],
        min_samples_leaf=best_settings[1],
        random_state=random_state,
    ).fit(train_x + validation_x, train_y + validation_y)

    model_path = Path(model_path)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"model": final_model, "features": FEATURE_NAMES}, model_path)
    return {
        "rows": len(rows),
        "random_state": random_state,
        "split": {"train": 0.70, "validation": 0.15, "test": 0.15},
        "class_distribution": dict(Counter(labels)),
        "max_depth": best_settings[0],
        "min_samples_leaf": best_settings[1],
        "validation_accuracy": best_accuracy,
        "test_accuracy": test_accuracy,
    }


def load_model(path: str | Path):
    joblib, *_ = _imports()
    bundle = joblib.load(path)
    if tuple(bundle.get("features", ())) != FEATURE_NAMES:
        raise ValueError("model feature schema does not match current code")
    return bundle["model"]
