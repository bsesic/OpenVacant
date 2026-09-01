"""Address lookup.

Geocoding is deliberately behind a small interface. The public Nominatim service
is fine for a municipality's volume but comes with conditions — a real contact
address and about one request per second — and some municipalities will want to
point this at their own instance or their state's service instead.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.contrib.gis.geos import Point


class GeocodingUnavailable(Exception):
    """Raised when the configured provider cannot answer."""


class BaseGeocoder:
    def search(self, query, municipality=None, limit=5):
        raise NotImplementedError

    def reverse(self, point):
        raise NotImplementedError


class NullGeocoder(BaseGeocoder):
    """Used when geocoding is switched off. Answers nothing, quietly."""

    def search(self, query, municipality=None, limit=5):
        return []

    def reverse(self, point):
        return None


class NominatimGeocoder(BaseGeocoder):
    """OpenStreetMap's Nominatim service."""

    def __init__(self, endpoint=None, user_agent=None, country_codes=None, timeout=None):
        self.endpoint = (endpoint or settings.GEOCODER_ENDPOINT).rstrip("/")
        self.user_agent = user_agent or settings.GEOCODER_USER_AGENT
        self.country_codes = country_codes or settings.GEOCODER_COUNTRY_CODES
        self.timeout = timeout or settings.GEOCODER_TIMEOUT

    def _request(self, path, params):
        url = f"{self.endpoint}/{path}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as error:
            raise GeocodingUnavailable(str(error)) from error

    def search(self, query, municipality=None, limit=5):
        """Look up an address, biased towards the municipality when known."""
        if not query:
            return []
        terms = query
        if municipality is not None and municipality.name.lower() not in query.lower():
            # Without this, "Bahnhofstraße 12" finds the wrong town entirely.
            terms = f"{query}, {municipality.name}"
        params = {
            "q": terms,
            "format": "jsonv2",
            "addressdetails": 1,
            "limit": limit,
        }
        if self.country_codes:
            params["countrycodes"] = self.country_codes
        return [self._normalise(entry) for entry in self._request("search", params)]

    def reverse(self, point):
        if point is None:
            return None
        params = {
            "lat": point.y,
            "lon": point.x,
            "format": "jsonv2",
            "addressdetails": 1,
        }
        result = self._request("reverse", params)
        if not result or "error" in result:
            return None
        return self._normalise(result)

    @staticmethod
    def _normalise(entry):
        address = entry.get("address", {})
        return {
            "label": entry.get("display_name", ""),
            "latitude": float(entry["lat"]),
            "longitude": float(entry["lon"]),
            "street": address.get("road", ""),
            "house_number": address.get("house_number", ""),
            "postal_code": address.get("postcode", ""),
            "city": address.get("city")
            or address.get("town")
            or address.get("village")
            or address.get("municipality", ""),
        }


def get_geocoder():
    """The configured geocoder for this instance."""
    provider = (settings.GEOCODER_PROVIDER or "none").lower()
    if provider == "nominatim":
        return NominatimGeocoder()
    return NullGeocoder()


def point_from_result(result):
    """A geometry for one search result."""
    if not result:
        return None
    return Point(result["longitude"], result["latitude"], srid=4326)
