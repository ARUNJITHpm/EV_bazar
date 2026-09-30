import { useEffect, useState } from "react";
import { developmentFixtures } from "../data/client";
import { DistrictMap } from "./DistrictMap";
export default function MapDemo() {
  const [fixtures, setFixtures] = useState<Awaited<ReturnType<typeof developmentFixtures>>>(null);
  useEffect(() => {
    void developmentFixtures("?fixtures=1").then(setFixtures);
  }, []);
  return (
    <>
      <h1>District map development demo</h1>
      <aside className="analytics-preparation">
        <h2>Test data</h2>
        <p>Invented fixture boundaries and values; these are not a map of real districts.</p>
      </aside>
      {fixtures && <DistrictMap atlas={fixtures.atlas} districts={fixtures.catalogue.districts} />}
    </>
  );
}
