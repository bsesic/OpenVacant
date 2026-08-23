from celery import shared_task


@shared_task
def refresh_property_context(property_id):
    """Recompute one record's spatial context off-request.

    Context resolution is a spatial query against every active layer, which is
    too slow to run while somebody waits for a form to save.
    """
    from apps.geodata.services import refresh_context
    from apps.properties.models import Property

    record = Property.objects.filter(pk=property_id).first()
    if record is None:
        return None
    flags = refresh_context(record)
    return sorted(flags)


@shared_task
def refresh_organization_context(organization_id):
    """Recompute the context for a whole municipality after a layer import."""
    from apps.geodata.services import refresh_context_for_queryset
    from apps.properties.models import Property

    records = Property.objects.filter(organization_id=organization_id)
    return refresh_context_for_queryset(records)
