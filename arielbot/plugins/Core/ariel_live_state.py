LIVE_RESTART_SUPPRESSION_SECONDS = 5 * 60


def should_suppress_live_push(last_live_end_time: int | None, detected_at: int) -> bool:
    return (
        last_live_end_time is not None
        and 0 <= detected_at - last_live_end_time < LIVE_RESTART_SUPPRESSION_SECONDS
    )
