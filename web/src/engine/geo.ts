// Great-circle distances (C5.4).
export const EARTH_R_KM = 6371.0088;

const RAD = Math.PI / 180;

/** Haversine distance in km between two (lat, lon) points in degrees. */
export function haversineKm(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
  rKm = EARTH_R_KM,
): number {
  const p1 = lat1 * RAD;
  const p2 = lat2 * RAD;
  const dp = p2 - p1;
  const dl = (lon2 - lon1) * RAD;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * rKm * Math.asin(Math.sqrt(Math.min(1, Math.max(0, a))));
}
