"""Test scoring (pure functions).

A question scores only if the selected options exactly match the correct ones.
There is no partial credit.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def score_question(correct_option_ids: Iterable[int], selected_option_ids: Iterable[int]) -> bool:
    """True if the selected options exactly match the correct ones."""
    return set(correct_option_ids) == set(selected_option_ids)


def score(
    questions: Iterable[tuple[int, int, Iterable[int]]],
    answers: Mapping[int, Iterable[int]],
) -> tuple[int, int]:
    """Return `(points_earned, points_possible)`.

    `questions` is a list of `(question_id, points, correct_option_ids)`.
    `answers` maps question id to selected option ids; unanswered scores 0.
    """
    earned = 0
    possible = 0

    for question_id, points, correct_option_ids in questions:
        possible += points
        selected = answers.get(question_id)
        if selected is None:
            continue
        if score_question(correct_option_ids, selected):
            earned += points

    return earned, possible


def percentage(points_earned: int, points_possible: int) -> int:
    """Score as a percentage (0 if there are no points)."""
    if points_possible <= 0:
        return 0
    return round(points_earned * 100 / points_possible)


def passed(score_percent: int | None, passing_score: int | None) -> bool | None:
    """True/False against the pass mark, or None if there is no pass mark."""
    if score_percent is None or passing_score is None:
        return None
    return score_percent >= passing_score
