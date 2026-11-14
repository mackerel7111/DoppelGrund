// Promise wrapper around the engine worker: reqId per request, latest wins per request type.
import type {
  ColorBy,
  GroupWeights,
  PaintedResponse,
  Palette,
  RankTarget,
  RankedResponse,
  ReadyResponse,
  WorkerRequest,
  WorkerResponse,
} from '../data/types';
import type { EngineLike } from '../stores/session';
import { isWorkerResponse, kindOf, type RequestKind } from './protocol';

export interface WorkerLike {
  postMessage(msg: WorkerRequest, transfer?: Transferable[]): void;
  onmessage: ((ev: MessageEvent<unknown>) => void) | null;
  onerror: ((ev: ErrorEvent) => void) | null;
  terminate(): void;
}

interface Pending {
  kind: RequestKind;
  resolve: (v: WorkerResponse | null) => void;
  reject: (e: Error) => void;
  onProgress?: (done: number, total: number) => void;
}

export function createEngineWorker(): WorkerLike {
  return new Worker(new URL('./engine.worker.ts', import.meta.url), {
    type: 'module',
  }) as unknown as WorkerLike;
}

export class EngineClient implements EngineLike {
  private readonly worker: WorkerLike;
  private nextId = 1;
  private readonly latest: Partial<Record<RequestKind, number>> = {};
  private readonly pending = new Map<number, Pending>();
  private ready: { resolve: (r: ReadyResponse) => void; reject: (e: Error) => void } | null = null;

  constructor(worker: WorkerLike) {
    this.worker = worker;
    worker.onmessage = (ev) => this.onMessage(ev.data);
    worker.onerror = (ev) => {
      const err = new Error(`engine worker error: ${ev.message}`);
      this.ready?.reject(err);
      for (const p of this.pending.values()) p.reject(err);
      this.pending.clear();
    };
  }

  init(baseUrl: string): Promise<ReadyResponse> {
    return new Promise((resolve, reject) => {
      this.ready = { resolve, reject };
      this.worker.postMessage({ type: 'init', baseUrl });
    });
  }

  rank(target: RankTarget, weights: GroupWeights): Promise<RankedResponse | null> {
    return this.request('rank', (reqId) => ({
      type: 'rank',
      reqId,
      target,
      weights,
    })) as Promise<RankedResponse | null>;
  }

  async stability(
    target: RankTarget,
    weights: GroupWeights,
    draws: number,
    onProgress: (done: number, total: number) => void,
  ): Promise<[number, number][] | null> {
    const res = await this.request(
      'stability',
      (reqId) => ({ type: 'stability', reqId, target, weights, draws }),
      onProgress,
    );
    return res && res.type === 'stability' ? res.rows : null;
  }

  paint(colorBy: ColorBy, palette: Palette): Promise<PaintedResponse | null> {
    return this.request('paint', (reqId) => ({
      type: 'paint',
      reqId,
      colorBy,
      palette,
    })) as Promise<PaintedResponse | null>;
  }

  terminate(): void {
    this.worker.terminate();
  }

  private request(
    kind: RequestKind,
    build: (reqId: number) => WorkerRequest,
    onProgress?: (done: number, total: number) => void,
  ): Promise<WorkerResponse | null> {
    const reqId = this.nextId++;
    // latest wins: an older pending request of the same kind resolves to null now
    for (const [id, p] of this.pending) {
      if (p.kind === kind) {
        p.resolve(null);
        this.pending.delete(id);
      }
    }
    this.latest[kind] = reqId;
    return new Promise((resolve, reject) => {
      this.pending.set(reqId, { kind, resolve, reject, onProgress });
      this.worker.postMessage(build(reqId));
    });
  }

  private onMessage(data: unknown): void {
    if (!isWorkerResponse(data)) return;
    if (data.type === 'ready') {
      this.ready?.resolve(data);
      this.ready = null;
      return;
    }
    if (data.type === 'error' && data.reqId === undefined) {
      this.ready?.reject(new Error(data.message));
      this.ready = null;
      return;
    }
    const reqId = data.reqId as number;
    const p = this.pending.get(reqId);
    if (!p) return; // stale: already superseded
    const kind = data.type === 'error' ? p.kind : kindOf(data);
    if (kind !== 'init' && (this.latest[kind] ?? 0) > reqId) {
      p.resolve(null);
      this.pending.delete(reqId);
      return;
    }
    if (data.type === 'progress') {
      p.onProgress?.(data.done, data.total);
      return;
    }
    this.pending.delete(reqId);
    if (data.type === 'error') p.reject(new Error(data.message));
    else p.resolve(data);
  }
}
