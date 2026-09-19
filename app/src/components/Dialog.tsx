import { useEffect, useRef, useState, type ReactNode } from "react";
import { Button } from "./Button";

// Focus-trapped modal: Esc closes, focus returns to trigger, Tab cycles inside.
export function Dialog({ title, triggerLabel, children }: { title: string; triggerLabel: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const panel = panelRef.current;
    const prevFocus = document.activeElement as HTMLElement | null;
    // Initial focus inside dialog.
    const first = panel?.querySelector<HTMLElement>("button, [href], input, select, [tabindex]");
    (first ?? panel)?.focus?.();

    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
        return;
      }
      if (e.key !== "Tab" || !panel) return;
      const items = Array.from(
        panel.querySelectorAll<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])"),
      ).filter((el) => !el.hasAttribute("disabled"));
      if (items.length === 0) return;
      const firstEl = items[0];
      const lastEl = items[items.length - 1];
      if (e.shiftKey && document.activeElement === firstEl) {
        e.preventDefault();
        lastEl.focus();
      } else if (!e.shiftKey && document.activeElement === lastEl) {
        e.preventDefault();
        firstEl.focus();
      }
    }
    document.addEventListener("keydown", onKey, true);
    return () => {
      document.removeEventListener("keydown", onKey, true);
      // Return focus to trigger (or wherever focus was).
      (triggerRef.current ?? prevFocus)?.focus?.();
    };
  }, [open ]);

  return (
    <div>
      <Button ref={triggerRef} variant="secondary" onClick={() => setOpen(true)}>
        {triggerLabel}
      </Button>
      {open && (
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-label={title}
          className="card"
          tabIndex={-1}
        >
          <h3>{title}</h3>
          {children}
          <Button variant="secondary" onClick={() => setOpen(false)}>
            Close
          </Button>
        </div>
      )}
    </div>
  );
}
