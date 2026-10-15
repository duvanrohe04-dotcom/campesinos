/* Mapas con Leaflet + OpenStreetMap, cargados solo cuando hacen falta (pensado para conexiones lentas).
   - #map: vista de mapa del listado con marcadores agrupados y tarjeta emergente.
   - #listing-map: ubicación aproximada de un anuncio (círculo de ~1 km).
   - #map-picker: el vendedor marca un punto aproximado al publicar. */
(function () {
  var LEAFLET = 'https://unpkg.com/leaflet@1.9.4/dist/';
  var CLUSTER = 'https://unpkg.com/leaflet.markercluster@1.5.3/dist/';
  var TILES = 'https://tile.openstreetmap.org/{z}/{x}/{y}.png';
  var ATTRIBUTION = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>';
  var loading = null;
  // Sin límite de tiempo, un GPS apagado o lento deja el botón esperando para siempre. Se acepta una ubicación de hace 5 min.
  var GEO_OPTIONS = { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 };

  function addCss(href) {
    var l = document.createElement('link'); l.rel = 'stylesheet'; l.href = href; document.head.appendChild(l);
  }
  function addScript(src) {
    return new Promise(function (resolve, reject) {
      var s = document.createElement('script'); s.src = src; s.onload = resolve; s.onerror = reject; document.head.appendChild(s);
    });
  }
  function loadLeaflet(withCluster) {
    if (window.L && (!withCluster || window.L.markerClusterGroup)) return Promise.resolve();
    if (!loading) {
      addCss(LEAFLET + 'leaflet.css');
      loading = addScript(LEAFLET + 'leaflet.js');
    }
    var p = loading;
    if (withCluster) {
      p = p.then(function () {
        addCss(CLUSTER + 'MarkerCluster.css'); addCss(CLUSTER + 'MarkerCluster.Default.css');
        return addScript(CLUSTER + 'leaflet.markercluster.js');
      });
    }
    return p;
  }
  function baseMap(el, center, zoom) {
    var map = window.L.map(el, { scrollWheelZoom: false }).setView(center, zoom);
    window.L.tileLayer(TILES, { maxZoom: 18, attribution: ATTRIBUTION }).addTo(map);
    return map;
  }
  function fail(el, msg) { el.innerHTML = ''; var p = document.createElement('p'); p.className = 'p-4 text-center'; p.textContent = msg; el.appendChild(p); }
  function roundPoint(v) { return Math.round(v * 100) / 100; }

  /* ---------- Mapa del listado ---------- */
  var listMap = document.getElementById('map');
  if (listMap) {
    var center = JSON.parse(listMap.getAttribute('data-center'));
    loadLeaflet(true).then(function () {
      var map = baseMap(listMap, center, 11);
      var near = listMap.getAttribute('data-near');
      if (near) {
        var parts = near.split(',').map(Number), radius = Number(listMap.getAttribute('data-radius')) * 1000;
        window.L.circle(parts, { radius: radius, color: '#2E5D22', fillOpacity: 0.06 }).addTo(map);
        window.L.marker(parts).addTo(map).bindPopup('Tu ubicación');
        map.fitBounds(window.L.circle(parts, { radius: radius }).getBounds());
      }
      return fetch(listMap.getAttribute('data-url')).then(function (r) { return r.json(); }).then(function (data) {
        var cluster = window.L.markerClusterGroup();
        data.points.forEach(function (p) {
          var marker = window.L.marker([p.lat, p.lng]);
          marker.bindPopup(function () { return popupNode(p); }, { minWidth: 200 });
          cluster.addLayer(marker);
        });
        map.addLayer(cluster);
        var counter = document.getElementById('map-count');
        if (counter) counter.textContent = data.points.length + (data.points.length === 1 ? ' anuncio en el mapa' : ' anuncios en el mapa');
        if (!near && data.points.length) map.fitBounds(cluster.getBounds().pad(0.15), { maxZoom: 13 });
      });
    }).catch(function () { fail(listMap, 'No pudimos cargar el mapa. Revisa tu conexión o mira los anuncios en lista.'); });
  }
  function popupNode(p) {
    var box = document.createElement('div');
    if (p.image) { var img = document.createElement('img'); img.src = p.image; img.alt = ''; img.style.cssText = 'width:100%;border-radius:8px;margin-bottom:6px'; box.appendChild(img); }
    var link = document.createElement('a'); link.href = p.url; link.textContent = p.title; link.style.cssText = 'font-weight:800;display:block'; box.appendChild(link);
    var price = document.createElement('div'); price.textContent = p.price + (p.unit ? ' / ' + p.unit : ''); price.style.cssText = 'font-weight:800;color:#2E5D22;font-size:1.1em'; box.appendChild(price);
    var place = document.createElement('div'); place.textContent = p.place + (p.exact ? '' : ' (zona aproximada)'); place.style.fontSize = '0.85em'; box.appendChild(place);
    return box;
  }

  /* ---------- Mapa dentro del anuncio (se carga al verse) ---------- */
  var card = document.getElementById('listing-map');
  if (card) {
    var start = function () {
      loadLeaflet(false).then(function () {
        var pt = [Number(card.getAttribute('data-lat')), Number(card.getAttribute('data-lng'))];
        var map = baseMap(card, pt, 13);
        window.L.circle(pt, { radius: 1000, color: '#B64A24', fillOpacity: 0.15 }).addTo(map);
      }).catch(function () { fail(card, 'No pudimos cargar el mapa.'); });
    };
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) { if (entries[0].isIntersecting) { io.disconnect(); start(); } });
      io.observe(card);
    } else { start(); }
  }

  /* ---------- Selector de punto al publicar ---------- */
  var picker = document.getElementById('map-picker');
  if (picker) {
    var latEl = document.getElementById('f-lat'), lngEl = document.getElementById('f-lng');
    var munEl = document.getElementById('f-municipality_id');
    var pickMap = null, marker = null, circle = null;
    var defaultCenter = JSON.parse(picker.getAttribute('data-center'));

    function municipalityCenter() {
      var opt = munEl && munEl.options[munEl.selectedIndex];
      var lat = opt && parseFloat(opt.getAttribute('data-lat')), lng = opt && parseFloat(opt.getAttribute('data-lng'));
      return (isFinite(lat) && isFinite(lng)) ? [lat, lng] : defaultCenter;
    }
    function setPoint(lat, lng, move) {
      lat = roundPoint(lat); lng = roundPoint(lng);
      latEl.value = lat; lngEl.value = lng;
      if (!pickMap) return;
      if (marker) { marker.setLatLng([lat, lng]); circle.setLatLng([lat, lng]); }
      else {
        marker = window.L.marker([lat, lng]).addTo(pickMap);
        circle = window.L.circle([lat, lng], { radius: 1000, color: '#B64A24', fillOpacity: 0.15 }).addTo(pickMap);
      }
      if (move) pickMap.setView([lat, lng], 13);
      document.getElementById('map-picker-status').textContent = 'Punto marcado (aproximado, ~1 km).';
    }
    function clearPoint() {
      latEl.value = ''; lngEl.value = '';
      if (marker) { pickMap.removeLayer(marker); pickMap.removeLayer(circle); marker = circle = null; }
      document.getElementById('map-picker-status').textContent = 'Sin punto marcado. Es opcional.';
    }
    function initPicker() {
      if (pickMap) { pickMap.invalidateSize(); return; }
      loadLeaflet(false).then(function () {
        pickMap = baseMap(picker, municipalityCenter(), 12);
        pickMap.on('click', function (e) { setPoint(e.latlng.lat, e.latlng.lng, false); });
        if (latEl.value && lngEl.value) setPoint(parseFloat(latEl.value), parseFloat(lngEl.value), true);
      }).catch(function () { fail(picker, 'No pudimos cargar el mapa. Puedes publicar sin marcar el punto.'); });
    }
    document.addEventListener('step-shown', function (e) { if (e.detail === 4) initPicker(); });
    var step4 = document.querySelector('[data-step="4"]');
    if (step4 && !step4.classList.contains('step-hidden')) initPicker();
    if (munEl) munEl.addEventListener('change', function () { if (pickMap && !marker) pickMap.setView(municipalityCenter(), 12); });
    document.getElementById('map-picker-clear').addEventListener('click', clearPoint);
    var here = document.getElementById('map-picker-here');
    if (!navigator.geolocation) { here.hidden = true; }
    here.addEventListener('click', function () {
      document.getElementById('map-picker-status').textContent = 'Buscando tu ubicación…';
      navigator.geolocation.getCurrentPosition(function (pos) {
        initPicker();
        setPoint(pos.coords.latitude, pos.coords.longitude, true);
      }, function () { document.getElementById('map-picker-status').textContent = 'No pudimos ver tu ubicación. Toca el mapa para marcar el punto.'; }, GEO_OPTIONS);
    });
  }

  /* ---------- Botones «Cerca de mí» ---------- */
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-near-url]');
    if (!btn) return;
    if (!navigator.geolocation) { alert('Tu celular no permite saber dónde estás.'); return; }
    btn.disabled = true;
    navigator.geolocation.getCurrentPosition(function (pos) {
      var u = new URL(btn.getAttribute('data-near-url'), window.location.origin);
      u.searchParams.set('near', pos.coords.latitude.toFixed(4) + ',' + pos.coords.longitude.toFixed(4));
      u.searchParams.set('radio', btn.getAttribute('data-radius'));
      u.searchParams.delete('page');
      window.location.href = u.toString();
    }, function () { btn.disabled = false; alert('No pudimos ver tu ubicación. Revisa que el permiso de ubicación y el GPS estén activados.'); }, GEO_OPTIONS);
  });
})();
