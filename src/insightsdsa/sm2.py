"""SM-2 spaced repetition algorithm (extracted from app.py)."""

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
    # 1. HANDLE "FORGOT" (Reset Logic)
    if quality < 3:
        new_reps = 0
        new_interval = 1  # Reset to 1 day (Review tomorrow)
        new_ease = current_ease  # Keep ease factor same

    # 2. HANDLE SUCCESS (Growth Logic)
    else:
        new_reps = repetitions + 1

        # Standard SM-2 Intervals
        if new_reps == 1:
            new_interval = 1
        elif new_reps == 2:
            new_interval = 6
        else:
            # The Magic Formula: Previous Interval * Ease Factor
            new_interval = int(current_interval * current_ease)

        # Update Ease Factor
        new_ease = current_ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))

        # Cap the Ease Factor
        if new_ease < 1.3:
            new_ease = 1.3

    # 3. CALCULATE DATE
    next_review_date = date.today() + timedelta(days=new_interval)

    return new_interval, new_ease, new_reps, next_review_date
