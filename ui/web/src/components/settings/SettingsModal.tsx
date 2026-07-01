import { type ReactNode } from "react";

type SettingsModalProps = {
  title: string;
  open: boolean;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
};

export function SettingsModal({ title, open, onClose, children, footer }: SettingsModalProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="settings-modal-overlay" role="presentation" onClick={onClose}>
      <div
        className="settings-modal"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        <header className="settings-modal-header">
          <h3>{title}</h3>
          <button type="button" className="link-button" onClick={onClose} aria-label="Close">
            Close
          </button>
        </header>
        <div className="settings-modal-body">{children}</div>
        {footer ? <footer className="settings-modal-footer">{footer}</footer> : null}
      </div>
    </div>
  );
}
