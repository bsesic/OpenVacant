from apps.municipalities.resolution import map_defaults


def municipality(request):
    """Expose the current municipality, its branding and the map defaults.

    Templates use this for the white label: the name in the navigation, the
    colours, the logo and the legal texts all come from the municipality, so
    adapting an instance needs no code change.
    """
    current = getattr(request, "municipality", None)
    # SimpleLazyObject wrapping None is falsy, so this also covers "unresolved".
    if not current:
        return {
            "municipality": None,
            "municipality_name": None,
            "enabled_modules": set(),
            "map_defaults": map_defaults(),
        }
    return {
        "municipality": current,
        "municipality_name": current.name,
        "enabled_modules": current.enabled_modules(),
        "map_defaults": map_defaults(current),
    }
