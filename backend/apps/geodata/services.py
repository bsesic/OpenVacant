"""Deriving a property's spatial context from the imported layers."""

from django.db import transaction
from django.utils import timezone

from apps.geodata.models import CATEGORY_TO_FLAG, CONTEXT_FLAGS, GeoFeature, SpatialContext


def matching_features(record, organization=None):
    """Active-layer features whose geometry contains the record's location."""
    if record.location is None:
        return GeoFeature.objects.none()
    return GeoFeature.objects.filter(
        layer__organization_id=organization.pk if organization else record.organization_id,
        layer__is_active=True,
        geometry__contains=record.location,
    ).select_related("layer")


@transaction.atomic
def refresh_context(record):
    """Recompute the record's spatial context and its derived flags.

    Returns the set of flags that are now true. A record without a location has
    no context: the flags are cleared rather than left stale, because a stale
    "heritage protected" is worse than none.
    """
    features = list(matching_features(record))
    feature_ids = {feature.pk for feature in features}

    SpatialContext.objects.filter(property=record).exclude(
        feature_id__in=feature_ids
    ).delete()
    for feature in features:
        SpatialContext.objects.get_or_create(property=record, feature=feature)

    active_flags = set()
    for feature in features:
        flag = CATEGORY_TO_FLAG.get(feature.layer.category)
        if flag:
            active_flags.add(flag)

    changed = []
    for flag in CONTEXT_FLAGS:
        value = flag in active_flags
        if getattr(record, flag) != value:
            setattr(record, flag, value)
            changed.append(flag)

    record.context_updated_at = timezone.now()
    record.save(update_fields=changed + ["context_updated_at", "updated_at"])
    return active_flags


def refresh_context_for_queryset(queryset):
    """Recompute the context for many records, returning how many changed."""
    updated = 0
    for record in queryset.iterator():
        before = {flag: getattr(record, flag) for flag in CONTEXT_FLAGS}
        refresh_context(record)
        if any(getattr(record, flag) != before[flag] for flag in CONTEXT_FLAGS):
            updated += 1
    return updated
