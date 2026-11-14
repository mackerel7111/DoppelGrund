// Arcs from the target on the body globe to each match card on the Earth globe:
// THREE.Line along a QuadraticBezierCurve3 whose control point is lifted above the midpoint.
import * as THREE from 'three';

export const ARC_SEGMENTS = 64;

/** Control point: midpoint lifted by `lift` × chord length along +y and toward the camera (+z). */
export function arcControl(a: THREE.Vector3, b: THREE.Vector3, lift = 0.35): THREE.Vector3 {
  const mid = a.clone().add(b).multiplyScalar(0.5);
  const h = a.distanceTo(b) * lift;
  return mid.add(new THREE.Vector3(0, h, h * 0.6));
}

export function arcPoints(a: THREE.Vector3, b: THREE.Vector3, n = ARC_SEGMENTS): THREE.Vector3[] {
  return new THREE.QuadraticBezierCurve3(a, arcControl(a, b), b).getPoints(n);
}

export class Arcs {
  private readonly group = new THREE.Group();
  private readonly lines: THREE.Line<THREE.BufferGeometry, THREE.LineBasicMaterial>[] = [];

  constructor(scene: THREE.Scene) {
    this.group.name = 'match-arcs';
    scene.add(this.group);
  }

  /** Redraw one arc per destination, `opacity[i]` each (cheap: ≤ 5 × 65 vertices; every frame). */
  update(from: THREE.Vector3 | null, to: THREE.Vector3[], opacity: number[]): void {
    const n = from ? to.length : 0;
    while (this.lines.length < n) {
      const geom = new THREE.BufferGeometry();
      geom.setAttribute(
        'position',
        new THREE.BufferAttribute(new Float32Array((ARC_SEGMENTS + 1) * 3), 3),
      );
      const mat = new THREE.LineBasicMaterial({ color: 0x4fc3f7, transparent: true, opacity: 0.9 });
      const line = new THREE.Line(geom, mat);
      this.lines.push(line);
      this.group.add(line);
    }
    this.lines.forEach((line, i) => {
      line.visible = i < n;
      if (!line.visible || !from) return;
      const pts = arcPoints(from, to[i]);
      const attr = line.geometry.getAttribute('position') as THREE.BufferAttribute;
      pts.forEach((p, k) => attr.setXYZ(k, p.x, p.y, p.z));
      attr.needsUpdate = true;
      line.geometry.computeBoundingSphere();
      line.material.opacity = opacity[i];
      line.material.depthTest = opacity[i] >= 0.5; // faint far-side arcs show through the globe
    });
  }

  dispose(): void {
    for (const l of this.lines) {
      l.geometry.dispose();
      l.material.dispose();
    }
    this.group.removeFromParent();
  }
}
