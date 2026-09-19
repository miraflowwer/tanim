// Non-color status: icon glyph + text (§§22-23).
export function Status({ label, tone = "info" }: { label: string; tone?: "ok" | "warn" | "bad" | "info" }) {
  const glyph = tone === "ok" ? "●" : tone === "warn" ? "▲" : tone === "bad" ? "■" : "○";
  return (
    <p className="status" role="status">
      <span aria-hidden="true">{glyph}</span> {label}
    </p>
  );
}
