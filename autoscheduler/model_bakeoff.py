"""Equal-budget regression tuning for future real policy-cost labels."""

from __future__ import annotations

import itertools
import math
from typing import Any, Callable, Iterable


ScoreFunction = Callable[[list[dict[str, Any]], list[float]], float]


def candidate_configurations(models: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Expand frozen model grids, capped equally by the configured family budget."""
    maximum = models["maximum_configurations_per_family"]
    candidates = {}
    for family in models["simplicity_order"]:
        grid = models["families"][family]
        keys = tuple(grid)
        settings = [dict(zip(keys, values)) for values in itertools.product(*(grid[key] for key in keys))]
        candidates[family] = settings[:maximum]
    return candidates


def _new_model(family: str, settings: dict[str, Any], random_state: int):
    from sklearn.dummy import DummyRegressor
    from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeRegressor

    if family == "Dummy":
        return DummyRegressor(**settings)
    if family == "Ridge":
        return make_pipeline(StandardScaler(), Ridge(**settings))
    if family == "Decision Tree":
        return DecisionTreeRegressor(**settings, random_state=random_state)
    if family == "Random Forest":
        return RandomForestRegressor(**settings, random_state=random_state, n_jobs=1)
    if family == "Histogram Gradient Boosting":
        return HistGradientBoostingRegressor(**settings, random_state=random_state)
    raise ValueError(f"unknown model family: {family}")


def _matrix(rows: Iterable[dict[str, Any]], feature_names: tuple[str, ...], target: str) -> tuple[list[dict[str, Any]], list[list[float]], list[float]]:
    parsed_rows = list(rows)
    matrix, targets = [], []
    for row_number, row in enumerate(parsed_rows, 1):
        try:
            values = [float(row[name]) for name in feature_names]
            value = float(row[target])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError(f"row {row_number} requires numeric {target} and all configured features") from error
        if not all(math.isfinite(item) for item in [*values, value]):
            raise ValueError(f"row {row_number} contains a non-finite feature or {target}")
        matrix.append(values)
        targets.append(value)
    if not parsed_rows:
        raise ValueError("bake-off split cannot be empty")
    return parsed_rows, matrix, targets


def _is_preferred(candidate: dict[str, Any], incumbent: dict[str, Any] | None, simplicity: tuple[str, ...]) -> bool:
    if incumbent is None:
        return True
    scale = max(abs(candidate["validation_score"]), abs(incumbent["validation_score"]), 1e-12)
    if abs(candidate["validation_score"] - incumbent["validation_score"]) <= scale * 0.005:
        return simplicity.index(candidate["family"]) < simplicity.index(incumbent["family"])
    return candidate["validation_score"] < incumbent["validation_score"]


def run_bakeoff(
    train_rows: Iterable[dict[str, Any]], validation_rows: Iterable[dict[str, Any]],
    test_rows: Iterable[dict[str, Any]], feature_names: tuple[str, ...], target: str,
    models: dict[str, Any], random_state: int, validation_score: ScoreFunction,
) -> dict[str, Any]:
    """Tune candidates on a caller-defined scheduler score; test rows remain sealed until selection."""
    train_rows, train_x, train_y = _matrix(train_rows, feature_names, target)
    validation_rows, validation_x, _ = _matrix(validation_rows, feature_names, target)
    test_rows, test_x, _ = _matrix(test_rows, feature_names, target)
    simplicity = tuple(models["simplicity_order"])
    family_results: dict[str, list[dict[str, Any]]] = {}
    selected = None
    for family, settings_list in candidate_configurations(models).items():
        results = []
        for settings in settings_list:
            model = _new_model(family, settings, random_state).fit(train_x, train_y)
            score = float(validation_score(validation_rows, list(model.predict(validation_x))))
            if not math.isfinite(score):
                raise ValueError("validation score must be finite")
            candidate = {"family": family, "settings": settings, "validation_score": score}
            results.append(candidate)
            if _is_preferred(candidate, selected, simplicity):
                selected = candidate
        family_results[family] = results

    final_model = _new_model(selected["family"], selected["settings"], random_state)
    final_model.fit(train_x + validation_x, train_y + [float(row[target]) for row in validation_rows])
    return {
        "selection_basis": "caller_supplied_validation_scheduler_score",
        "tie_margin_fraction": 0.005,
        "maximum_configurations_per_family": models["maximum_configurations_per_family"],
        "families": family_results,
        "selected": {
            **selected,
            "test_score": float(validation_score(test_rows, list(final_model.predict(test_x)))),
        },
    }
