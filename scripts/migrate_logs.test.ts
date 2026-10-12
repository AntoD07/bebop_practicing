import { describe, expect, it } from "vitest";
import { parseCsv, pyLiteralList } from "./migrate_logs";

describe("migrate_logs parsers", () => {
  it("parses python list reprs, nested one level", () => {
    expect(pyLiteralList("['Coltrane Pattern from 5th', 'Ideal Maj 7 Arpeggio']")).toEqual(["Coltrane Pattern from 5th", "Ideal Maj 7 Arpeggio"]);
    expect(pyLiteralList(`["['5', '6', '7', '9', '1']", "['1', '2']"]`)).toEqual(["['5', '6', '7', '9', '1']", "['1', '2']"]);
    expect(pyLiteralList("['3','5','#7','3','5']")).toEqual(["3", "5", "#7", "3", "5"]);
  });
  it("parses the legacy CSV with quoted fields", () => {
    const rows = parseCsv('Date,Line,Grade\n2024-07-04,"[\'a\', \'b\']",4\n2024-07-05,"[""[\'5\']""]",3\n');
    expect(rows).toHaveLength(2);
    expect(rows[0].Line).toBe("['a', 'b']");
    expect(rows[1].Line).toBe(`["['5']"]`);
    expect(rows[1].Grade).toBe("3");
  });
});
