"""SM-2 spaced repetition interval calculation (used by review scheduling)."""

from datetime import date, timedelta


def sm2_algorithm(quality, current_interval, current_ease, repetitions):
    """
    Inputs:
        quality: 0 (Forgot), 3 (Hard), 4 (Good), 5 (Easy)
        current_interval: Days since last review
        current_ease: Difficulty multiplier (default 2.5)
        repetitions: How many times successfully reviewed in a row

    Returns:
        (new_interval, new_ease, new_repetitions, next_review_date)
    """
    if quality < 3:
        new_reps = 0
        new_interval = 1
        new_ease = current_ease
    else:
        new_reps = repetitions + 1
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 6
        else:
            new_interval = int(current_interval * current_ease)
        new_ease = current_ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if new_ease < 1.3:
            new_ease = 1.3

    next_review_date = date.today() + timedelta(days=new_interval)
    return new_interval, new_ease, new_reps, next_review_date
