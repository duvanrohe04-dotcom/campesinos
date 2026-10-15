/* Asistente de publicación: pasos, categoría por tarjetas, fotos (cámara/galería, compresión, orden) y borrador automático. */
(function () {
  var form = document.getElementById('pub-form');
  if (!form) return;

  var STEP_NAMES = ['Qué ofreces', 'Detalles', 'Fotos', 'Precio y lugar'];
  var step = parseInt(form.getAttribute('data-start-step'), 10) || 1;
  var steps = Array.prototype.slice.call(form.querySelectorAll('[data-step]'));
  var bar = form.querySelectorAll('#step-bar li');
  var label = document.getElementById('step-label');
  var btnBack = document.getElementById('btn-back');
  var btnNext = document.getElementById('btn-next');
  var btnSubmit = document.getElementById('btn-submit');

  /* ---------- Categoría → muestra/oculta bloques [data-root] ---------- */
  function currentRoot() {
    var r = form.querySelector('input[name="root_id"]:checked');
    return r ? r.value : null;
  }
  function syncRoot() {
    var root = currentRoot();
    form.querySelectorAll('[data-root]').forEach(function (fs) {
      var on = fs.getAttribute('data-root') === root;
      fs.hidden = !on;
      fs.disabled = !on; // los campos deshabilitados no se envían
    });
    var r = form.querySelector('input[name="root_id"]:checked');
    document.getElementById('ica-notice').classList.toggle('hidden', !(r && r.getAttribute('data-ica')));
  }
  form.querySelectorAll('input[name="root_id"]').forEach(function (r) {
    r.addEventListener('change', function () {
      syncRoot();
      var first = form.querySelector('fieldset[data-root="' + currentRoot() + '"] input[name="category_id"]');
      var any = form.querySelector('fieldset[data-root="' + currentRoot() + '"] input[name="category_id"]:checked');
      if (first && !any) { /* deja que la persona elija el tipo */ }
    });
  });

  /* ---------- Pasos ---------- */
  function showStep(n) {
    step = Math.max(1, Math.min(4, n));
    steps.forEach(function (s) { s.classList.toggle('step-hidden', parseInt(s.getAttribute('data-step'), 10) !== step); });
    bar.forEach(function (li, i) {
      li.classList.toggle('bg-primary-700', i < step);
      li.classList.toggle('bg-tierra-200', i >= step);
    });
    label.textContent = 'Paso ' + step + ' de 4 · ' + STEP_NAMES[step - 1];
    btnBack.style.visibility = step === 1 ? 'hidden' : 'visible';
    btnNext.classList.toggle('hidden', step === 4);
    btnSubmit.classList.toggle('hidden', step !== 4);
    window.scrollTo(0, 0);  // sin objeto de opciones: Safari antiguo no lo entiende
    document.dispatchEvent(new CustomEvent('step-shown', { detail: step }));
  }

  function clearErrors(scope) {
    scope.querySelectorAll('.js-err').forEach(function (e) { e.remove(); });
    scope.querySelectorAll('.input-error').forEach(function (e) { e.classList.remove('input-error'); });
  }
  function addError(el, msg) {
    var p = document.createElement('p');
    p.className = 'error-text js-err'; p.setAttribute('role', 'alert'); p.textContent = msg;
    (el.closest('fieldset, div') || el.parentNode).appendChild(p);
    if (el.classList) el.classList.add('input-error');
  }

  function validateStep(n) {
    var sec = form.querySelector('[data-step="' + n + '"]');
    clearErrors(sec);
    var ok = true, firstBad = null;
    function bad(el, msg) { ok = false; addError(el, msg); if (!firstBad) firstBad = el; }

    if (n === 1) {
      if (!form.querySelector('input[name="ad_type"]:checked')) bad(sec.querySelector('[data-req-group="ad_type"]'), 'Elige qué quieres hacer.');
      if (!currentRoot()) bad(document.getElementById('root-grid'), 'Elige qué producto es.');
      else if (!form.querySelector('input[name="category_id"]:checked:not(:disabled)')) {
        bad(form.querySelector('fieldset[data-root="' + currentRoot() + '"]'), 'Elige el tipo exacto.');
      }
    }
    sec.querySelectorAll('input[data-req], select[data-req]').forEach(function (el) {
      if (el.closest('fieldset:disabled')) return;
      if (!el.value.trim()) bad(el, 'Este dato es obligatorio.');
    });
    sec.querySelectorAll('div[data-req]').forEach(function (g) {
      if (g.closest('fieldset:disabled')) return;
      var radios = g.querySelectorAll('input[type="radio"]');
      if (radios.length && !g.querySelector('input[type="radio"]:checked')) bad(g, 'Elige una opción.');
    });
    if (n === 1) {
      var t = document.getElementById('f-title');
      if (t && t.value.trim().length < 5) bad(t, 'Escribe un título de al menos 5 letras.');
    }
    if (firstBad && firstBad.scrollIntoView) firstBad.scrollIntoView({ block: 'center', behavior: 'smooth' });
    return ok;
  }

  btnNext.addEventListener('click', function () { if (validateStep(step)) showStep(step + 1); });
  btnBack.addEventListener('click', function () { showStep(step - 1); });
  form.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && e.target.tagName === 'INPUT' && step < 4) { e.preventDefault(); btnNext.click(); }
  });
  // Muchos teclados de Android no mandan «Enter» al tocar «Ir»/«Siguiente» y envían el formulario: antes del paso 4
  // eso debe avanzar de paso, no publicar a medias.
  form.addEventListener('submit', function (e) {
    if (step < 4) { e.preventDefault(); e.stopImmediatePropagation(); btnNext.click(); }
  });

  /* ---------- Precio con separador de miles mientras escribe ---------- */
  var price = document.getElementById('f-price');
  if (price) price.addEventListener('input', function () {
    var d = price.value.replace(/\D/g, '');
    price.value = d ? Number(d).toLocaleString('es-CO') : '';
  });

  /* ---------- Precio de referencia en la zona ---------- */
  var refBox = document.getElementById('price-reference');
  var refTimer;
  function money(n) { return '$ ' + Number(n).toLocaleString('es-CO'); }
  function loadReference() {
    if (!refBox) return;
    var cat = form.querySelector('input[name="category_id"]:checked:not(:disabled)');
    var unit = form.querySelector('input[name="price_unit"]:checked:not(:disabled)');
    var mun = document.getElementById('f-municipality_id');
    if (!cat || !unit || unit.value === 'a convenir' || !window.fetch) { refBox.classList.add('hidden'); return; }
    var url = refBox.getAttribute('data-url') + '?categoria=' + encodeURIComponent(cat.value) +
      '&unidad=' + encodeURIComponent(unit.value) + '&municipio=' + encodeURIComponent(mun ? mun.value : '');
    fetch(url, { headers: { 'Accept': 'application/json' } }).then(function (r) { return r.json(); }).then(function (d) {
      if (!d.available) { refBox.classList.add('hidden'); return; }
      var where = d.scope === 'municipio' ? 'en tu municipio' : 'en la zona';
      document.getElementById('price-reference-text').textContent =
        'Precio promedio ' + where + ': ' + money(d.average) + ' por ' + unit.value + ' (entre ' + money(d.minimum) +
        ' y ' + money(d.maximum) + ', según ' + d.sample_size + ' anuncios de los últimos 30 días).';
      refBox.setAttribute('data-average', d.average);
      refBox.classList.remove('hidden');
    }).catch(function () { refBox.classList.add('hidden'); });
  }
  if (refBox) {
    var scheduleRef = function () { clearTimeout(refTimer); refTimer = setTimeout(loadReference, 250); };
    form.addEventListener('change', function (e) {
      if (e.target.name === 'price_unit' || e.target.name === 'category_id' || e.target.id === 'f-municipality_id') scheduleRef();
    });
    document.getElementById('price-reference-use').addEventListener('click', function () {
      var avg = refBox.getAttribute('data-average');
      if (avg && price) { price.value = Number(avg).toLocaleString('es-CO'); price.dispatchEvent(new Event('input', { bubbles: true })); }
    });
  }

  /* ---------- Fotos ---------- */
  var grid = document.getElementById('photo-grid');
  var emptyMsg = document.getElementById('photo-empty');
  var msg = document.getElementById('photo-msg');
  var MAX = parseInt(form.getAttribute('data-max-images'), 10) || 6;
  var base = grid.getAttribute('data-base');
  var items = [];
  try {
    JSON.parse(grid.getAttribute('data-existing') || '[]').forEach(function (e) {
      items.push({ kind: 'e', id: e.id, url: base + e.f });
    });
  } catch (err) { /* sin fotos previas */ }

  function btn(txt, aria, fn, cls) {
    var b = document.createElement('button');
    b.type = 'button'; b.textContent = txt; b.setAttribute('aria-label', aria);
    b.className = 'btn btn-sm ' + (cls || 'btn-outline') + ' !min-h-[2.5rem] !px-3';
    b.addEventListener('click', fn);
    return b;
  }
  function renderPhotos() {
    grid.innerHTML = '';
    items.forEach(function (it, i) {
      var li = document.createElement('li');
      li.className = 'card overflow-hidden';
      var wrap = document.createElement('div');
      wrap.className = 'relative aspect-[4/3] bg-tierra-100';
      var img = document.createElement('img');
      img.src = it.url; img.alt = 'Foto ' + (i + 1); img.className = 'w-full h-full object-cover';
      wrap.appendChild(img);
      if (i === 0) {
        var tag = document.createElement('span');
        tag.className = 'badge badge-vendo absolute top-2 left-2'; tag.textContent = 'Principal';
        wrap.appendChild(tag);
      }
      li.appendChild(wrap);
      var row = document.createElement('div');
      row.className = 'p-2 flex flex-wrap gap-1 justify-between';
      if (i > 0) row.appendChild(btn('Hacer principal', 'Hacer principal la foto ' + (i + 1), function () { move(i, 0); }));
      var arrows = document.createElement('span'); arrows.className = 'flex gap-1';
      if (i > 0) arrows.appendChild(btn('←', 'Mover a la izquierda', function () { move(i, i - 1); }));
      if (i < items.length - 1) arrows.appendChild(btn('→', 'Mover a la derecha', function () { move(i, i + 1); }));
      row.appendChild(arrows);
      row.appendChild(btn('Quitar', 'Quitar la foto ' + (i + 1), function () { items.splice(i, 1); renderPhotos(); }, 'btn-danger'));
      li.appendChild(row);
      grid.appendChild(li);
    });
    emptyMsg.classList.toggle('hidden', items.length > 0);
  }
  function move(from, to) {
    var it = items.splice(from, 1)[0];
    items.splice(to, 0, it);
    renderPhotos();
  }

  /* Compresión en el navegador: máx. 1200px, WebP (o JPEG si el navegador no sabe WebP). Si algo falla (poca memoria,
     foto enorme, formato raro) se sube la foto original: el servidor la reduce igual. Nunca se queda esperando. */
  // Los navegadores viejos no giran la foto según su orientación al dibujarla: se deja que el servidor lo haga.
  var autoRotates = !!(window.CSS && CSS.supports && CSS.supports('image-orientation', 'from-image'));
  var COMPRESS_TIMEOUT_MS = 15000;
  function compress(file) {
    return new Promise(function (resolve) {
      var url = null, finished = false;
      function done(f) {
        if (finished) return;
        finished = true; clearTimeout(timer);
        if (url) URL.revokeObjectURL(url);
        resolve(f);
      }
      var timer = setTimeout(function () { done(file); }, COMPRESS_TIMEOUT_MS);
      if (!autoRotates || !window.HTMLCanvasElement || !HTMLCanvasElement.prototype.toBlob) return done(file);
      try {
        url = URL.createObjectURL(file);
        var img = new Image();
        img.onload = function () {
          try {
            var s = Math.min(1, 1200 / Math.max(img.width, img.height));
            var c = document.createElement('canvas');
            c.width = Math.round(img.width * s); c.height = Math.round(img.height * s);
            c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
            c.toBlob(function (blob) {
              if (blob && blob.type === 'image/webp') return done(new File([blob], 'foto.webp', { type: blob.type }));
              // Safari y otros no saben WebP y devuelven PNG (muy pesado): se pide JPEG
              c.toBlob(function (jpg) {
                done(jpg ? new File([jpg], 'foto.jpg', { type: 'image/jpeg' }) : file);
              }, 'image/jpeg', 0.82);
            }, 'image/webp', 0.8);
          } catch (err) { done(file); }
        };
        img.onerror = function () { done(file); };
        img.src = url;
      } catch (err) { done(file); }
    });
  }

  // Sin DataTransfer (iPhone con iOS anterior a 14.5 y Androids viejos) no se pueden armar los archivos a mano:
  // los dos selectores se envían tal cual, con el nombre «photos». Se pierde ordenar/quitar fotos nuevas, pero no se pierden fotos.
  var canTransfer = true;
  try { new DataTransfer(); } catch (err) { canTransfer = false; }

  var inCam = document.getElementById('in-camera'), inGal = document.getElementById('in-gallery');
  if (!canTransfer) { inCam.name = 'photos'; inGal.name = 'photos'; }
  function nativeCount() { return (inCam.files ? inCam.files.length : 0) + (inGal.files ? inGal.files.length : 0); }

  function addFiles(list) {
    msg.textContent = '';
    var files = Array.prototype.slice.call(list);
    var room = MAX - items.length;
    if (files.length > room) { msg.textContent = 'Solo caben ' + MAX + ' fotos en total.'; files = files.slice(0, Math.max(room, 0)); }
    Promise.all(files.map(compress)).then(function (out) {
      out.forEach(function (f) { items.push({ kind: 'n', file: f, url: URL.createObjectURL(f) }); });
      renderPhotos();
    });
  }
  document.getElementById('btn-camera').addEventListener('click', function () { inCam.click(); });
  document.getElementById('btn-gallery').addEventListener('click', function () { inGal.click(); });
  [inCam, inGal].forEach(function (inp) {
    inp.addEventListener('change', function () {
      if (!canTransfer) {
        var n = nativeCount();
        msg.textContent = n ? n + (n === 1 ? ' foto nueva lista' : ' fotos nuevas listas') + ' para subir.' : '';
        return;
      }
      addFiles(inp.files); inp.value = '';
    });
  });
  renderPhotos();

  /* Al enviar: orden de fotos + archivos ya comprimidos */
  form.addEventListener('submit', function () {
    var tokens = [], n = 0, i;
    if (canTransfer) {
      var dt = new DataTransfer();
      items.forEach(function (it) {
        if (it.kind === 'e') tokens.push('e' + it.id);
        else { dt.items.add(it.file); tokens.push('n' + n); n += 1; }
      });
      document.getElementById('photos').files = dt.files;
    } else {
      items.forEach(function (it) { if (it.kind === 'e') tokens.push('e' + it.id); });
      for (i = 0; i < nativeCount(); i += 1) tokens.push('n' + i);
    }
    document.getElementById('image-order').value = tokens.join(',');
    document.getElementById('image-order-set').value = '1';
    btnSubmit.disabled = true; btnSubmit.textContent = 'Publicando…';
  });

  /* ---------- Borrador automático (localStorage) ---------- */
  var key = form.getAttribute('data-draft-key');
  var hasValues = form.getAttribute('data-has-values') === '1';
  var SKIP = { csrf_token: 1, photos: 1, image_order: 1, image_order_set: 1 };
  function snapshot() {
    var data = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || SKIP[el.name] || el.type === 'file' || el.type === 'button' || el.type === 'submit') return;
      if (el.type === 'radio') { if (el.checked) data[el.name] = el.value; }
      else if (el.type === 'checkbox') { data[el.name] = el.checked ? el.value : ''; }
      else if (!el.disabled) data[el.name] = el.value;
      else if (el.tagName === 'SELECT' && el.value) data[el.name] = el.value;
    });
    return data;
  }
  var timer;
  function save() {
    clearTimeout(timer);
    timer = setTimeout(function () {
      try {
        var s = snapshot();
        if (!s.title && !currentRoot()) return;
        localStorage.setItem(key, JSON.stringify({ t: Date.now(), d: s }));
      } catch (e) { /* almacenamiento no disponible */ }
    }, 500);
  }
  function restore(d) {
    Object.keys(d).forEach(function (name) {
      var els = form.querySelectorAll('[name="' + name + '"]');
      Array.prototype.forEach.call(els, function (el) {
        if (el.type === 'radio') el.checked = el.value === d[name];
        else if (el.type === 'checkbox') el.checked = d[name] === el.value;
        else el.value = d[name];
      });
    });
    syncRoot();
    form.querySelectorAll('[data-village-select]').forEach(function (s) {
      var v = d[s.name]; var src = document.getElementById(s.getAttribute('data-mun-source'));
      if (src) src.dispatchEvent(new Event('change')); if (v) s.value = v;
    });
    if (window.syncOtherFields) window.syncOtherFields();
  }
  form.addEventListener('input', save); form.addEventListener('change', save);

  var banner = document.getElementById('draft-banner');
  if (!hasValues) {
    try {
      var raw = localStorage.getItem(key);
      if (raw) {
        var saved = JSON.parse(raw);
        if (saved && saved.d && Date.now() - saved.t < 7 * 864e5) {
          banner.classList.remove('hidden');
          document.getElementById('draft-restore').addEventListener('click', function () { restore(saved.d); banner.classList.add('hidden'); });
          document.getElementById('draft-discard').addEventListener('click', function () { localStorage.removeItem(key); banner.classList.add('hidden'); });
        }
      }
    } catch (e) { /* ignorar */ }
  }

  syncRoot();
  form.setAttribute('data-wizard', ''); // todo cargó bien: desde aquí los pasos se muestran de uno en uno
  showStep(step);
})();
