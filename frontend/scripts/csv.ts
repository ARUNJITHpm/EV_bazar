export interface CsvRecord {
  row: number;
  values: string[];
}

/** RFC 4180 quotes, escaped quotes, BOM, CRLF and embedded newlines. */
export function parseCsv(source: string, file: string): CsvRecord[] {
  const input = source.replace(/^\uFEFF/, "");
  const records: CsvRecord[] = [];
  let values: string[] = [],
    cell = "",
    quoted = false,
    closed = false,
    line = 1,
    row = 1;
  const fail = (message: string): never => {
    throw new Error(`${file}: row ${line}, column ${values.length + 1}: ${message}`);
  };
  const endCell = () => {
    values.push(cell);
    cell = "";
    closed = false;
  };
  const endRow = () => {
    endCell();
    records.push({ row, values });
    values = [];
    row = line + 1;
  };
  for (let index = 0; index < input.length; index++) {
    const char = input[index]!;
    if (quoted) {
      if (char === '"') {
        if (input[index + 1] === '"') {
          cell += '"';
          index++;
        } else {
          quoted = false;
          closed = true;
        }
      } else {
        cell += char;
        if (char === "\n") line++;
      }
    } else if (char === '"') {
      if (cell || closed) fail("unexpected quote");
      quoted = true;
    } else if (char === ",") endCell();
    else if (char === "\n" || char === "\r") {
      if (char === "\r" && input[index + 1] === "\n") index++;
      endRow();
      line++;
    } else {
      if (closed) fail("unexpected text after closing quote");
      cell += char;
    }
  }
  if (quoted) fail("unterminated quoted field");
  if (cell || values.length || closed) {
    endCell();
    records.push({ row, values });
  }
  return records;
}
