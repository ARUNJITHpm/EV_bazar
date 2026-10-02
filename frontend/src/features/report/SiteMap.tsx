/** Recorded coordinates only; report viewing makes no paid imagery requests. */
export function SiteMap({ lat, lng, name }: { lat: number; lng: number; name: string }) {
  return (
    <div className="border-y border-cw-rule py-4">
      <p className="m-0 font-cw-mono text-[14px] tabular-nums">
        {lat.toFixed(5)}, {lng.toFixed(5)}
      </p>
      <p className="mt-2 mb-0 text-[15px] text-cw-paper-muted">
        Recorded location for {name}. Satellite imagery and a verified plot boundary are not
        included in this report.
      </p>
      <a
        href={`https://www.openstreetmap.org/?mlat=${lat}&mlon=${lng}#map=15/${lat}/${lng}`}
        target="_blank"
        rel="noopener noreferrer"
        className="no-print mt-3 inline-block font-cw-sans text-[14px] underline underline-offset-4"
      >
        Open location in OpenStreetMap
      </a>
    </div>
  );
}
