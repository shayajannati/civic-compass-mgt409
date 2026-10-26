"use strict";
// Small ZIP-area map. Display only: it never affects routing, never uses browser
// geolocation, and only the 5-digit ZIP is sent (to this app). Map tiles come from
// OpenStreetMap; the boundary is the Census ZCTA polygon when available.
(() => {
  const input = document.querySelector("input[name=zip]");
  const wrap = document.getElementById("zip-map-wrap");
  const caption = document.getElementById("zip-map-label");
  if (!input || !wrap) return;
  let map = null, layer = null, last = "";

  function ensureMap() {
    if (map || typeof L === "undefined") return map;
    map = L.map("zip-map", { scrollWheelZoom: false, attributionControl: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 18,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors · ZIP area: U.S. Census Bureau',
    }).addTo(map);
    return map;
  }

  function setCaption(html) { caption.innerHTML = html; }
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function update() {
    const z = input.value.trim();
    if (z === last) return;
    last = z;
    if (!/^\d{5}$/.test(z)) {
      wrap.hidden = z.length !== 5 ? true : false;
      if (z.length === 5) setCaption("Please enter a valid 5-digit ZIP code.");
      return;
    }
    let d;
    try {
      const r = await fetch(`/api/zip/${z}`);
      d = await r.json();
    } catch { wrap.hidden = true; return; }
    if (z !== input.value.trim()) return; // user kept typing
    wrap.hidden = false;
    if (!d.found) {
      wrap.classList.add("no-map");
      setCaption(`ZIP ${esc(z)} was not found in Census ZIP Code Tabulation Areas. Please check it.`);
      return;
    }
    const note = `<strong>${esc(d.label)}</strong> · approximate ZIP-code area, not your exact address or district.` +
      (d.ambiguity.length ? ` <span class="map-warn">${esc(d.ambiguity.join(" "))} We'll ask for a street address before naming those officials.</span>` : "");
    const m = ensureMap();
    if (!m) { // Leaflet unavailable (offline): keep the label, skip the map
      wrap.classList.add("no-map");
      setCaption(note + " <span class='muted'>(Map unavailable right now.)</span>");
      return;
    }
    wrap.classList.remove("no-map");
    if (layer) { m.removeLayer(layer); layer = null; }
    if (d.boundary) {
      layer = L.geoJSON(d.boundary, { style: { color: "#653D48", weight: 2, fillColor: "#BB6D60", fillOpacity: 0.12 } }).addTo(m);
      m.invalidateSize();
      m.fitBounds(layer.getBounds(), { padding: [12, 12] });
    } else {
      layer = L.circleMarker([d.lat, d.lon], { radius: 7, color: "#653D48", fillColor: "#BB6D60", fillOpacity: 0.8 }).addTo(m);
      m.invalidateSize();
      m.setView([d.lat, d.lon], 12);
    }
    setCaption(note);
  }

  let t = null;
  input.addEventListener("input", () => { clearTimeout(t); t = setTimeout(update, 250); });
  // example chips fill the ZIP programmatically
  document.addEventListener("click", (e) => { if (e.target.closest("[data-example]")) setTimeout(update, 50); });
})();
