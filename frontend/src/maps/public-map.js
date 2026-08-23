// Public map of released records, with clustering and status filters.
import L from "leaflet";
import "leaflet.markercluster";
import { createMap, readConfig } from "./base.js";

function popupHtml(properties) {
  const lines = [`<strong>${properties.address}</strong>`];
  if (properties.property_type) lines.push(properties.property_type);
  if (properties.vacancy_status) lines.push(properties.vacancy_status);
  if (properties.condition) lines.push(properties.condition);
  if (properties.district) lines.push(properties.district);
  if (properties.description) lines.push(`<p class="mb-0">${properties.description}</p>`);
  return lines.join("<br>");
}

export function initPublicMap() {
  const element = document.getElementById("public-map");
  if (!element) return;

  const config = readConfig(element);
  const map = createMap(element, config);
  const cluster = L.markerClusterGroup();
  map.addLayer(cluster);

  const filter = document.getElementById("public-map-filter");
  let features = [];

  function render() {
    const onlyVacant = filter ? filter.checked : false;
    cluster.clearLayers();
    features
      .filter((feature) => !onlyVacant || feature.properties.is_vacant)
      .forEach((feature) => {
        const [lon, lat] = feature.geometry.coordinates;
        cluster.addLayer(L.marker([lat, lon]).bindPopup(popupHtml(feature.properties)));
      });
  }

  fetch(element.dataset.url, { headers: { Accept: "application/json" } })
    .then((response) => (response.ok ? response.json() : Promise.reject(response.status)))
    .then((data) => {
      features = data.features || [];
      render();
      const count = document.getElementById("public-map-count");
      if (count) count.textContent = features.length;
    })
    .catch(() => {
      const status = document.getElementById("public-map-status");
      if (status) status.hidden = false;
    });

  if (filter) filter.addEventListener("change", render);
}
