# ADR-0003: three-globe for the 3D view; deck.gl for 2D

- Status: proposed (confirm at H0 based on team experience; CesiumJS is the fallback if a team member already knows it)
- Context: The 3D view needs textured Moon/Mars/Earth spheres, markers, arcs between two globes, and a dynamic heat-map texture. No terrain streaming is needed (data is ~470 m; footprints ~47 km). deck.gl GlobeView is experimental and Earth-only.
- Decision: 2D first with deck.gl (MapView for Earth, OrthographicView for Moon/Mars). 3D upgrade with three.js + three-globe: two globe objects in one scene, Earth texture painted by the worker from the hex index map.
- Consequences: Low risk, light bundle, arcs are simple curves. Picking and painting are custom code (owned by spec 03 tasks 3.14-3.16).
