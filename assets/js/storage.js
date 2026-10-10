// IndexedDB: els PDF es guarden només en aquest dispositiu.
const DB_NAME = 'els-meus-diaris';
const STORE_NAME = 'pdfs';

function openDatabase() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, 1);
    request.onupgradeneeded = () => {
      if (!request.result.objectStoreNames.contains(STORE_NAME)) {
        request.result.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

async function transact(mode, action) {
  const db = await openDatabase();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE_NAME, mode);
    const request = action(tx.objectStore(STORE_NAME));
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
    tx.onerror = () => reject(tx.error);
  }).finally(() => db.close());
}

export const listPDFs = () => transact('readonly', store => store.getAll());
export const savePDF = file => transact('readwrite', store =>
  store.add({ name: file.name, file, date: Date.now() }));
export const deletePDF = id => transact('readwrite', store => store.delete(id));
