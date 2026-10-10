import { listPDFs, savePDF, deletePDF } from './storage.js';

const prompt = 'El meu diari d’avui. Genera’m el PDF visual complet amb notícies actuals verificades, una notícia per pàgina, imatges grans i explicacions breus en català, seguint el format de la revista que t’he adjuntat. Inclou totes les notícies importants que puguis verificar, de diverses categories, amb fonts directes.';
const dateElement = document.querySelector('#date');
const savedElement = document.querySelector('#saved');
const statusElement = document.querySelector('#status');
const input = document.querySelector('#pdf');
let objectURLs = [];

dateElement.textContent = new Intl.DateTimeFormat('ca-ES', {
  day: 'numeric', month: 'short', year: 'numeric'
}).format(new Date());

document.querySelector('#generate').addEventListener('click', () => {
  window.location.href = 'https://chatgpt.com/?q=' + encodeURIComponent(prompt);
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
