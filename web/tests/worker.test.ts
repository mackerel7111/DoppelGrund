import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { existsSync, readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { loadBundle } from '../src/data/loader';
import type { Bundle, RankTarget, WorkerRequest, WorkerResponse } from '../src/data/types';
import { EngineHost, prepare, rank } from '../src/workers/engine.worker';
import { EngineClient, type WorkerLike } from '../src/workers/client';
import { TOP_N } from '../src/workers/protocol';

const SAMPLE = fileURLToPath(new URL('../public/data/sample/', import.meta.url));
const BASE = 'http://doppelgrund.test/data/sample/';
const BAL = { terrain: 0.25, thermal: 0.25, cold_ice: 0.25, composition: 0.25 };

async function sampleBundle(): Promise<Bundle> {
  vi.stubGlobal('fetch', async (url: string) => {
    const path = SAMPLE + url.slice(BASE.length);
    return existsSync(path)
      ? new Response(new Uint8Array(readFileSync(path)))
      : new Response('', { status: 404 });
  });
  try {
    return await loadBundle(BASE);
  } finally {
    vi.unstubAllGlobals();
  }
}

function targetOf(b: Bundle, i = 0): RankTarget {
  return { features: Array.from(b.targets[i].features), lith: Array.from(b.targets[i].lith) };
}

/** In-memory replica of the sample rows tiled to n rows (CONTRACT ISSUE: 85k rank budget). */
function replicate(b: Bundle, n: number): Bundle {
  const m = b.manifest.n_hex;
  const tile = <T extends Float32Array | Uint8Array | Int16Array>(a: T, w: number): T => {
    const out = new (a.constructor as new (len: number) => T)(n * w);
    for (let i = 0; i < n; i++) out.set(a.subarray((i % m) * w, (i % m) * w + w), i * w);
    return out;
  };
  const latlng = tile(b.latlng, 2);
  for (let i = 0; i < n; i++)
    latlng[i * 2 + 1] = ((latlng[i * 2 + 1] + 180 + (i / m) * 7) % 360) - 180;
  return {
    ...b,
    manifest: { ...b.manifest, n_hex: n },
    h3: Array.from({ length: n }, (_, i) => b.h3[i % m]),
    features: tile(b.features, 10),
    lith: tile(b.lith, 6),
    latlng,
    novelty: tile(b.novelty, 2),
    cluster: tile(b.cluster, 1),
    flags: tile(b.flags, 1),
  };
}

let bundle: Bundle;
beforeAll(async () => {
  bundle = await sampleBundle();
});
afterEach(() => vi.unstubAllGlobals());

describe('EngineHost', () => {
  it('init → ready with nHex and synthetic flag', async () => {
    const out: WorkerResponse[] = [];
    const host = new EngineHost(
      (m) => out.push(m),
      async () => bundle,
    );
    await host.handle({ type: 'init', baseUrl: BASE });
    expect(out[0]).toEqual({ type: 'ready', nHex: bundle.manifest.n_hex, synthetic: true });
  });

  it('rank returns transferred N-length buffers, five cards and ≤ 200 sorted top rows', async () => {
    const out: [WorkerResponse, Transferable[]][] = [];
    const host = new EngineHost(
      (m, t) => out.push([m, t]),
      async () => bundle,
    );
    await host.handle({ type: 'init', baseUrl: BASE });
    await host.handle({ type: 'rank', reqId: 7, target: targetOf(bundle), weights: BAL });
    const [res, transfer] = out[1];
    if (res.type !== 'ranked') throw new Error(`expected ranked, got ${res.type}`);
    const n = bundle.manifest.n_hex;
    expect(res.reqId).toBe(7);
    expect(res.S).toHaveLength(n);
    expect(res.groups).toHaveLength(n * 4);
    expect(res.cards.map((c) => c.kind)).toEqual([
      'overall',
      'terrain',
      'thermal',
      'cold_ice',
      'composition',
    ]);
    expect(res.top.length).toBeLessThanOrEqual(TOP_N);
    for (let i = 1; i < res.top.length; i++)
      expect(res.S[res.top[i - 1]]).toBeGreaterThanOrEqual(res.S[res.top[i]]);
    expect(transfer).toHaveLength(4);
    expect(res.cards[0].row).toBe(res.top[0]);
    for (let i = 0; i < n; i++) if (bundle.flags[i] & 1) expect(Number.isNaN(res.S[i])).toBe(true);
    expect(host.last?.S).toHaveLength(n); // worker keeps its own copy for painting
  });

  it('rank before init reports an error with the reqId', async () => {
    const out: WorkerResponse[] = [];
    const host = new EngineHost((m) => out.push(m));
    await host.handle({ type: 'rank', reqId: 3, target: targetOf(bundle), weights: BAL });
    expect(out[0]).toMatchObject({ type: 'error', reqId: 3 });
  });

  it('ranks 85,000 rows within the 150 ms budget (median of 5)', () => {
    const p = prepare(replicate(bundle, 85_000));
    const t = targetOf(bundle);
    const times: number[] = [];
    for (let k = 0; k < 6; k++) {
      const t0 = performance.now();
      rank(p, k, t, BAL);
      times.push(performance.now() - t0);
    }
    times.shift(); // JIT warm-up
    times.sort((a, b) => a - b);
    const median = times[2];
    console.info(
      `[perf] rank 85k rows: median ${median.toFixed(1)} ms (runs ${times.map((x) => x.toFixed(0)).join(', ')})`,
    );
    expect(median).toBeLessThan(150);
  });
});

/** Fake worker that answers asynchronously through EngineHost. */
function fakeWorker(host: { current: EngineHost | null }): WorkerLike {
  const w: WorkerLike = {
    onmessage: null,
    onerror: null,
    terminate: () => {},
    postMessage: (msg: WorkerRequest) => {
      setTimeout(() => void host.current?.handle(msg), 0);
    },
  };
  host.current = new EngineHost(
    (m) => w.onmessage?.({ data: m } as MessageEvent<unknown>),
    async () => bundle,
  );
  return w;
}

describe('EngineClient', () => {
  it('resolves init with ready and resolves only the latest rank (latest wins)', async () => {
    const ref: { current: EngineHost | null } = { current: null };
    const client = new EngineClient(fakeWorker(ref));
    const ready = await client.init(BASE);
    expect(ready.synthetic).toBe(true);
    const first = client.rank(targetOf(bundle, 0), BAL);
    const second = client.rank(targetOf(bundle, 1), BAL);
    expect(await first).toBeNull();
    const res = await second;
    expect(res?.type).toBe('ranked');
    expect(res?.reqId).toBe(2);
  });

  it('drops a stale response that arrives after a newer request', async () => {
    const posted: WorkerRequest[] = [];
    const w: WorkerLike = {
      onmessage: null,
      onerror: null,
      terminate: () => {},
      postMessage: (m) => posted.push(m),
    };
    const client = new EngineClient(w);
    const a = client.rank(targetOf(bundle), BAL);
    const b = client.rank(targetOf(bundle), BAL);
    const mk = (reqId: number) => ({
      type: 'ranked',
      reqId,
      S: new Float32Array(),
      coverage: new Float32Array(),
      groups: new Float32Array(),
      cards: [],
      top: new Int32Array(),
    });
    w.onmessage?.({ data: mk(1) } as MessageEvent<unknown>);
    w.onmessage?.({ data: mk(2) } as MessageEvent<unknown>);
    expect(await a).toBeNull();
    expect((await b)?.reqId).toBe(2);
    expect(posted.map((p) => p.type)).toEqual(['rank', 'rank']);
  });

  it('rejects when the worker reports an error for a request', async () => {
    const w: WorkerLike = {
      onmessage: null,
      onerror: null,
      terminate: () => {},
      postMessage: () => {},
    };
    const client = new EngineClient(w);
    const a = client.rank(targetOf(bundle), BAL);
    w.onmessage?.({ data: { type: 'error', reqId: 1, message: 'boom' } } as MessageEvent<unknown>);
    await expect(a).rejects.toThrow('boom');
  });
});
