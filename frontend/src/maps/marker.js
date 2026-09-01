// Read-only map showing a single position, used on the report detail page.
import L from "leaflet";
import { createMap, readConfig } from "./base.js";

export function initStaticMarkers() {
  document.querySelectorAll("[data-static-marker]").forEach((element) => {
    const config = readConfig(element);
    const latitude = parseFloat(element.dataset.markerLatitude);
    const longitude = parseFloat(element.dataset.markerLongitude);
    if (Number.isNaN(latitude) || Number.isNaN(longitude)) return;

    // Centre on the marker rather than the municipality: the point is to show
    // where this one object is.
    const map = createMap(element, { ...config, latitude, longitude });
    L.marker([latitude, longitude]).addTo(map);
    map.scrollWheelZoom.disable();
  });
}
