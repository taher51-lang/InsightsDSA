"""Unit tests for SM-2 scheduling."""

from datetime import date, timedelta

from insightsdsa.sm2 import sm2_algorithm


def test_sm2_forgot_resets():
    ni, ne, nr, nd = sm2_algorithm(quality=0, current_interval=10, current_ease=2.5, repetitions=5)
    assert nr == 0
    assert ni == 1
    assert ne == 2.5
    assert nd == date.today() + timedelta(days=1)


def test_sm2_first_two_success_intervals():
    ni, ne, nr, _ = sm2_algorithm(quality=4, current_interval=1, current_ease=2.5, repetitions=0)
    assert nr == 1
    assert ni == 1
    ni2, _, nr2, _ = sm2_algorithm(quality=4, current_interval=ni, current_ease=ne, repetitions=nr)
    assert nr2 == 2
    assert ni2 == 6


def test_sm2_ease_floor():
    _, ne, _, _ = sm2_algorithm(quality=3, current_interval=6, current_ease=1.25, repetitions=2)
    assert ne >= 1.3
