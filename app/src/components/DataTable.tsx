export function DataTable({ columns, rows, caption }: { columns: string[]; rows: string[][]; caption?: string }) {
  return (
    <div style={{ overflowX: "auto" }}>
      <table className="responsive">
        {caption && <caption className="hint">{caption}</caption>}
        <thead>
          <tr>{columns.map((c) => (<th key={c} scope="col">{c}</th>))}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>{r.map((cell, j) => (<td key={j}>{cell}</td>))}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
