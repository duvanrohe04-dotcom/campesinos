/* JS mínimo: modales, conteo de contactos, veredas por municipio, filtros desplegables, estado de conexión. */
(function () {
  // Modales <dialog>
  document.addEventListener('click', function (e) {
    var open = e.target.closest('[data-modal-open]');
    if (open) { var d = document.getElementById(open.getAttribute('data-modal-open')); if (d && d.showModal) d.showModal(); }
    var close = e.target.closest('[data-modal-close]');
    if (close) { var dlg = close.closest('dialog'); if (dlg) dlg.close(); }
  });

  // Confirmaciones sencillas en formularios de acción
  document.addEventListener('submit', function (e) {
    var msg = e.target.getAttribute && e.target.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // Veredas filtradas por el municipio elegido
  function syncVillages(sel) {
    var src = document.getElementById(sel.getAttribute('data-mun-source'));
    if (!src) return;
    var mun = src.value, current = sel.value, keep = false;
    Array.prototype.forEach.call(sel.options, function (o) {
      if (!o.value || o.value === OTHER_VILLAGE) return;  // «Elige» y «Otra» siempre visibles
      var show = o.getAttribute('data-mun') === mun;
      o.hidden = !show; o.disabled = !show;
      if (show && o.value === current) keep = true;
    });
    if (!keep && current !== OTHER_VILLAGE) sel.value = '';
  }
  var OTHER_VILLAGE = '0';
  document.querySelectorAll('[data-village-select]').forEach(function (sel) {
    var src = document.getElementById(sel.getAttribute('data-mun-source'));
    if (src) src.addEventListener('change', function () { syncVillages(sel); });
    syncVillages(sel);
  });

  // Campos «¿Cuál?»: se muestran solo si eligen «Otra/Otro» (vereda o una opción de lista)
  var OTHER_RE = /^otr[ao]$/i;
  function syncOtherFields() {
    document.querySelectorAll('[data-other-for]').forEach(function (box) {
      var picked = document.querySelector('input[name="' + box.getAttribute('data-other-for') + '"]:checked');
      box.hidden = !(picked && OTHER_RE.test(picked.value));
    });
    document.querySelectorAll('[data-village-other]').forEach(function (box) {
      var scope = box.closest('form') || document;
      var sel = scope.querySelector('[data-village-select]');
      box.hidden = !sel || sel.value !== OTHER_VILLAGE;
    });
  }
  document.addEventListener('change', syncOtherFields);
  window.syncOtherFields = syncOtherFields;
  syncOtherFields();

  // Panel de filtros: abierto por defecto en escritorio
  var fp = document.getElementById('filters-panel');
  if (fp && window.matchMedia('(min-width: 1024px)').matches) fp.open = true;

  // Enviar formulario de filtros al cambiar la categoría
  document.querySelectorAll('[data-autosubmit]').forEach(function (el) {
    el.addEventListener('change', function () { el.form.submit(); });
  });

  // PWA: service worker y botón "Instalar app"
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', function () { navigator.serviceWorker.register('/sw.js').catch(function () {}); });
  }
  var deferred = null, installBtn = document.getElementById('install-btn');
  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault(); deferred = e;
    if (installBtn) installBtn.classList.remove('hidden');
  });
  if (installBtn) installBtn.addEventListener('click', function () {
    if (!deferred) return;
    deferred.prompt();
    deferred.userChoice.finally(function () { deferred = null; installBtn.classList.add('hidden'); });
  });
  window.addEventListener('appinstalled', function () { if (installBtn) installBtn.classList.add('hidden'); });

  // Indicador sin conexión
  var bar = document.getElementById('offline-bar');
  function net() { if (bar) bar.classList.toggle('hidden', navigator.onLine); }
  window.addEventListener('online', net); window.addEventListener('offline', net); net();
})();
