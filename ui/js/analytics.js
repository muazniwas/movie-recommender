const PALETTE = [
  '#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6',
  '#06b6d4', '#f97316', '#84cc16', '#ec4899', '#6366f1',
  '#14b8a6', '#eab308', '#f43f5e', '#a855f7', '#0ea5e9',
  '#22c55e', '#fb923c', '#e879f9', '#38bdf8', '#4ade80',
];

const charts = {};

// ── Helpers ────────────────────────────────────────────────────────────────

async function fetchJSON(endpoint) {
  const res = await fetch(endpoint);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function setStatus(state) {
  const el = document.getElementById('status-badge');
  el.className = `badge badge--${state}`;
  el.textContent = state === 'ready' ? 'Data loaded' : state === 'error' ? 'Error loading data' : 'Loading data…';
}

function makeChart(id, config) {
  if (charts[id]) charts[id].destroy();
  const ctx = document.getElementById(id).getContext('2d');
  charts[id] = new Chart(ctx, config);
}

function fmt(n) {
  return typeof n === 'number' ? n.toLocaleString() : n;
}

// ── Renderers ──────────────────────────────────────────────────────────────

function renderRatings(data) {
  document.getElementById('stat-total').textContent  = fmt(data.total);
  document.getElementById('stat-mean').textContent   = data.mean.toFixed(2);
  document.getElementById('stat-median').textContent = data.median.toFixed(1);
  document.getElementById('stat-std').textContent    = data.std.toFixed(3);

  const labels = data.labels.map(l => `${l} ★`);

  makeChart('chart-rating-bar', {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: 'Number of Ratings',
        data: data.counts,
        backgroundColor: PALETTE.slice(0, 5),
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
        x: { grid: { display: false }, ticks: { color: '#64748b' } },
      },
    },
  });

  makeChart('chart-rating-doughnut', {
    type: 'doughnut',
    data: {
      labels,
      datasets: [{
        data: data.percentages,
        backgroundColor: PALETTE.slice(0, 5),
        borderWidth: 2,
        borderColor: '#fff',
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: '#64748b', font: { size: 12 } } },
        tooltip: { callbacks: { label: ctx => ` ${ctx.parsed}%` } },
      },
      cutout: '60%',
    },
  });
}

function renderGenres(data) {
  const byCount  = data.by_movie_count;
  const byRating = data.by_avg_rating;

  makeChart('chart-genre-count', {
    type: 'bar',
    data: {
      labels: byCount.map(d => d.genre),
      datasets: [{
        label: 'Movies',
        data: byCount.map(d => d.movie_count),
        backgroundColor: PALETTE,
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
        y: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } },
      },
    },
  });

  makeChart('chart-genre-rating', {
    type: 'bar',
    data: {
      labels: byRating.map(d => d.genre),
      datasets: [{
        label: 'Avg Rating',
        data: byRating.map(d => d.avg_rating),
        backgroundColor: byRating.map(d => d.avg_rating >= 3.7 ? '#10b981' : '#3b82f6'),
        borderRadius: 4,
      }],
    },
    options: {
      indexAxis: 'y',
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        x: {
          min: 3.0, max: 4.5,
          grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' },
        },
        y: { grid: { display: false }, ticks: { color: '#64748b', font: { size: 11 } } },
      },
    },
  });
}

function renderTopMovies(data) {
  const tbody = document.getElementById('top-movies-body');
  const max   = data.movies[0]?.bayesian_avg ?? 5;

  tbody.innerHTML = data.movies.map((m, i) => `
    <tr>
      <td class="rank-cell">${i + 1}</td>
      <td><strong>${m.title}</strong></td>
      <td class="genres-cell">${m.genres.replace(/\|/g, ' · ')}</td>
      <td>${fmt(m.num_ratings)}</td>
      <td>${m.avg_rating.toFixed(2)}</td>
      <td>
        <div class="rating-bar">
          <div class="rating-bar-fill" style="width:${(m.bayesian_avg / max) * 120}px"></div>
          <span>${m.bayesian_avg.toFixed(3)}</span>
        </div>
      </td>
    </tr>
  `).join('');
}

