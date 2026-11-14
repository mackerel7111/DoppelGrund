# ADR-0001: Static-first web app, scoring in the browser

- Status: accepted (pre-event planning)
- Context: All heavy computation is offline. The live app ranks ~85,000 rows × ~11 features against one target, which takes milliseconds in a Web Worker. Demo-day network and server failures are a real risk.
- Decision: No backend. The pipeline exports a static bundle (contract C6); the browser loads it and scores in a worker. Python `doppelgrund/scoring.py` stays the reference; TypeScript must pass parity vectors (C7).
- Consequences: Instant slider re-ranking, offline demo, free hosting. Cost: two scorer implementations kept in sync by a parity test. Arbitrary-click targets need precomputed disc grids.
