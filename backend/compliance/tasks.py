from celery import shared_task


@shared_task
def apply_retention():
    """Apply the retention rules on a schedule.

    Scheduled rather than manual: a deletion concept that depends on somebody
    remembering to run it is not a concept.
    """
    from compliance import retention

    return retention.run_all()
