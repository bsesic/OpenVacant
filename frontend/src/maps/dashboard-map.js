// Administration map: the municipality's own records, filterable.
//
// Marker colour carries the two things staff scan for — whether the object is a
// confirmed vacancy, and whether its condition is critical.
import L from "leaflet";
import "leaflet.markercluster";
import { createMap, readConfig } from "./base.js";

function markerColour(properties) {
  if (properties.is_critical) return "#dc3545";
  if (properties.is_vacant) return "#0d6efd";
  return "#6c757d";
}

function popupHtml(properties) {
  const lines = [
    `<strong><a href="${properties.url}">${properties.reference}</a></strong>`,
    properties.address,
    `${properties.status} · ${properties.vacancy_status}`,
    properties.condition,
  ];
  if (properties.district) lines.push(properties.district);
  if (!properties.is_public) lines.push("<em>not published</em>");
  return lines.filter(Boolean).join("<br>");
}

export function initDashboardMap() {
  const element = document.getElementById("dashboard-map");
  if (!element) return;

  const config = readConfig(element);
  const map = createMap(element, config);
  const cluster = L.markerClusterGroup();
  map.addLayer(cluster);

  const filters = {
    status: document.getElementById("dashboard-filter-status"),
    condition: document.getElementById("dashboard-filter-condition"),
  };
  const status = document.getElementById("dashboard-map-status");

  function load() {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([name, field]) => {
      if (field && field.value) params.set(name, field.value);
    });
    const query = params.toString();
    fetch(query ? `${element.dataset.url}?${query}` : element.dataset.url, {
      headers: { Accept: "application/json" },
    })
      .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
      .then((data) => {
        cluster.clearLayers();
        (data.features || []).forEach((feature) => {
          const [lon, lat] = feature.geometry.coordinates;
          cluster.addLayer(
            L.circleMarker([lat, lon], {
              radius: 7,
              color: markerColour(feature.properties),
              fillColor: markerColour(feature.properties),
              fillOpacity: 0.7,
              weight: 1,
            }).bindPopup(popupHtml(feature.properties))
          );
        });
        if (status) status.hidden = true;
      })
      .catch(() => {
        if (status) status.hidden = false;
      });
  }

  Object.values(filters).forEach((field) => {
    if (field) field.addEventListener("change", load);
  });
  load();
}
