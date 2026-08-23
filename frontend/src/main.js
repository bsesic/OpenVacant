// Theme entry point: Bootstrap JS (dropdowns, modals, ...) + project styles.
import "bootstrap";
import "./styles/main.scss";

// Maps initialise themselves only when their container is on the page, so every
// page pays for the import once and nothing runs where it is not needed.
import { initPicker } from "./maps/picker.js";
import { initPublicMap } from "./maps/public-map.js";
import { initStaticMarkers } from "./maps/marker.js";

function boot() {
  initPicker();
  initPublicMap();
  initStaticMarkers();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
