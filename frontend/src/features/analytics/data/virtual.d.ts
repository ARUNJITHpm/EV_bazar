declare module "virtual:analytics-public-data" {
  const catalogue: import("./schemas").PublicCatalogue;
  export default catalogue;
}
declare module "virtual:analytics-fixtures" {
  const fixtures: {
    catalogue: import("./schemas").PublicCatalogue;
    csvs: { name: string; source: string }[];
  } | null;
  export default fixtures;
}
