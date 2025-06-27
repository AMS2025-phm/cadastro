const CACHE_NAME = 'levantamento-medidas-cache-v1';
const urlsToCache = [
    '/',
    '/index.html',
    '/style.css',
    '/sw.js', // Certifique-se de cachear o próprio Service Worker
    '/localidades.json', // Se o frontend busca este arquivo
    // Inclua quaisquer outros arquivos JS, imagens, fontes que seu frontend usa
    'https://cdn.tailwindcss.com/', // Cacheie libs externas se precisar offline (com cautela)
    'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap'
];

self.addEventListener('install', event => {
    console.log('Service Worker: Instalação iniciada...');
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => {
                console.log('Service Worker: Cache aberto, adicionando arquivos...');
                // Adicione todos os URLs críticos ao cache. Falha em um URL pode falhar o install.
                return cache.addAll(urlsToCache);
            })
            .then(() => self.skipWaiting())
            .catch(error => {
                console.error('Service Worker: Falha ao cachear arquivos durante a instalação:', error);
            })
    );
});

self.addEventListener('activate', event => {
    console.log('Service Worker: Ativação iniciada...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(cacheName => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('Service Worker: Deletando cache antigo:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        }).then(() => self.clients.claim()) // Permite que o SW controle as páginas imediatamente
    );
});

self.addEventListener('fetch', event => {
    event.respondWith(
        caches.match(event.request)
            .then(response => {
                // Retorna o recurso do cache se encontrado
                if (response) {
                    return response;
                }
                // Se não encontrado no cache, faz a requisição à rede
                return fetch(event.request).then(
                    networkResponse => {
                        // Se a requisição de rede for bem-sucedida, clone a resposta
                        // e adicione ao cache antes de retorná-la.
                        if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic') {
                            return networkResponse;
                        }
                        const responseToCache = networkResponse.clone();
                        caches.open(CACHE_NAME)
                            .then(cache => {
                                cache.put(event.request, responseToCache);
                            });
                        return networkResponse;
                    }
                );
            })
            .catch(() => {
                // Se tudo falhar (cache e rede), você pode retornar uma página offline personalizada
                // return caches.match('/offline.html'); // Se você tiver uma página offline
                console.log('Offline: Falha ao buscar recurso da rede e cache.');
                // Pode retornar um fallback ou um Response vazio, dependendo da necessidade
                return new Response(null, { status: 503, statusText: 'Service Unavailable' });
            })
    );
});


// Variáveis e Funções para IndexedDB (repetidas aqui para SW, mas idealmente seriam um módulo compartilhado)
const DB_NAME = 'levantamentoMedidasDB';
const DB_VERSION = 1;
const STORE_NAME = 'unidades';

let db; // Variável global para a instância do DB no Service Worker

async function openDB_SW() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(DB_NAME, DB_VERSION);

        request.onupgradeneeded = event => {
            db = event.target.result;
            if (!db.objectStoreNames.contains(STORE_NAME)) {
                db.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
            }
        };

        request.onsuccess = event => {
            db = event.target.result;
            resolve(db);
        };

        request.onerror = event => {
            console.error('Service Worker: Erro ao abrir IndexedDB:', event.target.error);
            reject(event.target.error);
        };
    });
}

async function getUnits_SW() {
    await openDB_SW();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, 'readonly');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.getAll();

        request.onsuccess = () => resolve(request.result);
        request.onerror = () => reject(request.error);
    });
}

async function deleteUnit_SW(id) {
    await openDB_SW();
    return new Promise((resolve, reject) => {
        const transaction = db.transaction(STORE_NAME, 'readwrite');
        const store = transaction.objectStore(STORE_NAME);
        const request = store.delete(id);

        request.onsuccess = () => resolve();
        request.onerror = () => reject(request.error);
    });
}

// --- Evento 'sync' para Background Sync ---
self.addEventListener('sync', event => {
    if (event.tag === 'sync-pending-units') {
        console.log('Service Worker: Evento de sincronização acionado para "sync-pending-units".');
        event.waitUntil(syncUnitsWithServer_SW());
    }
});

async function syncUnitsWithServer_SW() {
    const unitsToSend = await getUnits_SW(); // Pega todas as unidades do IndexedDB
    if (unitsToSend.length === 0) {
        console.log('Service Worker: Nenhum dado pendente para sincronizar.');
        return;
    }

    // Usar a mesma BASE_URL que o frontend, ou uma específica para o SW
    // IMPORTANTE: Altere para a URL do seu backend no Render
   //const BASE_URL_SW = 'http://127.0.0.1:5000'; // ALtere para a URL do seu backend no Render em produção!
   //const BASE_URL_SW = 'https://https://levantamento-377s.onrender.com';
     const BASE_URL_SW = self.location.origin;

    console.log(`Service Worker: Tentando sincronizar ${unitsToSend.length} unidades pendentes...`);

    for (const unit of unitsToSend) {
        try {
            const response = await fetch(`${BASE_URL_SW}/submit_levantamento`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(unit.data) // Envia o 'data' completo salvo no IndexedDB
            });

            if (response.ok) {
                const result = await response.json();
                if (result.status === 'success') {
                    console.log(`Service Worker: Dados sincronizados com sucesso: ${unit.id}`);
                    await deleteUnit_SW(unit.id); // Remove do IndexedDB após sucesso
                    // Opcional: Notificar o cliente (main thread) que uma unidade foi sincronizada
                    self.clients.matchAll().then(clients => {
                        clients.forEach(client => {
                            client.postMessage({ type: 'UNIT_SYNCED', id: unit.id, message: `Dados de ${unit.localidade} sincronizados.` });
                        });
                    });
                } else {
                    console.error(`Service Worker: Falha ao sincronizar ${unit.id}:`, result.message);
                    // Não remove do IndexedDB para tentar novamente depois
                }
            } else {
                console.error(`Service Worker: Falha na rede ao sincronizar ${unit.id}. Status: ${response.status}`);
                // Não remove do IndexedDB para tentar novamente depois (erro de rede)
            }
        } catch (innerError) {
            console.error(`Service Worker: Erro ao processar unidade ${unit.id} para sincronização:`, innerError);
            // Continua para a próxima unidade, o dado permanece no IndexedDB
        }
    }
    console.log('Service Worker: Sincronização em segundo plano concluída.');

    // Notificar o cliente (main thread) que a sincronização geral está concluída
    self.clients.matchAll().then(clients => {
        clients.forEach(client => {
            client.postMessage({ type: 'SYNC_COMPLETE', message: 'Sincronização em segundo plano concluída.' });
        });
    });
}