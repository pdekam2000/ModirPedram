import { useMemo, useState } from "react";
import { saveCredential, testCredential, type CredentialStatus } from "../../api/platformClient";
import { SettingsModal } from "./SettingsModal";

type CredentialTableProps = {
  credentials: CredentialStatus[];
  onRefresh: () => Promise<void>;
  onError: (message: string) => void;
  onMessage: (providerId: string, message: string) => void;
};

type ModalMode = "add" | "edit";

export function CredentialTable({ credentials, onRefresh, onError, onMessage }: CredentialTableProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<ModalMode>("add");
  const [activeProvider, setActiveProvider] = useState<CredentialStatus | null>(null);
  const [secretInput, setSecretInput] = useState("");
  const [busy, setBusy] = useState(false);

  const sorted = useMemo(
    () => [...credentials].sort((left, right) => left.label.localeCompare(right.label)),
    [credentials],
  );

  function openModal(provider: CredentialStatus, mode: ModalMode) {
    setActiveProvider(provider);
    setModalMode(mode);
    setSecretInput("");
    setModalOpen(true);
  }

  function closeModal() {
    setModalOpen(false);
    setActiveProvider(null);
    setSecretInput("");
  }

  async function handleSave() {
    if (!activeProvider) {
      return;
    }
    if (!secretInput.trim()) {
      onError("Enter a key before saving.");
      return;
    }
    setBusy(true);
    try {
      await saveCredential(activeProvider.provider_id, secretInput.trim());
      await onRefresh();
      onMessage(activeProvider.provider_id, "Saved. Key is masked and not returned.");
      closeModal();
    } catch (err) {
      onError(err instanceof Error ? err.message : "Credential save failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(provider: CredentialStatus) {
    const confirmed = window.confirm(`Remove saved credential for ${provider.label}?`);
    if (!confirmed) {
      return;
    }
    setBusy(true);
    try {
      await saveCredential(provider.provider_id, "");
      await onRefresh();
      onMessage(provider.provider_id, "Credential removed.");
    } catch (err) {
      onError(err instanceof Error ? err.message : "Credential remove failed");
    } finally {
      setBusy(false);
    }
  }

  async function handleTest(provider: CredentialStatus) {
    setBusy(true);
    try {
      const result = await testCredential(provider.provider_id);
      onMessage(provider.provider_id, result.message);
    } catch (err) {
      onMessage(provider.provider_id, err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div className="settings-table-wrap">
        <table className="settings-cred-table">
          <thead>
            <tr>
              <th>Provider</th>
              <th>Status</th>
              <th>Masked Key</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((item) => (
              <tr key={item.provider_id}>
                <td>{item.label}</td>
                <td>
                  <span className={`settings-badge ${item.configured ? "success" : "muted"}`}>
                    {item.configured ? "Connected" : "Not set"}
                  </span>
                </td>
                <td className="mono">{item.configured ? item.masked_value || "configured" : "—"}</td>
                <td>
                  <div className="settings-inline-actions">
                    {item.configured ? (
                      <button type="button" className="link-button" disabled={busy} onClick={() => openModal(item, "edit")}>
                        Edit
                      </button>
                    ) : (
                      <button type="button" className="link-button" disabled={busy} onClick={() => openModal(item, "add")}>
                        Add
                      </button>
                    )}
                    {item.testable && item.configured ? (
                      <button type="button" className="link-button" disabled={busy} onClick={() => void handleTest(item)}>
                        Test
                      </button>
                    ) : null}
                    {item.configured ? (
                      <button type="button" className="link-button danger-text" disabled={busy} onClick={() => void handleRemove(item)}>
                        Remove
                      </button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted settings-helper">Full secrets are never displayed after save.</p>

      <SettingsModal
        title={modalMode === "add" ? `Add ${activeProvider?.label || "API"} Key` : `Replace ${activeProvider?.label || "API"} Key`}
        open={modalOpen}
        onClose={closeModal}
        footer={
          <div className="action-row">
            <button type="button" onClick={closeModal}>
              Cancel
            </button>
            <button type="button" className="primary-btn" disabled={busy} onClick={() => void handleSave()}>
              {busy ? "Saving…" : "Save"}
            </button>
          </div>
        }
      >
        <p className="muted">
          {modalMode === "edit"
            ? "Enter a new key to replace the saved credential. The existing key is not shown."
            : "Paste your API key. It will be encrypted locally."}
        </p>
        <label className="field-row full-width">
          API key
          <input
            className="filter-input full-width mono"
            type="password"
            autoComplete="off"
            value={secretInput}
            onChange={(e) => setSecretInput(e.target.value)}
            placeholder="Paste API key"
          />
        </label>
      </SettingsModal>
    </>
  );
}
