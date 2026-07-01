import { ExecutionCenterPage } from "./ExecutionCenterPage";

export function DeveloperConsolePage() {
  return (
    <div className="developer-console-wrap">
      <div className="dev-banner">Developer Mode — debug tools only. End users should stay in User Mode.</div>
      <ExecutionCenterPage />
    </div>
  );
}
