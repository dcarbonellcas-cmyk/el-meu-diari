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

function madridDate() {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Europe/Madrid', year: 'numeric', month: '2-digit', day: '2-digit'
  }).formatToParts(new Date());
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

async function renderArchive() {
  const archive = document.querySelector('#archive');
  try {
    const response = await fetch('./diaris/archive.json', { cache: 'no-store' });
    if (!response.ok) throw new Error('archive unavailable');
    const catalog = await response.json();
    if (!Array.isArray(catalog.editions)) throw new Error('invalid archive');
    archive.replaceChildren();
    const editions = catalog.editions.filter(edition =>
      /^diaris\/arxiu\/\d{4}-\d{2}-\d{2}\/\d{2}-\d{2}-\d{2}-\d{6}\.pdf$/.test(edition.pdf) &&
      !Number.isNaN(new Date(edition.updatedAt).getTime())
    );
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
