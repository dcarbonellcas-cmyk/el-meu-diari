const dateElement = document.querySelector('#date');
dateElement.textContent = new Intl.DateTimeFormat('ca-ES', {
  day: 'numeric', month: 'short', year: 'numeric'
}).format(new Date());

const diaryButton = document.querySelector('#generate');
const diaryStatus = document.querySelector('#diary-status');

const viewer = document.querySelector('#viewer');
const viewerPages = document.querySelector('#viewer-pages');
const viewerProgress = document.querySelector('#viewer-progress');
const viewerTitle = document.querySelector('#viewer-title');
const viewerFallback = document.querySelector('#viewer-fallback');
let viewerRequest = 0;

async function openPDF(url, title) {
  const request = ++viewerRequest;
  archiveScreen.hidden = true;
  homeHero.hidden = false;
  viewerTitle.textContent = title;
  viewerFallback.href = url;
  viewerPages.replaceChildren();
  viewerProgress.textContent = 'Carregant totes les pàgines…';
  viewer.hidden = false;
  viewer.scrollIntoView({ behavior: 'smooth', block: 'start' });
  try {
    if (!window.pdfjsLib) throw new Error('PDF.js unavailable');
    window.pdfjsLib.GlobalWorkerOptions.workerSrc =
      'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/pdf.worker.min.js';
    const pdf = await window.pdfjsLib.getDocument(url).promise;
    if (request !== viewerRequest) return;
    viewerProgress.textContent = pdf.numPages + ' pàgines · Desplaça’t cap avall per llegir-les totes.';
    for (let n = 1; n <= pdf.numPages; n++) {
      if (request !== viewerRequest) return;
      const page = await pdf.getPage(n);
      const base = page.getViewport({ scale: 1 });
      const available = Math.max(240, viewerPages.clientWidth - 2);
      const scale = Math.min(1.7, available / base.width * Math.min(window.devicePixelRatio || 1, 1.5));
      const viewport = page.getViewport({ scale });
      const canvas = document.createElement('canvas');
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = '100%';
      canvas.style.height = 'auto';
      canvas.setAttribute('aria-label', 'Pàgina ' + n + ' de ' + pdf.numPages);
      viewerPages.append(canvas);
      await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise;
    }
  } catch (error) {
    if (request !== viewerRequest) return;
    viewerProgress.textContent = 'No s’ha pogut mostrar el PDF aquí. Utilitza l’enllaç de sota per obrir-lo.';
  }
}

document.querySelector('#viewer-close').addEventListener('click', () => {
  ++viewerRequest;
  viewer.hidden = true;
  viewerPages.replaceChildren();
});

const archiveScreen = document.querySelector('#archive-screen');
const homeHero = document.querySelector('#home-hero');

