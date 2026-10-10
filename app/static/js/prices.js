/* Tendencia semanal de precios (Chart.js por CDN). Si no carga, queda la tabla. */
(function () {
  var canvas = document.getElementById('trend-chart');
  var dataEl = document.getElementById('trend-data');
  if (!canvas || !dataEl) return;
  function draw() {
    if (!window.Chart) { canvas.parentNode.classList.add('hidden'); return; }
    var d = JSON.parse(dataEl.textContent);
    var money = function (v) { return '$ ' + Number(v).toLocaleString('es-CO'); };
    new window.Chart(canvas, {
      type: 'line',
      data: {
        labels: d.labels,
        datasets: [
          { label: 'Promedio', data: d.averages, borderColor: '#2E5D22', backgroundColor: '#2E5D22', tension: 0.25, pointRadius: 4 },
          { label: 'Más bajo', data: d.minimums, borderColor: '#B3A594', borderDash: [6, 4], pointRadius: 2 },
          { label: 'Más alto', data: d.maximums, borderColor: '#B64A24', borderDash: [6, 4], pointRadius: 2 }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        scales: { y: { ticks: { callback: money } } },
        plugins: { legend: { position: 'bottom' }, tooltip: { callbacks: { label: function (c) { return c.dataset.label + ': ' + money(c.parsed.y); } } } }
      }
    });
  }
  if (document.readyState === 'complete') draw(); else window.addEventListener('load', draw);
})();
