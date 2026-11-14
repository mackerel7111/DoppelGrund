import { createApp } from 'vue';
import { createPinia } from 'pinia';
import App from './App.vue';
import { loadBundle, loadImageBitmap, loadLayer, loadStability } from './data/loader';
import { useSession } from './stores/session';
import { EngineClient, createEngineWorker } from './workers/client';
import './styles/base.css';

/** Same-origin bundle URL; `?bundle=<name>` selects web/public/data/<name>/ (e.g. "sample"). */
function bundleBaseUrl(): string {
  const name = new URLSearchParams(window.location.search).get('bundle');
  const sub = name && /^[a-z0-9_-]+$/.test(name) ? `${name}/` : '';
  return new URL(`${import.meta.env.BASE_URL}data/${sub}`, window.location.origin).href;
}

const pinia = createPinia();
const app = createApp(App);
app.use(pinia);
app.mount('#app');

const store = useSession(pinia);
const base = bundleBaseUrl();
const client = new EngineClient(createEngineWorker());
const t0 = performance.now();
store.loading.phase = 'loading';

Promise.all([
  loadBundle(base, (done, total) => {
    store.loading.done = done;
    store.loading.total = total;
  }),
  client.init(base),
])
  .then(([bundle, ready]) => {
    store.setBundle(bundle);
    store.synthetic = ready.synthetic;
    store.attach({
      engine: client,
      fetchStability: (id, lens) => loadStability(base, id, lens),
      fetchImage: (file) => loadImageBitmap(base, file),
      fetchLayer: (id) => loadLayer(base, id),
    });
    store.timings.loadMs = performance.now() - t0;
    store.loading.phase = 'ready';
  })
  .catch((e: unknown) => {
    store.loading.phase = 'error';
    store.loading.error = e instanceof Error ? e.message : String(e);
  });
