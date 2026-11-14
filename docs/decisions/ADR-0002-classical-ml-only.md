# ADR-0002: Classical methods only

- Status: accepted
- Context: ~85k Earth rows and only ~30-50 labelled analogue pairs; no ground truth for "true analogue"; free CPU compute; judges reward validity.
- Decision: Tolerance-kernel scoring (numerical method), PCA + HDBSCAN/GMM (unsupervised), weight calibration by regularised optimisation (weakly supervised), statistics for novelty and stability. No neural networks.
- Consequences: Explainable, fast, reproducible. Every ML component must beat the profile-weighted baseline on rediscovery metrics or be reported as an exploration.
