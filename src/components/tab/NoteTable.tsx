import type { PlacedJSON } from "@/lib/engine/types";
import { GLYPH, fingerStr } from "@/lib/tab/geometry";
import { Table, Td, Th } from "@/components/ui/table";

export function NoteTable({ placed }: { placed: PlacedJSON[] }) {
  return (
    <Table className="text-xs">
      <thead>
        <tr>
          <Th>#</Th>
          <Th>beat</Th>
          <Th>pitch</Th>
          <Th>deg</Th>
          <Th>cell</Th>
          <Th>str</Th>
          <Th>fret</Th>
          <Th>fin</Th>
          <Th>stk</Th>
          <Th>rest</Th>
        </tr>
      </thead>
      <tbody>
        {placed.map((p) => (
          <tr key={p.i}>
            <Td>{p.i}</Td>
            <Td className="tabular-nums">{p.beat}</Td>
            <Td>{p.name}</Td>
            <Td>{p.degree ?? p.role ?? ""}</Td>
            <Td className="max-w-[12rem] truncate text-fg-muted">{p.cell ?? ""}</Td>
            <Td>{p.string}</Td>
            <Td>{p.fret}</Td>
            <Td>{fingerStr(p)}</Td>
            <Td className={p.stroke === "U" ? "text-danger" : ""}>{GLYPH[p.stroke] ?? p.stroke}</Td>
            <Td>{p.rest ? "Y" : "N"}</Td>
          </tr>
        ))}
      </tbody>
    </Table>
  );
}
