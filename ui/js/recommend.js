let selectedGenres = new Set();
const movieRatings = new Map(); // movieId → rating (1–5)

// ── Helpers ──────────────────────────────────────────────────────────────────

async function fetchJSON(url) {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function postJSON(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function showStep(n) {
  [1, 2, 3].forEach(i => {
    document.getElementById(`step-${i}`).classList.toggle('hidden', i !== n);
    const s = document.getElementById(`stepper-${i}`);
    s.classList.remove('active', 'done');
    if (i < n) s.classList.add('done');
    if (i === n) s.classList.add('active');
  });
}

// ── Step 1: Genre Selection ──────────────────────────────────────────────────

async function loadGenres() {
  const data = await fetchJSON('/api/recommend/genres');
  const grid = document.getElementById('genre-grid');

  grid.innerHTML = data.genres.map(g => `
    <div class="genre-chip" data-genre="${g}">${g}</div>
  `).join('');

  grid.addEventListener('click', e => {
    const chip = e.target.closest('.genre-chip');
    if (!chip) return;
    const g = chip.dataset.genre;
    if (selectedGenres.has(g)) {
      selectedGenres.delete(g);
      chip.classList.remove('selected');
    } else {
      selectedGenres.add(g);
      chip.classList.add('selected');
    }
    document.getElementById('btn-to-step2').disabled = selectedGenres.size === 0;
  });
}

document.getElementById('btn-to-step2').addEventListener('click', async () => {
  const btn = document.getElementById('btn-to-step2');
  btn.disabled = true;
  btn.textContent = 'Loading…';
  try {
    const data = await postJSON('/api/recommend/movies', { genres: [...selectedGenres] });
    renderMovies(data.movies);
    showStep(2);
  } catch (err) {
    alert('Failed to load movies: ' + err.message);
    btn.disabled = false;
  } finally {
    btn.textContent = 'Find Movies →';
    btn.disabled = selectedGenres.size === 0;
  }
});

// ── Step 2: Rate Movies ───────────────────────────────────────────────────────

function renderMovies(movies) {
  const grid = document.getElementById('movies-grid');

  grid.innerHTML = movies.map(m => `
    <div class="movie-card" id="mc-${m.movieId}" data-id="${m.movieId}">
      <div class="movie-title">${m.title}</div>
      <div class="movie-genres">${m.genres.replace(/\|/g, ' · ')}</div>
      <div class="movie-meta">${m.year ? m.year + ' · ' : ''}${m.num_ratings.toLocaleString()} ratings · ${m.avg_rating.toFixed(2)} avg</div>
      <div class="star-rating" data-id="${m.movieId}">
        ${[1, 2, 3, 4, 5].map(v =>
          `<span class="star" data-val="${v}" title="${v} star${v > 1 ? 's' : ''}">★</span>`
        ).join('')}
      </div>
      <div class="star-label" id="sl-${m.movieId}">Not rated</div>
    </div>
  `).join('');

  // Click to set rating
  grid.addEventListener('click', e => {
    const star = e.target.closest('.star');
    if (!star) return;
    const container = star.closest('.star-rating');
    const movieId   = parseInt(container.dataset.id);
    const val       = parseInt(star.dataset.val);
    setRating(movieId, val);
  });

  // Hover preview
  grid.addEventListener('mouseover', e => {
    const star = e.target.closest('.star');
    if (!star) return;
    const container = star.closest('.star-rating');
    highlightStars(container, parseInt(star.dataset.val));
  });

  // Reset on mouse leave (only when leaving the container entirely)
  grid.addEventListener('mouseout', e => {
    const star = e.target.closest('.star');
    if (!star) return;
    const container = star.closest('.star-rating');
    if (!container || container.contains(e.relatedTarget)) return;
    highlightStars(container, movieRatings.get(parseInt(container.dataset.id)) ?? 0);
  });
}

function highlightStars(container, upTo) {
  container.querySelectorAll('.star').forEach(s => {
    s.classList.toggle('active', parseInt(s.dataset.val) <= upTo);
  });
}

function setRating(movieId, val) {
  movieRatings.set(movieId, val);
  const card = document.getElementById(`mc-${movieId}`);
  card.classList.add('rated');
  highlightStars(card.querySelector('.star-rating'), val);
  document.getElementById(`sl-${movieId}`).textContent = `${val} star${val > 1 ? 's' : ''}`;
  document.getElementById('btn-to-step3').disabled = false;
}

document.getElementById('btn-back-1').addEventListener('click', () => {
  movieRatings.clear();
  document.getElementById('btn-to-step3').disabled = true;
  showStep(1);
});

document.getElementById('btn-to-step3').addEventListener('click', async () => {
  const btn = document.getElementById('btn-to-step3');
  btn.disabled = true;
  btn.textContent = 'Thinking…';
  try {
    const ratings = [...movieRatings.entries()].map(([movieId, rating]) => ({ movieId, rating }));
    const data = await postJSON('/api/recommend', { ratings });
    renderResults(data.recommendations);
    showStep(3);
  } catch (err) {
    alert('Failed to get recommendations: ' + err.message);
    btn.disabled = false;
  } finally {
    btn.textContent = 'Get Recommendations →';
  }
});

// ── Step 3: Results ───────────────────────────────────────────────────────────

function renderResults(recs) {
  const list = document.getElementById('results-list');

  if (!recs.length) {
    list.innerHTML = '<p style="color:var(--text-secondary);padding:.5rem 0">No recommendations found — try rating more movies.</p>';
    return;
  }

  list.innerHTML = recs.map((r, i) => `
    <div class="result-card">
      <div class="result-rank">${i + 1}</div>
      <div class="result-info">
        <div class="result-title">${r.title}${r.year ? ` <span class="result-year">(${r.year})</span>` : ''}</div>
        <div class="result-genres">${r.genres.replace(/\|/g, ' · ')}</div>
      </div>
      <div class="result-scores">
        ${scoreRow('Hybrid',  r.hybrid_score,  '')}
        ${scoreRow('ALS',     r.als_score,     '--als')}
        ${scoreRow('Content', r.content_score, '--content')}
      </div>
    </div>
  `).join('');
}

function scoreRow(label, val, mod) {
  const cls = mod ? `score-fill score-fill${mod}` : 'score-fill';
  return `
    <div class="score-row">
      <span class="score-label">${label}</span>
      <div class="score-track">
        <div class="${cls}" style="width:${(val * 100).toFixed(1)}%"></div>
      </div>
      <span class="score-val">${val.toFixed(3)}</span>
    </div>`;
}

document.getElementById('btn-restart').addEventListener('click', () => {
  selectedGenres.clear();
  movieRatings.clear();
  document.querySelectorAll('.genre-chip').forEach(c => c.classList.remove('selected'));
  document.getElementById('btn-to-step2').disabled = true;
  document.getElementById('btn-to-step3').disabled = true;
  showStep(1);
});

// ── Init ──────────────────────────────────────────────────────────────────────

loadGenres();
