import { useEffect, useRef, useState, type ReactNode } from "react";
import type { NavigationItem } from "../../app/routes/types";

// Role-aware shell (§§02/04): one role menu at a time, public shell without
// authenticated nav, Farmer bottom nav (<=5 persistent), drawer for the rest.
export function PublicShell({ children }: { children: ReactNode }) {
  return (
    <div className="app public">
      <a className="skip" href="#main">Skip to main content</a>
      <header className="topbar">
        <h1>TANIM</h1>
        <p>Timely Agricultural Network for Informed Market</p>
      </header>
      <main id="main" tabIndex={-1}>{children}</main>
    </div>
  );
}

export function PageHeader({ title, purpose, action }: { title: string; purpose?: string; action?: ReactNode }) {
  return (
    <div className="pagehead">
      <h2>{title}</h2>
      {purpose && <p className="hint">{purpose}</p>}
      {action && <div className="pagehead-action">{action}</div>}
    </div>
  );
}

export function Breadcrumbs({ trail }: { trail: { label: string; href?: string }[] }) {
  return (
    <nav aria-label="Breadcrumb" className="crumbs">
      <ol>
        {trail.map((item, i) => (
          <li key={item.label}>
            {i > 0 && <span aria-hidden="true"> / </span>}
            {item.href && i < trail.length - 1 ? <a href={item.href}>{item.label}</a> : <span aria-current="page">{item.label}</span>}
          </li>
        ))}
      </ol>
    </nav>
  );
}

export function Sidebar({ label, items, current }: { label: string; items: NavigationItem[]; current: string }) {
  return (
    <nav className="sidenav" aria-label={label}>
      <ul>
        {items.map((item) => (
          <li key={item.id}>
            <a href={item.href} aria-current={current === item.id ? "page" : undefined}>{item.label}</a>
          </li>
        ))}
      </ul>
    </nav>
  );
}

const MORE_IDS = new Set(["map", "farms", "notifications", "profile", "privacy"]);

export function FarmerBottomNav({ items, current }: { items: NavigationItem[]; current: string }) {
  const primary = items.filter((i) => i.mobilePrimary).slice(0, 4);
  const more = items.filter((i) => MORE_IDS.has(i.id));
  const [open, setOpen] = useState(false);
  const firstRef = useRef<HTMLAnchorElement>(null);

  useEffect(() => {
    if (!open) return;
    firstRef.current?.focus();
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open ]);

  const inMore = more.some((i) => i.id === current || (current.startsWith("plan") && i.id === "plans"));
  return (
    <>
      <nav className="bottomnav" aria-label="Farmer primary">
        {primary.map((item) => (
          <a key={item.id} href={item.href}
            aria-current={current === item.id || (item.id === "plans" && current.startsWith("plan")) ? "page" : undefined}>
            {item.label}
          </a>
        ))}
        <button type="button" aria-expanded={open} aria-controls="more-sheet" aria-current={inMore ? "page" : undefined}
          onClick={() => setOpen((v) => !v)}>
          More
        </button>
      </nav>
      {open && (
        <div id="more-sheet" className="sheet" role="dialog" aria-modal="true" aria-label="More destinations">
          <div className="sheet-panel">
            <p className="row space-between">
              <strong>More</strong>
              <button type="button" className="secondary" onClick={() => setOpen(false)}>Close</button>
            </p>
            <ul>
              {more.map((item, i) => (
                <li key={item.id}>
                  <a ref={i === 0 ? firstRef : undefined} href={item.href}
                    aria-current={current === item.id ? "page" : undefined}
                    onClick={() => setOpen(false)}>
                    {item.label}
                  </a>
                </li>
              ))}
              <li><a href="#/login" onClick={() => setOpen(false)}>Sign out</a></li>
            </ul>
          </div>
        </div>
      )}
    </>
  );
}

export function RoleDrawer({ label, role, org, items, current }: {
  label: string; role: string; org: string; items: NavigationItem[]; current: string;
}) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = "";
    };
  }, [open ]);
  return (
    <>
      <button type="button" className="secondary menu-btn" aria-expanded={open} onClick={() => setOpen(true)}>
        Menu
      </button>
      {open && (
        <div className="sheet" role="dialog" aria-modal="true" aria-label={label}>
          <div className="sheet-panel">
            <p className="hint">{org} · {role}</p>
            <p className="row space-between">
              <strong>{label}</strong>
              <button type="button" className="secondary" onClick={() => setOpen(false)}>Close</button>
            </p>
            <ul>
              {items.map((item) => (
                <li key={item.id}>
                  <a href={item.href} aria-current={current === item.id ? "page" : undefined}
                    onClick={() => setOpen(false)}>
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </>
  );
}

export function AppShell({ navLabel, nav, current, topbarExtra, children, bottomNav }: {
  navLabel: string;
  nav: NavigationItem[];
  current: string;
  topbarExtra?: ReactNode;
  children: ReactNode;
  bottomNav?: ReactNode;
}) {
  return (
    <div className="app">
      <a className="skip" href="#main">Skip to main content</a>
      <header className="topbar">
        <div>
          <h1>TANIM</h1>
          <p>Timely Agricultural Network for Informed Market</p>
        </div>
        {topbarExtra}
      </header>
      <div className="shell">
        <Sidebar label={navLabel} items={nav} current={current} />
        <main id="main" tabIndex={-1}>{children}</main>
      </div>
      {bottomNav}
      <footer>
        <p className="hint">Demo data is synthetic and labeled where shown. Farmer names stay hidden in group views.</p>
      </footer>
    </div>
  );
}
