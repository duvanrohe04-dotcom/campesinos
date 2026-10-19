/* Accesibilidad: leer en voz alta, dictado por voz y texto grande (Web Speech API; se oculta si el navegador no la tiene). */
(function () {
  var root = document.documentElement;

  /* ---------- Texto grande (preferencia guardada) ---------- */
  function applyTextSize(large) {
    root.classList.toggle('text-large', large);
    document.querySelectorAll('[data-text-size]').forEach(function (b) {
      b.setAttribute('aria-pressed', large ? 'true' : 'false');
      var label = b.querySelector('[data-label]');
      if (label) label.textContent = large ? 'Letra normal' : 'Letra grande';
    });
  }
  var stored = false;
  try { stored = localStorage.getItem('textsize') === 'large'; } catch (e) { /* sin almacenamiento */ }
  applyTextSize(stored);
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-text-size]');
    if (!btn) return;
    var large = !root.classList.contains('text-large');
    applyTextSize(large);
    try { localStorage.setItem('textsize', large ? 'large' : 'normal'); } catch (err) { /* ignorar */ }
  });

  /* ---------- Escuchar (síntesis de voz) ---------- */
  var synth = window.speechSynthesis;
  var speakButtons = document.querySelectorAll('[data-speak]');
  // Los botones vienen ocultos (`hidden`) para que sin JavaScript no queden botones muertos: se muestran solo si el
  // navegador sabe leer en voz alta.
  var canSpeak = !!(synth && window.SpeechSynthesisUtterance);
  speakButtons.forEach(function (b) { b.hidden = !canSpeak; });
  function pickVoice() {
    var voices = synth.getVoices();
    return voices.find(function (v) { return /es[-_]CO/i.test(v.lang); }) ||
           voices.find(function (v) { return /^es/i.test(v.lang); }) || null;
  }
  function stopSpeaking() {
    if (synth) synth.cancel();
    document.querySelectorAll('[data-speak][aria-pressed="true"]').forEach(function (b) { b.setAttribute('aria-pressed', 'false'); });
  }
  function textFor(btn) {
    var spec = btn.getAttribute('data-speak') || '';
    if (spec.charAt(0) === '#') {
      var el = document.querySelector(spec);
      return el ? el.innerText : '';
    }
    return spec;
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-speak]');
    if (!btn || !synth) return;
    if (btn.getAttribute('aria-pressed') === 'true') { stopSpeaking(); return; }
    stopSpeaking();
    var text = textFor(btn).replace(/\s+/g, ' ').trim();
    if (!text) return;
    var u = new SpeechSynthesisUtterance(text);
    u.lang = 'es-CO'; u.rate = 0.9;
    var voice = pickVoice(); if (voice) u.voice = voice;
    u.onend = u.onerror = function () { btn.setAttribute('aria-pressed', 'false'); };
    btn.setAttribute('aria-pressed', 'true');
    synth.speak(u);
  });
  window.addEventListener('pagehide', stopSpeaking);

  /* ---------- Dictado por voz (reconocimiento de voz) ---------- */
  var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  var micButtons = document.querySelectorAll('[data-dictate]');
  micButtons.forEach(function (b) { b.hidden = !Recognition; });  // igual que «Escuchar»: solo si hay reconocimiento de voz
  if (!Recognition) return;
  var active = null, recognition = null;
  function stopDictation() {
    if (recognition) { try { recognition.stop(); } catch (e) { /* ya detenido */ } }
    if (active) active.setAttribute('aria-pressed', 'false');
    active = recognition = null;
  }
  document.addEventListener('click', function (e) {
    var btn = e.target.closest('[data-dictate]');
    if (!btn) return;
    if (active === btn) { stopDictation(); return; }
    stopDictation();
    var field = document.getElementById(btn.getAttribute('data-dictate'));
    if (!field) return;
    recognition = new Recognition();
    recognition.lang = 'es-CO'; recognition.interimResults = false; recognition.continuous = false;
    recognition.onresult = function (ev) {
      var said = ev.results[0][0].transcript.trim();
      var max = parseInt(field.getAttribute('maxlength'), 10) || 10000;
      field.value = (field.value ? field.value.replace(/\s+$/, '') + ' ' : '') + said;
      field.value = field.value.slice(0, max);
      field.dispatchEvent(new Event('input', { bubbles: true }));
    };
    recognition.onend = recognition.onerror = function () { if (active === btn) stopDictation(); };
    active = btn; btn.setAttribute('aria-pressed', 'true');
    try { recognition.start(); } catch (err) { stopDictation(); }
  });
})();