function showArchive() {
  renderArchive();
  homeHero.hidden = true;
  viewer.hidden = true;
  archiveScreen.hidden = false;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showHome() {
  archiveScreen.hidden = true;
  homeHero.hidden = false;
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

document.querySelector('#show-archive').addEventListener('click', showArchive);
document.querySelector('#back-home').addEventListener('click', showHome);

async function updateLatestLabel() {
  try {
    const response = await fetch('./diaris/latest.json', { cache: 'no-store' });
    if (!response.ok) return;
    const edition = await response.json();
    if (!edition.updatedAt || edition.date !== madridDate() || !edition.count) return;
    const time = new Intl.DateTimeFormat('ca-ES', {
      timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit'
    }).format(new Date(edition.updatedAt));
    document.querySelector('#latest-label').textContent = 'Veure ara · Edició de les ' + time + ' h';
  } catch {
    // Keep the generic button label if offline.
  }
}
updateLatestLabel();

function madridDate(date = new Date()) {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Madrid', year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(date);
  const value = type => parts.find(part => part.type === type).value;
  return `${value('year')}-${value('month')}-${value('day')}`;
}

diaryButton.addEventListener('click', async () => {
  diaryButton.disabled = true;
  diaryStatus.textContent = 'Comprovant el diari d’avui…';
  try {
    const response = await fetch('./diaris/latest.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('unavailable');
    const edition = await response.json();
    if (edition.date !== madridDate()) {
      diaryStatus.textContent = 'El diari d’avui encara s’està preparant. Torna-ho a provar més tard.';
      return;
    }
    if (!Number.isInteger(edition.count) || edition.count < 1) {
      diaryStatus.textContent = 'Encara no hi ha notícies d’avui disponibles. Torna-ho a provar més tard.';
      return;
    }
    const updated = new Date(edition.updatedAt);
    if (Number.isNaN(updated.getTime())) throw new Error('invalid edition');
    diaryStatus.textContent = 'Ja pots llegir el diari aquí mateix.';
    openPDF('./diaris/avui.pdf?v=' + encodeURIComponent(edition.updatedAt), 'El diari d’avui');
  } catch {
    diaryStatus.textContent = 'No s’ha pogut obrir el diari. Comprova la connexió i torna-ho a provar.';
  } finally {
    diaryButton.disabled = false;
  }
});

function latestEditionPerDay(editions) {
  const days = new Map();
  for (const edition of editions) {
    const day = madridDate(new Date(edition.updatedAt));
    const previous = days.get(day);
    if (!previous || new Date(edition.updatedAt) > new Date(previous.updatedAt)) {
      days.set(day, edition);
    }
  }
  return [...days.values()].sort((a, b) =>
    new Date(b.updatedAt) - new Date(a.updatedAt)
  );
}

async function renderArchive() {
  const archive = document.querySelector('#archive');
  try {
    const response = await fetch('./diaris/archive.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('archive unavailable');
    const catalog = await response.json();
    if (!Array.isArray(catalog.editions)) throw new Error('invalid archive');
    archive.replaceChildren();
    const editions = latestEditionPerDay(catalog.editions.filter(edition =>
      /^diaris\/arxiu\/\d{4}-\d{2}-\d{2}\/\d{2}-\d{2}-\d{2}-\d{6}\.pdf$/.test(edition.pdf) &&
      !Number.isNaN(new Date(edition.updatedAt).getTime())
    ));
    if (!editions.length) {
      const empty = document.createElement('p');
      empty.className = 'small';
      empty.textContent = 'La primera edició es guardarà automàticament quan hi hagi notícies.';
      archive.append(empty);
      return;
    }
    const list = document.createElement('div');
    const more = document.createElement('button');
    more.type = 'button';
    more.className = 'cta secondary';
    more.textContent = 'Veure més edicions';
    const format = new Intl.DateTimeFormat('ca-ES', {
      timeZone: 'Europe/Madrid', day: 'numeric', month: 'long', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
    let shown = 0;
    function showMore() {
      for (const edition of editions.slice(shown, shown + 20)) {
        const row = document.createElement('div');
        row.className = 'pdf-row';
        const link = document.createElement('a');
        link.href = './' + edition.pdf;
        link.addEventListener('click', event => {
          event.preventDefault();
          openPDF(link.href, 'Edició del ' + format.format(new Date(edition.updatedAt)));
        });
        link.className = 'pdf-link';
        link.textContent = '📄 ' + format.format(new Date(edition.updatedAt)) +
          ' · ' + edition.count + ' notícies';
        row.append(link);
        list.append(row);
      }
      shown += 20;
      more.hidden = shown >= editions.length;
    }
    more.addEventListener('click', showMore);
    archive.append(list, more);
    showMore();
  } catch {
    archive.replaceChildren();
    const message = document.createElement('p');
    message.className = 'small';
    message.textContent = 'No s’ha pogut carregar l’arxiu. Comprova la connexió o torna-ho a provar.';
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'cta secondary';
    retry.textContent = 'Tornar a provar';
    retry.addEventListener('click', renderArchive);
    archive.append(message, retry);
  }
}

renderArchive();

/* Local weather: only coarse coordinates are sent after explicit opt-in. */
const weatherButton = document.querySelector('#weather-enable');
const weatherStop = document.querySelector('#weather-stop');
const weatherStatus = document.querySelector('#weather-status');
const weatherResult = document.querySelector('#weather-result');
let weatherEnabled = false;
try { weatherEnabled = localStorage.getItem('diari-weather-enabled') === 'yes'; } catch {}
let weatherBusy = false;
let weatherGeneration = 0;
function weatherDescription(code) {
  if (code === 0) return '☀️ Cel serè';
  if ([1, 2].includes(code)) return '🌤️ Sol i núvols';
  if (code === 3) return '☁️ Cel cobert';
  if ([45, 48].includes(code)) return '🌫️ Boira';
  if ([51, 53, 55, 56, 57].includes(code)) return '🌦️ Plugim';
  if ([61, 63, 65, 66, 67, 80, 81, 82].includes(code)) return '🌧️ Pluja';
  if ([71, 73, 75, 77, 85, 86].includes(code)) return '🌨️ Neu';
  if ([95, 96, 99].includes(code)) return '⛈️ Tempesta';
  return 'Previsió meteorològica';
}
function weatherNumber(value, suffix) {
  return Number.isFinite(value) ? Math.round(value) + suffix : 'No disponible';
}
function rememberWeather(enabled) {
  weatherEnabled = enabled;
  try {
    if (enabled) localStorage.setItem('diari-weather-enabled', 'yes');
    else localStorage.removeItem('diari-weather-enabled');
  } catch {}
  weatherStop.hidden = !enabled;
}
async function refreshWeather() {
  if (!weatherEnabled || weatherBusy || document.hidden) return;
  const generation = weatherGeneration;
  weatherBusy = true;
  weatherButton.disabled = true;
  weatherStatus.textContent = 'Consultant el temps d’on ets…';
  try {
    if (!navigator.geolocation) throw new Error('unsupported');
    const position = await new Promise((resolve, reject) =>
      navigator.geolocation.getCurrentPosition(resolve, reject, {
        enableHighAccuracy: false, timeout: 12000, maximumAge: 60000
      })
    );
    if (!weatherEnabled || generation !== weatherGeneration) return;
    // Approximate to ~1 km; never store coordinates.
    const params = new URLSearchParams({
      latitude: position.coords.latitude.toFixed(2),
      longitude: position.coords.longitude.toFixed(2),
      current: 'temperature_2m,apparent_temperature,weather_code,wind_speed_10m',
      daily: 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
      timezone: 'auto', forecast_days: '3'
    });
    const response = await fetch('https://api.open-meteo.com/v1/forecast?' + params, {
      cache: 'no-store', signal: AbortSignal.timeout(15000)
    });
    if (!response.ok) throw new Error('unavailable');
    const data = await response.json();
    if (!data.current || !Array.isArray(data.daily?.time) || !data.daily.time.length) throw new Error('invalid');
    if (!weatherEnabled || generation !== weatherGeneration) return;
    renderWeatherCards(data);
    const time = new Intl.DateTimeFormat('ca-ES', { hour: '2-digit', minute: '2-digit' }).format(new Date());
    weatherStatus.textContent = '📍 A prop de la teva ubicació actual · Consultat a les ' + time +
      ' h. S’actualitza en obrir l’app i cada hora mentre estigui oberta.';
    weatherButton.textContent = 'Actualitzar el temps';
  } catch (error) {
    if (generation !== weatherGeneration) return;
    weatherResult.replaceChildren();
    weatherStatus.textContent = error.code === 1
      ? 'No has permès la ubicació. Pots activar-la als permisos de l’app o de Safari i tornar-ho a provar.'
      : 'No s’ha pogut consultar el temps. Comprova la connexió i la ubicació i torna-ho a provar.';
    if (error.code === 1) rememberWeather(false);
  } finally {
    weatherBusy = false;
    weatherButton.disabled = false;
  }
}
weatherButton.addEventListener('click', () => { rememberWeather(true); refreshWeather(); });
weatherStop.addEventListener('click', () => {
  ++weatherGeneration;
  rememberWeather(false);
  weatherResult.replaceChildren();
  weatherStatus.textContent = 'El temps automàtic està desactivat.';
  weatherButton.textContent = 'Activar el temps de la meva ubicació';
});
weatherStop.hidden = !weatherEnabled;
document.addEventListener('visibilitychange', () => { if (!document.hidden) refreshWeather(); });
window.addEventListener('pageshow', refreshWeather);
setInterval(refreshWeather, 60 * 60 * 1000);
refreshWeather();

function renderWeatherCards(data) {
  weatherResult.replaceChildren();
  const current = document.createElement('p');
  current.className = 'weather-now';
  current.textContent = 'Ara · ' + weatherDescription(data.current.weather_code) + ' · ' +
    weatherNumber(data.current.temperature_2m, ' °C') + ' · Sensació: ' +
    weatherNumber(data.current.apparent_temperature, ' °C') + ' · Vent: ' +
    weatherNumber(data.current.wind_speed_10m, ' km/h');
  const track = document.createElement('div');
  track.className = 'weather-track';
  track.tabIndex = 0;
  track.setAttribute('aria-label', 'Previsió per dies. Llisca o utilitza les fletxes per canviar de dia.');
  const controls = document.createElement('div');
  controls.className = 'weather-controls';
  const previous = document.createElement('button');
  const next = document.createElement('button');
  const counter = document.createElement('span');
  previous.type = next.type = 'button';
  previous.textContent = '‹';
  next.textContent = '›';
  previous.setAttribute('aria-label', 'Dia anterior');
  next.setAttribute('aria-label', 'Dia següent');
  counter.setAttribute('aria-live', 'polite');
  const cards = [];
  data.daily.time.forEach((day, i) => {
    const card = document.createElement('article');
    card.className = 'weather-card';
    const heading = document.createElement('h3');
    heading.textContent = i === 0 ? 'Avui' : i === 1 ? 'Demà' : 'Demà passat';
    const date = document.createElement('p');
    date.className = 'weather-day';
    date.textContent = new Intl.DateTimeFormat('ca-ES', {
      weekday: 'long', day: 'numeric', month: 'short', timeZone: 'UTC'
    }).format(new Date(day + 'T12:00:00Z'));
    const description = weatherDescription(data.daily.weather_code[i]);
    const icon = document.createElement('div');
    icon.className = 'weather-illustration';
    icon.setAttribute('aria-hidden', 'true');
    icon.textContent = description.includes(' ') ? description.split(' ')[0] : '🌡️';
    const condition = document.createElement('p');
    condition.className = 'weather-condition';
    condition.textContent = description.replace(/^\S+\s/, '');
    const temperatures = document.createElement('p');
    temperatures.className = 'weather-temperatures';
    temperatures.textContent = weatherNumber(data.daily.temperature_2m_max[i], '°') +
      ' / ' + weatherNumber(data.daily.temperature_2m_min[i], '°');
    const rain = document.createElement('p');
    rain.textContent = '💧 Probabilitat de pluja: ' +
      weatherNumber(data.daily.precipitation_probability_max[i], '%');
    const hint = document.createElement('p');
    hint.className = 'small';
    hint.textContent = 'Temperatura màxima / mínima';
    card.append(heading, date, icon, condition, temperatures, hint, rain);
    track.append(card);
    cards.push(card);
  });
  let selected = 0;
  function updateControls() {
    previous.disabled = selected === 0;
    next.disabled = selected === cards.length - 1;
    counter.textContent = (selected + 1) + ' / ' + cards.length;
  }
  function goTo(index) {
    selected = Math.max(0, Math.min(cards.length - 1, index));
    track.scrollTo({ left: cards[selected].offsetLeft - cards[0].offsetLeft, behavior: 'smooth' });
    updateControls();
  }
  previous.addEventListener('click', () => goTo(selected - 1));
  next.addEventListener('click', () => goTo(selected + 1));
  track.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      goTo(selected + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  track.addEventListener('scroll', () => {
    let nearest = 0;
    cards.forEach((card, i) => {
      if (Math.abs(card.offsetLeft - cards[0].offsetLeft - track.scrollLeft) <
          Math.abs(cards[nearest].offsetLeft - cards[0].offsetLeft - track.scrollLeft)) nearest = i;
    });
    selected = nearest;
    updateControls();
  }, { passive: true });
  controls.append(previous, counter, next);
  const hint = document.createElement('p');
  hint.className = 'small';
  hint.textContent = 'Llisca cap als costats per veure els altres dies ↔';
  weatherResult.append(current, track, controls, hint);
  updateControls();
}
