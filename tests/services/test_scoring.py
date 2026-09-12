"""Scoring, against worked examples.

SC-007 asks for scores verified across single-answer, multi-answer, blank, and
fully wrong cases. This is that table. It is the test whose failure would
otherwise produce no error at all, just wrong results nobody notices.
"""

from __future__ import annotations

import pytest

from app.services import scoring

# (question_id, points, correct_option_ids)
SINGLE = (1, 1, [10])          # one correct option
MULTI = (2, 2, [20, 21])       # two correct options, worth more
THIRD = (3, 1, [30])


# --------------------------------------------------------- one correct option


def test_the_right_single_answer_earns_its_points():
    assert scoring.score([SINGLE], {1: [10]}) == (1, 1)


def test_the_wrong_single_answer_earns_nothing():
    assert scoring.score([SINGLE], {1: [11]}) == (0, 1)


def test_selecting_two_where_one_is_correct_earns_nothing():
    """Adding a wrong option spoils it, even though the right one is there."""
    assert scoring.score([SINGLE], {1: [10, 11]}) == (0, 1)


# ------------------------------------------------------ several correct options


def test_all_of_the_correct_options_earns_the_points():
    assert scoring.score([MULTI], {2: [20, 21]}) == (2, 2)


def test_order_does_not_matter():
    assert scoring.score([MULTI], {2: [21, 20]}) == (2, 2)


def test_some_but_not_all_earns_nothing():
    """No partial credit. This is the case the spec names explicitly."""
    assert scoring.score([MULTI], {2: [20]}) == (0, 2)


def test_all_of_them_plus_a_wrong_one_earns_nothing():
    assert scoring.score([MULTI], {2: [20, 21, 22]}) == (0, 2)


def test_duplicates_in_the_selection_do_not_change_the_outcome():
    assert scoring.score([MULTI], {2: [20, 21, 21]}) == (2, 2)


# ------------------------------------------------------------------- blank


def test_an_unanswered_question_earns_nothing_but_still_counts_towards_the_total():
    assert scoring.score([SINGLE, MULTI], {1: [10]}) == (1, 3)


def test_an_attempt_with_no_answers_at_all_scores_zero():
    """A completed attempt, not an absent one."""
    assert scoring.score([SINGLE, MULTI, THIRD], {}) == (0, 4)


def test_an_empty_selection_is_the_same_as_not_answering():
    assert scoring.score([SINGLE], {1: []}) == (0, 1)


# -------------------------------------------------------------- fully wrong


def test_every_answer_wrong_scores_zero_out_of_the_total():
    assert scoring.score([SINGLE, MULTI, THIRD], {1: [11], 2: [22], 3: [31]}) == (0, 4)


def test_a_mixed_attempt_earns_exactly_what_it_should():
    earned, possible = scoring.score(
        [SINGLE, MULTI, THIRD], {1: [10], 2: [20], 3: [30]}
    )
    assert (earned, possible) == (2, 4), "1 for SINGLE, 0 for the partial MULTI, 1 for THIRD"


# ------------------------------------------------------------------ percentage


@pytest.mark.parametrize(
    "earned,possible,expected",
    [(0, 4, 0), (1, 4, 25), (2, 4, 50), (4, 4, 100), (1, 3, 33), (2, 3, 67)],
)
def test_the_percentage_is_of_what_was_available(earned, possible, expected):
    assert scoring.percentage(earned, possible) == expected


def test_a_test_with_no_points_scores_zero_rather_than_dividing_by_nothing():
    assert scoring.percentage(0, 0) == 0


# --------------------------------------------------------------- pass or fail


@pytest.mark.parametrize(
    "score_percent,mark,expected",
    [(80, 80, True), (81, 80, True), (79, 80, False), (100, 80, True), (0, 80, False)],
)
def test_the_mark_is_at_or_above(score_percent, mark, expected):
    assert scoring.passed(score_percent, mark) is expected


def test_a_test_with_no_pass_mark_has_no_outcome():
    """Different from failing: there is nothing to fail against."""
    assert scoring.passed(50, None) is None


def test_an_unscored_attempt_has_no_outcome():
    assert scoring.passed(None, 80) is None
