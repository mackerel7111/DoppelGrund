// Engine worker (C8). All per-hex loops run here: scoring, cards, stability, painting.
import { loadBundle, loadIndexMap } from '../data/loader';
import type {
  Bundle,
  GroupWeights,
  RankTarget,
  RankedResponse,
  WorkerRequest,
  WorkerResponse,
} from '../data/types';
import { eligibleMask, selectCards, topRows } from '../engine/cards';
import { featureWeights, groupIndex, scoreAll, type ScoreInputs } from '../engine/scoring';
import { applyTransforms } from '../engine/transforms';
import { StabilityAccumulator } from '../engine/stability';
import { paint, sampleIndex } from '../globe/painter';
import { GROUP_IDS, type ColorBy, type Manifest } from '../data/types';

type IndexLoader = (
  baseUrl: string,
  manifest: Manifest,
) => Promise<{ width: number; height: number; rgba: Uint8ClampedArray }>;

/** Per-row values and eligibility for the active metric (novelty does not need a rank). */
export function metricValues(
  p: Prepared,
  last: LastRank | null,
  colorBy: ColorBy,
): { values: Float32Array; eligible: Uint8Array } {
  const b = p.bundle;
  const n = b.manifest.n_hex;
  if (colorBy === 'novelty') {
    const values = new Float32Array(n);
    const eligible = new Uint8Array(n);
    for (let i = 0; i < n; i++) {
      values[i] = b.novelty[i * 2];
      eligible[i] = b.flags[i] & 1 ? 0 : 1;
    }
    return { values, eligible };
  }
  if (!last) return { values: new Float32Array(n).fill(NaN), eligible: new Uint8Array(n) };
  if (colorBy === 'S') return { values: last.S, eligible: last.eligible };
  const g = GROUP_IDS.indexOf(colorBy);
  const values = new Float32Array(n);
  for (let i = 0; i < n; i++) values[i] = last.groups[i * 4 + g];
  return { values, eligible: last.eligible };
}
import { TOP_N } from './protocol';

type Post = (msg: WorkerResponse, transfer: Transferable[]) => void;

