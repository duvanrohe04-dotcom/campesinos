/* Gráfico semanal del panel (Chart.js por CDN). Si no carga (sin conexión), queda la tabla debajo. */
(function () {
  var canvas = document.getElementById('weekly-chart');
  var dataEl = document.getElementById('weekly-data');
  if (!canvas || !dataEl) return;

  function draw() {
    if (!window.Chart) { canvas.parentNode.classList.add('hidden'); return; }
    var data = JSON.parse(dataEl.textContent);
    new window.Chart(canvas, {
      type: 'bar',
      data: {
        labels: data.labels,
        datasets: [
          { label: 'Vistas', data: data.views, backgroundColor: '#66AE4F', borderRadius: 4 },
          { label: 'Contactos', data: data.contacts, backgroundColor: '#B64A24', borderRadius: 4 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
        plugins: { legend: { position: 'bottom' } }
      }
    });
  }
  if (document.readyState === 'complete') draw(); else window.addEventListener('load', draw);
})();
