/* JS mínimo: modales, conteo de contactos, veredas por municipio, filtros desplegables, estado de conexión. */
(function () {
  // Modales <dialog>
  document.addEventListener('click', function (e) {
    var open = e.target.closest('[data-modal-open]');
    if (open) { var d = document.getElementById(open.getAttribute('data-modal-open')); if (d && d.showModal) d.showModal(); }
    var close = e.target.closest('[data-modal-close]');
    if (close) { var dlg = close.closest('dialog'); if (dlg) dlg.close(); }
  });

  // «Volver»: página anterior del historial si es de este mismo sitio; si no, el enlace de respaldo
  document.addEventListener('click', function (e) {
    var back = e.target.closest('[data-back]');
    if (!back || e.defaultPrevented || e.ctrlKey || e.metaKey || e.shiftKey) return;
    var from = document.referrer;
    if (history.length > 1 && from && from.indexOf(location.origin + '/') === 0 && from !== location.href) {
      e.preventDefault();
      history.back();
    }
  });

  // Teclado abierto: en pantallas pequeñas el CSS quita la barra inferior y el encabezado fijo (.kb-open) para que
  // el campo en el que se escribe no quede casi sin espacio.
  var TYPING = 'input:not([type=checkbox]):not([type=radio]):not([type=button]):not([type=submit]):not([type=file]), textarea, select';
  function isTyping(el) {
    var matches = el && (el.matches || el.webkitMatchesSelector || el.msMatchesSelector);
    return !!matches && matches.call(el, TYPING);
  }
  document.addEventListener('focusin', function (e) {
    if (isTyping(e.target)) document.documentElement.classList.add('kb-open');
  });
  document.addEventListener('focusout', function () {
    setTimeout(function () {  // al pasar de un campo a otro no debe parpadear
      if (!isTyping(document.activeElement)) document.documentElement.classList.remove('kb-open');
    }, 150);
  });

  // Confirmaciones sencillas en formularios de acción
  document.addEventListener('submit', function (e) {
    var msg = e.target.getAttribute && e.target.getAttribute('data-confirm');
    if (msg && !window.confirm(msg)) e.preventDefault();
  });

  // Veredas filtradas por el municipio elegido. Se quitan de la lista las de otros municipios: ocultarlas con
  // `hidden`/`disabled` no funciona en iPhone ni en varios Android (siguen apareciendo, en gris).
  function syncVillages(sel) {
    var src = document.getElementById(sel.getAttribute('data-mun-source'));
    if (!src) return;
    if (!sel._allOptions) sel._allOptions = Array.prototype.slice.call(sel.options);
    var mun = src.value, current = sel.value;
    while (sel.options.length) sel.remove(0);
    sel._allOptions.forEach(function (o) {
      var always = !o.value || o.value === OTHER_VILLAGE;  // «Elige» y «Otra» siempre visibles
      if (always || o.getAttribute('data-mun') === mun) sel.appendChild(o);
    });
    sel.value = current;
    if (sel.value !== current) sel.value = '';
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
