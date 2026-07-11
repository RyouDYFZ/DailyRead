const state = { manifest: [], current: null };

const articleEl = document.querySelector('#article');
const loadingEl = document.querySelector('#loading');
const dateListEl = document.querySelector('#date-list');
const dateSelectEl = document.querySelector('#date-select');

function escapeHtml(value) {
  const span = document.createElement('span');
  span.textContent = value;
  return span.innerHTML;
}

function renderQuiz(quiz, date) {
  const questions = quiz.map((item, index) => {
    const options = Object.entries(item.options).map(([letter, label]) => `
      <label class="option" data-letter="${letter}">
        <input type="radio" name="q${index}" value="${letter}">
        <span class="option-letter">${letter}</span>
        <span>${escapeHtml(label)}</span>
      </label>`).join('');
    return `<fieldset class="question" data-answer="${item.answer}">
      <legend><span>${item.number}.</span> ${escapeHtml(item.question)}</legend>
      ${options}<p class="feedback" aria-live="polite"></p>
    </fieldset>`;
  }).join('');

  return `<section class="quiz" aria-labelledby="quiz-title">
    <h2 id="quiz-title">\u9605\u8bfb\u7406\u89e3</h2>
    <form id="quiz-form" data-date="${date}">${questions}
      <div class="quiz-actions">
        <button type="submit">\u63d0\u4ea4\u7b54\u6848</button>
        <button type="button" class="secondary" id="reset-quiz">\u91cd\u65b0\u4f5c\u7b54</button>
      </div>
      <div id="score" class="score" aria-live="polite"></div>
    </form>
  </section>`;
}

function activateDate(date) {
  document.querySelectorAll('.date-link').forEach((button) => {
    button.classList.toggle('active', button.dataset.date === date);
  });
  dateSelectEl.value = date;
}

async function loadArticle(date, updateHash = true) {
  const item = state.manifest.find((entry) => entry.date === date) || state.manifest[0];
  if (!item) return;
  loadingEl.hidden = false;
  articleEl.hidden = true;
  try {
    const response = await fetch(item.file);
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const data = await response.json();
    state.current = data;
    articleEl.innerHTML = `${data.content_html}${renderQuiz(data.quiz, data.date)}${data.sources_html}`;
    articleEl.hidden = false;
    loadingEl.hidden = true;
    activateDate(data.date);
    bindQuiz();
    document.title = `${data.title} · DailyRead`;
    if (updateHash) history.replaceState(null, '', `#${data.date}`);
    window.scrollTo({ top: 0, behavior: 'instant' });
  } catch (error) {
    loadingEl.textContent = `\u52a0\u8f7d\u5931\u8d25\uff1a${error.message}`;
  }
}

function bindQuiz() {
  const form = document.querySelector('#quiz-form');
  const reset = document.querySelector('#reset-quiz');
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    let score = 0;
    const questions = [...form.querySelectorAll('.question')];
    questions.forEach((question, index) => {
      const answer = question.dataset.answer;
      const selected = form.querySelector(`input[name="q${index}"]:checked`);
      question.querySelectorAll('.option').forEach((option) => {
        option.classList.remove('correct', 'incorrect');
        if (option.dataset.letter === answer) option.classList.add('correct');
      });
      const feedback = question.querySelector('.feedback');
      if (!selected) {
        feedback.textContent = `\u672a\u4f5c\u7b54\u3002\u6b63\u786e\u7b54\u6848\uff1a${answer}`;
      } else if (selected.value === answer) {
        score += 1;
        feedback.textContent = '\u2713 \u56de\u7b54\u6b63\u786e';
      } else {
        selected.closest('.option').classList.add('incorrect');
        feedback.textContent = `\u2717 \u6b63\u786e\u7b54\u6848\uff1a${answer}`;
      }
    });
    const scoreEl = document.querySelector('#score');
    scoreEl.textContent = `\u5f97\u5206\uff1a${score} / ${questions.length}`;
    scoreEl.classList.add('visible');
    scoreEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
  });
  reset.addEventListener('click', () => {
    form.reset();
    form.querySelectorAll('.option').forEach((el) => el.classList.remove('correct', 'incorrect'));
    form.querySelectorAll('.feedback').forEach((el) => { el.textContent = ''; });
    const scoreEl = document.querySelector('#score');
    scoreEl.textContent = '';
    scoreEl.classList.remove('visible');
  });
}

function renderNavigation() {
  dateListEl.innerHTML = state.manifest.map((item) => `
    <button class="date-link" data-date="${item.date}">
      <time>${item.date}</time><span>${escapeHtml(item.title)}</span>
    </button>`).join('');
  dateSelectEl.innerHTML = state.manifest.map((item) =>
    `<option value="${item.date}">${item.date} · ${escapeHtml(item.title)}</option>`
  ).join('');
  dateListEl.addEventListener('click', (event) => {
    const button = event.target.closest('.date-link');
    if (button) loadArticle(button.dataset.date);
  });
  dateSelectEl.addEventListener('change', () => loadArticle(dateSelectEl.value));
}

async function init() {
  try {
    const response = await fetch('articles.json');
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.manifest = await response.json();
    renderNavigation();
    const requested = location.hash.slice(1);
    await loadArticle(requested, !requested);
  } catch (error) {
    loadingEl.textContent = `\u7f51\u9875\u521d\u59cb\u5316\u5931\u8d25\uff1a${error.message}`;
  }
}

init();