function yieldToEventLoop(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

/** Bundle data pre-transformed once at init and cached for every request. */
export interface Prepared {
  bundle: Bundle;
  Xe: Float64Array;
  s: Float64Array;
  median: Float64Array;
  groupOfFeature: Uint8Array;
  C: Float64Array;
}

export interface LastRank {
  S: Float32Array;
  coverage: Float32Array;
  groups: Float32Array;
  eligible: Uint8Array;
}

export function prepare(bundle: Bundle): Prepared {
  const f = bundle.manifest.features;
  return {
    bundle,
    Xe: applyTransforms(
      bundle.features,
      f.length,
      f.map((x) => x.transform),
    ),
    s: Float64Array.from(f, (x) => x.s),
    median: Float64Array.from(f, (x) => x.median),
    groupOfFeature: groupIndex(f),
    C: Float64Array.from(bundle.manifest.compat_matrix.flat()),
  };
}

/** Build scoring inputs for one target and weight set. */
export function scoreInputs(p: Prepared, target: RankTarget, weights: GroupWeights): ScoreInputs {
  const f = p.bundle.manifest.features;
  const { wNum, wLith } = featureWeights(weights, f);
  const lith = Float32Array.from(target.lith);
  const lithMissing = lith.some((v) => !Number.isFinite(v));
  return {
    Xe: p.Xe,
    Le: p.bundle.lith,
    flags: p.bundle.flags,
    n: p.bundle.manifest.n_hex,
    xt: applyTransforms(
      target.features,
      f.length,
      f.map((x) => x.transform),
    ),
    lt: lithMissing ? null : lith,
    median: p.median,
    s: p.s,
    groupOfFeature: p.groupOfFeature,
    wNum,
    wLith,
    C: p.C,
  };
}

/** Score + cards + top rows for one request. */
export function rank(
  p: Prepared,
  reqId: number,
  target: RankTarget,
  weights: GroupWeights,
): { response: RankedResponse; last: LastRank } {
  const { S, coverage, groups } = scoreAll(scoreInputs(p, target, weights));
  const params = p.bundle.manifest.params;
  const cards = selectCards(S, coverage, groups, p.bundle.latlng, params);
  const eligible = eligibleMask(S, coverage, params.coverage_floor);
  const top = topRows(S, eligible, TOP_N);
  return {
    response: { type: 'ranked', reqId, S, coverage, groups, cards, top },
    last: { S: S.slice(), coverage: coverage.slice(), groups: groups.slice(), eligible },
  };
}

/** Message handler, separated from the worker global so it runs in Vitest. */
export class EngineHost {
  prepared: Prepared | null = null;
  last: LastRank | null = null;
  readonly latest: Record<string, number> = {};
  private readonly post: Post;
  private readonly load: typeof loadBundle;
  private readonly loadIndex: IndexLoader;
  private baseUrl = '';
  private index: { width: number; height: number; rows: Int32Array } | null = null;

  constructor(
    post: Post,
    load: typeof loadBundle = loadBundle,
    loadIndex: IndexLoader = loadIndexMap,
  ) {
    this.post = post;
    this.load = load;
    this.loadIndex = loadIndex;
  }

  async handle(req: WorkerRequest): Promise<void> {
    if (req.type !== 'init') this.latest[req.type] = req.reqId;
    try {
      switch (req.type) {
        case 'init': {
          this.baseUrl = req.baseUrl;
          this.prepared = prepare(await this.load(req.baseUrl));
          const m = this.prepared.bundle.manifest;
          const t0 = this.prepared.bundle.targets[0];
          if (t0) {
            // JIT warm-up so the first user-visible rank meets the budget; result discarded
            const target = { features: Array.from(t0.features), lith: Array.from(t0.lith) };
            rank(this.prepared, 0, target, m.lenses.balanced);
          }
          this.post({ type: 'ready', nHex: m.n_hex, synthetic: m.synthetic }, []);
          return;
        }
        case 'rank': {
          const p = this.requirePrepared();
          const { response, last } = rank(p, req.reqId, req.target, req.weights);
          this.last = last;
          const { S, coverage, groups, top } = response;
          this.post(response, [S.buffer, coverage.buffer, groups.buffer, top.buffer]);
          return;
        }
        case 'stability': {
          const p = this.requirePrepared();
          const m = p.bundle.manifest;
          const acc = new StabilityAccumulator(
            scoreInputs(p, req.target, req.weights),
            req.weights,
            {
              ...m.params.stability,
              seed: m.params.seed,
              coverage_floor: m.params.coverage_floor,
            },
          );
          for (let d = 0; d < req.draws; d++) {
            acc.step();
            this.post({ type: 'progress', reqId: req.reqId, done: acc.done, total: req.draws }, []);
            await yieldToEventLoop(); // lets newer requests (rank or stability) arrive
            if (this.latest.stability !== req.reqId) return; // cancelled by a newer request
          }
          this.post({ type: 'stability', reqId: req.reqId, rows: acc.result() }, []);
          return;
        }
        case 'paint': {
          const p = this.requirePrepared();
          if (!this.index) {
            const img = await this.loadIndex(this.baseUrl, p.bundle.manifest);
            const k = 4; // paint at 1/4 size: 2 MB per repaint instead of 32 MB
            this.index = {
              width: Math.floor(img.width / k),
              height: Math.floor(img.height / k),
              rows: sampleIndex(img.rgba, img.width, img.height, k),
            };
          }
          if (this.latest.paint !== req.reqId) return; // superseded while decoding
          const { values, eligible } = metricValues(p, this.last, req.colorBy);
          const rgba = paint(this.index.rows, values, req.palette, eligible);
          const { width, height } = this.index;
          this.post({ type: 'painted', reqId: req.reqId, width, height, rgba }, [rgba.buffer]);
          return;
        }
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      this.post({ type: 'error', message, ...('reqId' in req ? { reqId: req.reqId } : {}) }, []);
    }
  }

  private requirePrepared(): Prepared {
    if (!this.prepared) throw new Error('worker not initialised (send init first)');
    return this.prepared;
  }
}

interface WorkerScope {
  postMessage(msg: unknown, transfer: Transferable[]): void;
  onmessage: ((ev: MessageEvent<WorkerRequest>) => void) | null;
}

if (typeof (globalThis as { WorkerGlobalScope?: unknown }).WorkerGlobalScope !== 'undefined') {
  const scope = globalThis as unknown as WorkerScope;
  const host = new EngineHost((msg, transfer) => scope.postMessage(msg, transfer));
  scope.onmessage = (ev) => void host.handle(ev.data);
}
