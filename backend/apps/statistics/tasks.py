from celery import shared_task


@shared_task
def take_daily_snapshots():
    """Store today's key figures for every municipality.

    Scheduled daily: the current numbers can be counted at any time, but the
    numbers as they stood last quarter cannot be reconstructed afterwards.
    """
    from apps.municipalities.models import Municipality
    from apps.statistics.services import take_snapshot

    taken = 0
    for municipality in Municipality.objects.select_related("organization"):
        take_snapshot(municipality.organization)
        taken += 1
    return taken
