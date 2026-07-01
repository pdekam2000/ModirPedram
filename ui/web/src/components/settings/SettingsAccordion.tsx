import { type ReactNode } from "react";

type SettingsAccordionProps = {
  id: string;
  title: string;
  subtitle?: string;
  badge?: string;
  open: boolean;
  onToggle: () => void;
  children: ReactNode;
};

export function SettingsAccordion({ id, title, subtitle, badge, open, onToggle, children }: SettingsAccordionProps) {
  return (
    <section className={`settings-accordion ${open ? "is-open" : ""}`} data-settings-section={id}>
      <button type="button" className="settings-accordion-header" onClick={onToggle} aria-expanded={open}>
        <span className="settings-accordion-title-wrap">
          <span className="settings-accordion-title">{title}</span>
          {subtitle ? <span className="settings-accordion-subtitle muted">{subtitle}</span> : null}
        </span>
        {badge ? <span className="settings-badge">{badge}</span> : null}
        <span className="settings-accordion-chevron">{open ? "−" : "+"}</span>
      </button>
      {open ? <div className="settings-accordion-body">{children}</div> : null}
    </section>
  );
}

export function useAccordionSections(initial: string[] = ["channel"]) {
  const maxOpen = 2;

  function toggleSection(current: string[], id: string): string[] {
    if (current.includes(id)) {
      return current.filter((item) => item !== id);
    }
    const next = [...current, id];
    if (next.length <= maxOpen) {
      return next;
    }
    return [...next.slice(-maxOpen)];
  }

  return { initial, toggleSection, maxOpen };
}
