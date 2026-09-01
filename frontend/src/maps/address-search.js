// Address search on the report form.
//
// Queries go through our own server, not the geocoder directly: the upstream
// service's terms need a real contact address, and the proxy is the only place
// the request rate can be held down. Typing is debounced for the same reason.
export function initAddressSearch() {
  const input = document.getElementById("address-search");
  if (!input) return;

  const results = document.getElementById("address-search-results");
  const endpoint = input.dataset.url;
  let timer = null;
  let controller = null;

  function fill(result) {
    const set = (id, value) => {
      const field = document.getElementById(id);
      if (field && value) field.value = value;
    };
    set("id_street", result.street);
    set("id_house_number", result.house_number);
    set("id_postal_code", result.postal_code);
    set("id_city", result.city);
    set("id_latitude", result.latitude.toFixed(6));
    set("id_longitude", result.longitude.toFixed(6));
    results.innerHTML = "";
    // Let the map pick up the new coordinates.
    document.dispatchEvent(
      new CustomEvent("openvacant:location", {
        detail: { latitude: result.latitude, longitude: result.longitude },
      })
    );
  }

  function render(entries) {
    results.innerHTML = "";
    entries.forEach((entry) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "list-group-item list-group-item-action small";
      item.textContent = entry.label;
      item.addEventListener("click", () => fill(entry));
      results.appendChild(item);
    });
  }

  input.addEventListener("input", () => {
    const query = input.value.trim();
    window.clearTimeout(timer);
    if (query.length < 3) {
      results.innerHTML = "";
      return;
    }
    timer = window.setTimeout(() => {
      if (controller) controller.abort();
      controller = new AbortController();
      fetch(`${endpoint}?q=${encodeURIComponent(query)}`, {
        headers: { Accept: "application/json" },
        signal: controller.signal,
      })
        .then((response) => (response.ok ? response.json() : { results: [] }))
        .then((data) => render(data.results || []))
        .catch(() => {
          // An aborted or failed lookup is not worth interrupting the form for;
          // the reporter can always type the address or use the map.
        });
    }, 400);
  });
}
