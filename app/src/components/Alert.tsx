import type { ReactNode } from "react";

export function Alert({ title, children, tone = "info" }: { title: string; children: ReactNode; tone?: "info" | "error" }) {
  return (
    <div className={tone === "error" ? "alert error" : "alert"} role={tone === "error" ? "alert" : "status"}>
      <strong>{title}. </strong>
      <span>{children}</span>
    </div>
  );
}
