// Shared Leaflet setup. The tile URL and attribution come from the server so a
// municipality can point the map at its own tile service without a rebuild.
import L from "leaflet";

export function readConfig(element) {
  return {
    latitude: parseFloat(element.dataset.latitude),
    longitude: parseFloat(element.dataset.longitude),
    zoom: parseInt(element.dataset.zoom, 10),
    tileUrl: element.dataset.tileUrl,
    attribution: element.dataset.tileAttribution || "",
  };
}

export function createMap(element, config) {
  const map = L.map(element).setView([config.latitude, config.longitude], config.zoom);
  L.tileLayer(config.tileUrl, {
    attribution: config.attribution,
    maxZoom: 19,
  }).addTo(map);
  return map;
}
