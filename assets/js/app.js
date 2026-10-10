import { listPDFs, savePDF, deletePDF } from './storage.js';

const dateElement = document.querySelector('#date');
const savedElement = document.querySelector('#saved');
const statusElement = document.querySelector('#status');
const input = document.querySelector('#pdf');
let objectURLs = [];

dateElement.textContent = new Intl.DateTimeFormat('ca-ES', {
  day: 'numeric', month: 'short', year: 'numeric'
}).format(new Date());

const diaryButton = document.querySelector('#generate');
const diaryStatus = document.querySelector('#diary-status');

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
    diaryStatus.textContent = 'Obrint el PDF del dia…';
    window.location.assign('./diaris/avui.pdf?v=' + encodeURIComponent(edition.updatedAt));
  } catch {
    diaryStatus.textContent = 'No s’ha pogut obrir el diari. Comprova la connexió i torna-ho a provar.';
  } finally {
    diaryButton.disabled = false;
  }
});

document.querySelector('#install').addEventListener('click', () => {
  alert('A l’iPhone, obre la pàgina amb Safari, toca Compartir i tria «Afegir a la pantalla d’inici».');
});

function setStatus(message) {
  statusElement.textContent = message;
}

async function renderPDFs() {
  objectURLs.forEach(url => URL.revokeObjectURL(url));
  objectURLs = [];
  savedElement.replaceChildren();

  try {
    const records = await listPDFs();
    if (!records.length) {
      const empty = document.createElement('p');
      empty.className = 'small';
      empty.textContent = 'Encara no hi ha cap PDF guardat en aquest dispositiu.';
      savedElement.append(empty);
      return;
    }

    for (const record of records.reverse()) {
      const row = document.createElement('div');
      row.className = 'pdf-row';

      const link = document.createElement('a');
      const url = URL.createObjectURL(record.file);
      objectURLs.push(url);
      link.href = url;
      link.target = '_blank';
      link.rel = 'noopener';
      link.download = record.name;
      link.className = 'pdf-link';
      link.textContent = '📄 ' + record.name;

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'pdf-delete';
      remove.textContent = 'Eliminar';
      remove.addEventListener('click', async () => {
        if (!confirm('Vols eliminar aquest PDF de la biblioteca?')) return;
        try {
          await deletePDF(record.id);
          setStatus('PDF eliminat.');
          await renderPDFs();
        } catch {
          setStatus('No s’ha pogut eliminar el PDF.');
        }
      });

      row.append(link, remove);
      savedElement.append(row);
    }
  } catch {
    setStatus('No s’ha pogut accedir a l’emmagatzematge d’aquest dispositiu.');
  }
}

input.addEventListener('change', async event => {
  const files = [...event.target.files];
  if (!files.length) return;
  let count = 0;

  try {
    for (const file of files) {
      if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) continue;
      await savePDF(file);
      count++;
    }
    setStatus(count ? `${count} PDF desat(s) en aquest dispositiu.` : 'Selecciona un fitxer PDF.');
    await renderPDFs();
  } catch {
    setStatus('No s’ha pogut guardar el PDF. Comprova l’espai disponible.');
  } finally {
    input.value = '';
  }
});

renderPDFs();
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('./sw.js').catch(() => {});
}

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
