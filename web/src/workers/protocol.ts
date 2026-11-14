// C8 worker protocol. Message types live in data/types.ts (contract mirror); re-exported here.
export type {
  ColorBy,
  ErrorResponse,
  InitRequest,
  PaintRequest,
  PaintedResponse,
  Palette,
  ProgressResponse,
  RankRequest,
  RankTarget,
  RankedResponse,
  ReadyResponse,
  StabilityRequest,
  StabilityResponse,
  WorkerRequest,
  WorkerResponse,
} from '../data/types';

import type { WorkerRequest, WorkerResponse } from '../data/types';

/** C8: `top` holds the best 200 eligible rows. */
export const TOP_N = 200;

/** Request types that follow the latest-wins rule. */
export type RequestKind = Exclude<WorkerRequest['type'], 'init'>;

const RESPONSE_TYPES = new Set(['ready', 'error', 'ranked', 'progress', 'stability', 'painted']);

export function isWorkerResponse(v: unknown): v is WorkerResponse {
  return (
    typeof v === 'object' &&
    v !== null &&
    RESPONSE_TYPES.has(String((v as { type?: unknown }).type))
  );
}

/** Which request kind a response answers. */
export function kindOf(res: WorkerResponse): RequestKind | 'init' {
  switch (res.type) {
    case 'ranked':
      return 'rank';
    case 'progress':
    case 'stability':
      return 'stability';
    case 'painted':
      return 'paint';
    default:
      return 'init';
  }
}
