import { RuntimeStatusResponse } from "../api/client";

import { KeyValue } from "./shared";

import {

  CategoryRuntimeSlot,

  categoryStatusClass,

  formatVoiceStatusLabel,

  resolveCategoryRuntimeSlots,

} from "../utils/categoryRuntimeShell";



type Props = {

  status: RuntimeStatusResponse | null;

  legacyPanel?: Record<string, unknown>;

  compact?: boolean;

};



function artifactCount(slot: CategoryRuntimeSlot): number {

  return Array.isArray(slot.artifacts) ? slot.artifacts.length : 0;

}



function errorCode(slot: CategoryRuntimeSlot): string {

  const error = slot.error as Record<string, unknown> | null | undefined;

  return error?.code ? String(error.code) : "";

}



export function CategoryRuntimeSlotsPanel({ status, legacyPanel, compact = false }: Props) {

  const slots = resolveCategoryRuntimeSlots(status, legacyPanel);



  return (

    <section className={`category-runtime-shell ${compact ? "category-runtime-shell-compact" : ""}`}>

      <h4>Media categories</h4>

      <p className="muted category-runtime-shell-note">

        Read-only runtime shell — video dispatches clips; voice, subtitle, and assembly categories show preflight and execution metadata.

      </p>

      <div className="category-runtime-slot-list">

        {slots.map((slot) => {

          const isVoice = slot.category_key === "voice_generation";

          const code = errorCode(slot);

          return (

            <article

              key={slot.category_key}

              className={`category-runtime-slot-card ${isVoice ? "category-runtime-slot-card-voice" : ""}`}

            >

              <div className="category-runtime-slot-head">

                <strong>{slot.category_name}</strong>

                <span className={categoryStatusClass(slot.status, code)}>

                  {formatVoiceStatusLabel(slot.status, code)}

                </span>

              </div>

              <div className="kv-grid kv-grid-tight">

                <KeyValue label="Provider" value={slot.provider || "—"} />

                {isVoice ? (

                  <>

                    <KeyValue

                      label="Executed"

                      value={slot.executed === undefined ? "—" : String(slot.executed)}

                    />

                    <KeyValue

                      label="Dry run"

                      value={slot.dry_run === undefined ? "—" : String(slot.dry_run)}

                    />

                  </>

                ) : (

                  <KeyValue label="Artifacts" value={String(artifactCount(slot))} />

                )}

                {!compact && !isVoice && (

                  <>

                    <KeyValue label="Started" value={slot.started_at || "—"} />

                    <KeyValue label="Completed" value={slot.completed_at || "—"} />

                  </>

                )}

              </div>

            </article>

          );

        })}

      </div>

    </section>

  );

}

