async function fetchDefaultData() {
  const res = await fetch('/static/data/studio_test_dashboard.json', { cache: 'no-store' });
  if (!res.ok) {
    throw new Error(`加载默认数据失败: ${res.status}`);
  }
  return await res.json();
}

function pillClass(ok) {
  return ok ? 'pill ok' : 'pill bad';
}

function renderDashboard(data) {
  const summary = data.summary || {};
  const smoke = summary.smoke || {};
  const regression = summary.regression || {};

  document.getElementById('metric-buttons').textContent = String(summary.button_count ?? '-');
  document.getElementById('metric-smoke').textContent = `${smoke.passed ?? 0}/${smoke.total ?? 0}`;
  document.getElementById('metric-regression').textContent = `${regression.passed ?? 0}/${regression.total ?? 0}`;
  document.getElementById('metric-failed').textContent = `${(smoke.failed ?? 0) + (regression.failed ?? 0)}/${(smoke.skipped ?? 0) + (regression.skipped ?? 0)}`;

  const matrixBody = document.getElementById('matrix-body');
  matrixBody.innerHTML = '';
  for (const row of data.matrix_rows || []) {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><code>${row.id}</code></td>
      <td>${row.label || ''}</td>
      <td>${row.page || ''}</td>
      <td><span class="${pillClass(Boolean(row.covered))}">${row.covered ? '已覆盖' : '未覆盖'}</span></td>
    `;
    matrixBody.appendChild(tr);
  }

  const rows = [...(data.smoke_results || []), ...(data.regression_results || [])];
  const resultsBody = document.getElementById('results-body');
  resultsBody.innerHTML = '';
  for (const row of rows) {
    const ok = row.returncode === 0;
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${row.name || row.cmd?.join(' ') || '-'}</td>
      <td>${row.project || '-'}</td>
      <td>${row.kind || 'regression'}</td>
      <td><span class="${pillClass(ok)}">${ok ? 'PASS' : 'FAIL'}</span></td>
      <td>${row.duration_sec ?? '-'}</td>
    `;
    resultsBody.appendChild(tr);
  }

  document.getElementById('raw-output').textContent = JSON.stringify(data, null, 2);
}

async function loadDefault() {
  try {
    const data = await fetchDefaultData();
    renderDashboard(data);
  } catch (err) {
    document.getElementById('raw-output').textContent = String(err);
  }
}

document.getElementById('reload-btn').addEventListener('click', loadDefault);
document.getElementById('load-file-btn').addEventListener('click', async () => {
  const input = document.getElementById('file-input');
  const file = input.files?.[0];
  if (!file) {
    alert('先选择一个 JSON 文件');
    return;
  }
  const text = await file.text();
  renderDashboard(JSON.parse(text));
});

loadDefault();
