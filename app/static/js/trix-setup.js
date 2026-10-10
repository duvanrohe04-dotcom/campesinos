/* Editor Trix del admin: sin adjuntos ni imágenes (el HTML se sanitiza además en el servidor). */
document.addEventListener('trix-file-accept', function (e) { e.preventDefault(); });
document.addEventListener('trix-initialize', function (e) {
  // Quita botones de adjuntar archivos de la barra
  var tools = e.target.toolbarElement && e.target.toolbarElement.querySelector('[data-trix-button-group="file-tools"]');
  if (tools) tools.remove();
});
