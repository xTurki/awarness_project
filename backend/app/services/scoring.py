"""Scoring. One function, no session, no clock, no I/O.

This is the part of the phase where being wrong is **silent**: nobody notices a
slightly wrong score, there is no exception and no crash, just a number that
does not match what somebody answered. It is pure so that a table of worked
examples is enough to prove it (research R5).

Exact match only. A question's points are earned when the selected set equals
the correct set: miss one correct option or add one wrong option and it scores
nothing. There is no partial credit (FR-027).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping


def score_question(correct_option_ids: Iterable[int], selected_option_ids: Iterable[int]) -> bool:
    """Whether this question is earned. Set comparison, one line."""
    return set(correct_option_ids) == set(selected_option_ids)


def score(
    questions: Iterable[tuple[int, int, Iterable[int]]],
    answers: Mapping[int, Iterable[int]],
) -> tuple[int, int]:
    """Return `(points_earned, points_possible)`.

    `questions` is `(question_id, points, correct_option_ids)` for every question
    in the attempt. `answers` maps a question id to what was selected. A question
    with no entry is unanswered and earns nothing, which is why an attempt left
    entirely blank scores zero rather than failing.
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
    """A score is a percentage of what was available.

    A test with no points available scores zero rather than dividing by nothing.
    """
    if points_possible <= 0:
        return 0
    return round(points_earned * 100 / points_possible)


def passed(score_percent: int | None, passing_score: int | None) -> bool | None:
    """Pass or fail against the test's mark.

    A test with no pass mark has no outcome, which is different from failing.
    """
    if score_percent is None or passing_score is None:
        return None
    return score_percent >= passing_score
