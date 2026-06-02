import { SessionActionEligibility, SessionActionType } from "../api/client";
import { ACTION_META, SESSION_ACTIONS } from "../utils/sessionActions";

type Props = {
  eligibility: SessionActionEligibility | null;
  loading?: boolean;
  acting?: boolean;
  onActionClick: (action: SessionActionType) => void;
};

function buttonClass(action: SessionActionType): string {
  const variant = ACTION_META[action].variant;
  if (variant === "danger") {
    return "action-btn action-btn-danger";
  }
  if (variant === "neutral") {
    return "action-btn action-btn-neutral";
  }
  return "action-btn";
}

export function SessionActionBar({ eligibility, loading, acting, onActionClick }: Props) {
  return (
    <div className="session-action-bar">
      {SESSION_ACTIONS.map((action) => {
        const gate = eligibility?.actions?.[action];
        const allowed = gate?.allowed === true;
        const blockedReason = gate?.reason || "Loading eligibility…";
        const meta = ACTION_META[action];
        return (
          <span key={action} className="action-btn-wrap" title={!allowed ? blockedReason : meta.safetyNote}>
            <button
              type="button"
              className={buttonClass(action)}
              disabled={loading || acting || !allowed}
              onClick={() => onActionClick(action)}
            >
              {meta.label}
            </button>
            {!allowed && !loading && <span className="action-block-hint">{blockedReason}</span>}
          </span>
        );
      })}
    </div>
  );
}
