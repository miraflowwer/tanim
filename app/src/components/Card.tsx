import type { ReactNode } from "react";

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <article className="card" aria-label={title}>
      <h3>{title}</h3>
      {children}
    </article>
  );
}