function renderUsers(data) {
  document.getElementById('stat-act-min').textContent    = fmt(data.activity.min);
  document.getElementById('stat-act-max').textContent    = fmt(data.activity.max);
  document.getElementById('stat-act-mean').textContent   = data.activity.mean.toFixed(1);
  document.getElementById('stat-act-median').textContent = fmt(data.activity.median);

  const genderLabels = Object.keys(data.gender);
  const genderCounts = Object.values(data.gender);

  makeChart('chart-gender', {
    type: 'doughnut',
    data: {
      labels: genderLabels,
      datasets: [{
        data: genderCounts,
        backgroundColor: ['#3b82f6', '#ec4899'],
        borderWidth: 2,
        borderColor: '#fff',
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: {
        legend: { position: 'right', labels: { color: '#64748b', font: { size: 12 } } },
        tooltip: {
          callbacks: {
            label: ctx => {
              const total = genderCounts.reduce((a, b) => a + b, 0);
              return ` ${ctx.label}: ${ctx.parsed} (${(ctx.parsed / total * 100).toFixed(1)}%)`;
            },
          },
        },
      },
      cutout: '60%',
    },
  });

  makeChart('chart-age', {
    type: 'bar',
    data: {
      labels: data.age_groups.map(d => d.age_group),
      datasets: [{
        label: 'Users',
        data: data.age_groups.map(d => d.count),
        backgroundColor: PALETTE,
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
        x: { grid: { display: false }, ticks: { color: '#64748b' } },
      },
    },
  });

  makeChart('chart-activity', {
    type: 'bar',
    data: {
      labels: data.activity_histogram.map(d => d.bucket),
      datasets: [{
        label: 'Users',
        data: data.activity_histogram.map(d => d.count),
        backgroundColor: '#6366f1',
        borderRadius: 6,
      }],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' } },
        x: { grid: { display: false }, ticks: { color: '#64748b' } },
      },
    },
  });
}

function renderTrends(data) {
  makeChart('chart-trends', {
    type: 'line',
    data: {
      labels: data.periods,
      datasets: [
        {
          label: 'Ratings',
          data: data.counts,
          borderColor: '#3b82f6',
          backgroundColor: 'rgba(59,130,246,.08)',
          fill: true,
          tension: 0.3,
          pointRadius: 2,
          yAxisID: 'y1',
        },
        {
          label: 'Avg Rating',
          data: data.avg_ratings,
          borderColor: '#f59e0b',
          backgroundColor: 'transparent',
          tension: 0.3,
          pointRadius: 2,
          borderDash: [5, 3],
          yAxisID: 'y2',
        },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { labels: { color: '#64748b' } } },
      scales: {
        y1: {
          type: 'linear', position: 'left',
          grid: { color: '#f1f5f9' }, ticks: { color: '#64748b' },
          title: { display: true, text: 'Number of Ratings', color: '#64748b' },
        },
        y2: {
          type: 'linear', position: 'right',
          min: 3.0, max: 4.5,
          grid: { drawOnChartArea: false }, ticks: { color: '#64748b' },
          title: { display: true, text: 'Average Rating', color: '#64748b' },
        },
        x: { grid: { display: false }, ticks: { color: '#64748b', maxTicksLimit: 12 } },
      },
    },
  });
}

// ── Bootstrap ──────────────────────────────────────────────────────────────

async function init() {
  setStatus('loading');
  try {
    const [ratings, genres, topMovies, users, trends] = await Promise.all([
      fetchJSON('/api/analytics/ratings'),
      fetchJSON('/api/analytics/genres'),
      fetchJSON('/api/analytics/top-movies?n=20'),
      fetchJSON('/api/analytics/users'),
      fetchJSON('/api/analytics/trends'),
    ]);

    renderRatings(ratings);
    renderGenres(genres);
    renderTopMovies(topMovies);
    renderUsers(users);
    renderTrends(trends);

    setStatus('ready');
  } catch (err) {
    setStatus('error');
    console.error(err);
  }
}

document.addEventListener('DOMContentLoaded', init);
