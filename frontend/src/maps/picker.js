// Marker picker for the citizen report form.
//
// The form also works without this: a reporter who cannot use the map (no
// JavaScript, screen reader, older phone) can type an address instead, and the
// server accepts either. The map is an aid, not the only way in.
import L from "leaflet";
import { createMap, readConfig } from "./base.js";

export function initPicker() {
  const element = document.getElementById("report-map");
  if (!element) return;

  const config = readConfig(element);
  const map = createMap(element, config);
  const latitudeField = document.getElementById("id_latitude");
  const longitudeField = document.getElementById("id_longitude");
  const readout = document.getElementById("report-map-readout");
  let marker = null;

  function place(latlng) {
    if (marker) {
      marker.setLatLng(latlng);
    } else {
      marker = L.marker(latlng, { draggable: true }).addTo(map);
      marker.on("dragend", () => place(marker.getLatLng()));
    }
    latitudeField.value = latlng.lat.toFixed(6);
    longitudeField.value = latlng.lng.toFixed(6);
    if (readout) {
      readout.textContent = `${latlng.lat.toFixed(5)}, ${latlng.lng.toFixed(5)}`;
    }
  }

  map.on("click", (event) => place(event.latlng));

  // Restore a previously chosen marker when the form comes back with errors.
  if (latitudeField.value && longitudeField.value) {
    place(L.latLng(parseFloat(latitudeField.value), parseFloat(longitudeField.value)));
  }

  const locateButton = document.getElementById("report-map-locate");
  if (locateButton && navigator.geolocation) {
    locateButton.addEventListener("click", () => {
      navigator.geolocation.getCurrentPosition((position) => {
        const latlng = L.latLng(position.coords.latitude, position.coords.longitude);
        map.setView(latlng, 18);
        place(latlng);
      });
    });
  } else if (locateButton) {
    locateButton.hidden = true;
  }
}
