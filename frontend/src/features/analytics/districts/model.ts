import type { District, Registration, PublicCharger, PublicTariff } from "../data/schemas";
export type Point = [number, number];
export interface DistrictShape {
  lgd_code: number;
  rings: Point[][];
}
export interface Atlas {
  registrations: Registration[];
  chargers: PublicCharger[];
  tariffs: PublicTariff[];
  shapes: DistrictShape[];
}
export interface Topology {
  transform?: { scale: Point; translate: Point };
  arcs: Point[][];
  objects: {
    districts: {
      geometries: {
        type: "Polygon" | "MultiPolygon";
        properties: { lgd_code: number };
        arcs: number[][] | number[][][];
      }[];
    };
  };
}
// Called only after the Part 2 build gate validates arcs, joins and EPSG:4326.
export function decodeTopology(topology: Topology): DistrictShape[] {
  const arcs = topology.arcs.map((arc) => {
    let x = 0,
      y = 0;
    return arc.map(([a, b]): Point => {
      if (!topology.transform) return [a, b];
      x += a;
      y += b;
      return [
        x * topology.transform.scale[0] + topology.transform.translate[0],
        y * topology.transform.scale[1] + topology.transform.translate[1],
      ];
    });
  });
  return topology.objects.districts.geometries.map((geometry) => ({
    lgd_code: geometry.properties.lgd_code,
    rings: (geometry.type === "Polygon"
      ? (geometry.arcs as number[][])
      : (geometry.arcs as number[][][]).flat()
    ).map((ring) =>
      ring.flatMap((ref, index) => {
        const arc = ref < 0 ? [...arcs[-ref - 1]!].reverse() : arcs[ref]!;
        return index ? arc.slice(1) : arc;
      }),
    ),
  }));
}
export function monthOffset(month: string, offset: number) {
  const [year, m] = month.split("-").map(Number);
  const date = new Date(Date.UTC(year!, m! - 1 + offset, 1));
  return date.toISOString().slice(0, 7);
}
export function latestMonth(atlas: Atlas) {
  return (
    atlas.registrations
      .map((row) => row.month)
      .sort()
      .at(-1) ?? null
  );
}
const classes = ["2W", "3W", "4W", "bus", "goods"] as const;
export function registrationTotal(
  atlas: Atlas,
  code: number,
  end: string | null,
  months = 12,
): number | null {
  if (!end) return null;
  let total = 0;
  for (let index = 0; index < months; index++)
    for (const vehicleClass of classes) {
      const cells = atlas.registrations.filter(
        (row) =>
          row.lgd_code === code &&
          row.month === monthOffset(end, -index) &&
          row.vehicle_class === vehicleClass,
      );
      if (!cells.length) return null;
      total += cells.reduce((sum, row) => sum + row.count, 0);
    }
  return total;
}
export type Indicator = "registrations" | "chargers" | "ratio" | "usage";
export const indicatorLabels: Record<Indicator, string> = {
  registrations: "EV registrations (latest 12 months)",
  chargers: "Listed public chargers",
  ratio: "Listed chargers per 1,000 EV registrations",
  usage: "Estimated monthly kWh per charger",
};
export interface DistrictValue {
  value: number | null;
  p10?: number;
  p90?: number;
  sample_size?: number;
  note?: string;
}
export function districtValue(atlas: Atlas, code: number, indicator: Indicator): DistrictValue {
  const registrations = registrationTotal(atlas, code, latestMonth(atlas));
  const listed = atlas.chargers.filter((row) => row.lgd_code === code).length;
  if (indicator === "registrations") return { value: registrations };
  if (indicator === "chargers") return { value: listed || null };
  if (indicator === "ratio")
    return {
      value:
        registrations != null && registrations > 0 && listed > 0
          ? (listed / registrations) * 1000
          : null,
    };
  return { value: null };
}
export function hasDistrictIndicator(atlas: Atlas, district: District) {
  return (
    atlas.registrations.some((row) => row.lgd_code === district.lgd_code) ||
    atlas.chargers.some((row) => row.lgd_code === district.lgd_code) ||
    atlas.tariffs.some((row) => row.state === district.state_name)
  );
}
export function neighbourCodes(shapes: DistrictShape[], code: number): number[] {
  const edges = (shape: DistrictShape) =>
    new Set(
      shape.rings.flatMap((ring) =>
        ring
          .slice(1)
          .map((point, index) =>
            [JSON.stringify(ring[index]), JSON.stringify(point)].sort().join("|"),
          ),
      ),
    );
  const target = shapes.find((shape) => shape.lgd_code === code);
  if (!target) return [];
  const targetEdges = edges(target);
  return shapes
    .filter(
      (shape) => shape.lgd_code !== code && [...edges(shape)].some((edge) => targetEdges.has(edge)),
    )
    .map((shape) => shape.lgd_code);
}
