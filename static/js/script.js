// static/js/script.js

(() => {
  // Elements
  const themeToggle = document.getElementById('themeToggle');
  const body = document.getElementById('body');
  const ajaxBtn = document.getElementById('ajaxPredictBtn');
  const form = document.getElementById('predictForm');
  const alertZone = document.getElementById('alertZone');
  const resultCard = document.getElementById('resultCard');
  const predLabel = document.getElementById('predLabel');
  const probBar = document.getElementById('probBar');
  const explainBox = document.getElementById('explainBox');

  // Chart setup
  const ctx = document.getElementById('probChart').getContext('2d');
  const chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      labels: ['Death', 'Survival'],
      datasets: [{
        data: [0, 100],
        backgroundColor: ['rgba(124,58,237,0.95)', 'rgba(6,182,212,0.9)'],
        hoverOffset: 6,
        borderWidth: 0
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { position: 'bottom' },
        tooltip: { callbacks: {
          label: (ctx) => `${ctx.label}: ${ctx.parsed}%`
        }}
      }
    }
  });

  // Theme: load from localStorage
  function loadTheme() {
    const t = localStorage.getItem('theme');
    if (t === 'dark') body.classList.add('dark');
    updateThemeBtn();
  }
  function toggleTheme() {
    body.classList.toggle('dark');
    localStorage.setItem('theme', body.classList.contains('dark') ? 'dark' : 'light');
    updateThemeBtn();
  }
  function updateThemeBtn() {
    themeToggle.textContent = body.classList.contains('dark') ? '☀️' : '🌙';
  }
  themeToggle.addEventListener('click', toggleTheme);
  loadTheme();

  // Helper: show alerts
  function showAlert(msg, type='danger', timeout = 5000) {
    alertZone.innerHTML = `
      <div class="alert alert-${type} alert-dismissible fade show" role="alert">
        ${msg}
        <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
      </div>`;
    if (timeout) setTimeout(()=> { bootstrap.Alert.getOrCreateInstance(alertZone.querySelector('.alert')).close(); }, timeout);
  }

  // Helper: serialize form to JSON object
  function formToJson(formElem){
    const fd = new FormData(formElem);
    const obj = {};
    for (const [k, v] of fd.entries()) {
      // ensure we send numbers (backend expects ints)
      if (v === '') { obj[k] = null; }
      else if (!isNaN(v) && v.trim() !== '') obj[k] = Number(v);
      else obj[k] = v;
    }
    return obj;
  }

  // Update UI with result
  function updateResultUI(out) {
    resultCard.classList.remove('d-none');
    predLabel.textContent = out.prediction || 'Unknown';

    // probability is probability of class=1 (death) per backend
    let p = (out.probability === null || out.probability === undefined) ? null : Number(out.probability);
    if (p === null || Number.isNaN(p)) {
      probBar.style.width = '0%';
      probBar.textContent = 'N/A';
      explainBox.textContent = 'Probability not available.';
      chart.data.datasets[0].data = [0, 100];
    } else {
      const pct = Math.max(0, Math.min(1, p));
      const pct100 = Math.round(pct * 10000) / 100; // two decimals
      probBar.style.width = `${pct100}%`;
      probBar.textContent = `${pct100}%`;
      explainBox.innerHTML = `<strong>Note:</strong> Model probability for class <em>Dead</em>. Use clinically.`;
      // update chart: show percent death vs survival
      chart.data.datasets[0].data = [Math.round(pct * 10000) / 100, Math.round((1-pct) * 10000) / 100];
    }
    chart.update();
  }

  // Minimal client-side validation: ensure all required fields set
  function validateFormJson(obj) {
    const missing = [];
    for (const k in obj) {
      if (obj[k] === null || obj[k] === '') missing.push(k);
    }
    return missing;
  }

  // Main AJAX predict flow
  async function doAjaxPredict() {
    try {
      ajaxBtn.disabled = true;
      ajaxBtn.textContent = 'Predicting...';

      const payload = formToJson(form);
      const missing = validateFormJson(payload);
      if (missing.length) {
        showAlert(`Please fill: ${missing.join(', ')}`, 'warning', 6000);
        return;
      }

      // POST JSON to /api/predict
      const res = await fetch('/api/predict', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(payload)
      });

      if (!res.ok) {
        const txt = await res.json().catch(()=>null);
        const msg = txt && (txt.error || (txt.errors && txt.errors.join('; '))) ? (txt.error || txt.errors.join('; ')) : `Server returned ${res.status}`;
        showAlert(`Prediction error: ${msg}`, 'danger', 8000);
        return;
      }

      const out = await res.json();
      updateResultUI(out);

    } catch (err) {
      console.error('AJAX predict failed', err);
      showAlert('Unexpected error while predicting. See console.', 'danger', 8000);
    } finally {
      ajaxBtn.disabled = false;
      ajaxBtn.textContent = 'Predict (AJAX)';
    }
  }

  ajaxBtn.addEventListener('click', (e) => {
    e.preventDefault();
    doAjaxPredict();
  });

  // Allow fallback: real form submission (server render)
  // Intercept normal submit for usability: if user clicks "Submit (server render)" we allow default behavior.
  form.addEventListener('submit', (e) => {
    // no interception here, default server form submit will proceed.
  });

  // Initial chart paint
  chart.update();

})();
