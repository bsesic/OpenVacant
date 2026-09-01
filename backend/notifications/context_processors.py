def notifications(request):
    """Expose the unread notification count to templates (navbar badge)."""
    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return {}
    return {"unread_notifications_count": user.notifications.filter(unread=True).count()}
