declare module "virtual:analytics-public-data" {
  const catalogue: import("./schemas").PublicCatalogue;
  export default catalogue;
}
declare module "virtual:analytics-atlas" {
  const atlas: import("../districts/model").Atlas;
  export default atlas;
}
declare module "virtual:analytics-fixtures" {
  const fixtures: {
    catalogue: import("./schemas").PublicCatalogue;
    csvs: { name: string; source: string }[];
    atlas: import("../districts/model").Atlas;
  } | null;
  export default fixtures;
}
