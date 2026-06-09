import { useEffect, useMemo, useState } from "react";
import {
  ContentBrainPreflightResponse,
  ContentBrainTestResult,
  ContentBrainTestStep,
  fetchContentBrainTestStudioPreflight,
  findStep,
  postContentBrainOpenExportFolder,
  postContentBrainTestStudioRun,
} from "../api/contentBrainTestStudioClient";

type FormState = {
  topic: string;
  duration_seconds: number;
  platform: string;
  niche: string;
  mood: string;
  clip_length_preference: string;
};

const DEFAULT_FORM: FormState = {
  topic: "zander fishing method",
  duration_seconds: 30,
  platform: "youtube_shorts",
  niche: "general",
  mood: "emotional",
  clip_length_preference: "",
};

function PreflightPanel({
  preflight,
  loading,
  error,
}: {
  preflight: ContentBrainPreflightResponse | null;
  loading: boolean;
  error: string | null;
}) {
  if (loading) {
    return (
      <section className="card cb-test-preflight">
        <p className="muted">Checking API readiness…</p>
      </section>
    );
  }
  if (error) {
    return (
      <section className="card cb-test-preflight">
        <div className="error-banner">{error}</div>
      </section>
    );
  }
  if (!preflight) {
    return null;
  }

  const checks = Object.entries(preflight.checks || {});
  return (
    <section className="card cb-test-preflight">
      <div className="card-header">
        <h2>API Preflight</h2>
        <span className={`pill ${preflight.trend_mode === "live" ? "pill-live" : ""}`}>
          Trend: {preflight.trend_mode}
        </span>
      </div>
      <p className="muted">Recommended mode: {preflight.recommended_mode}</p>
      <div className="cb-test-preflight-grid">
        {checks.map(([key, check]) => (
          <div key={key} className={`cb-test-preflight-item ${check.ready ? "ready" : "missing"}`}>
            <div className="cb-test-preflight-head">
              <strong>{check.label || key}</strong>
              <span className={check.ready ? "success-text" : "error-text"}>
                {check.ready ? "Ready" : "Not ready"}
              </span>
            </div>
            {check.notes && <p className="muted">{check.notes}</p>}
          </div>
        ))}
      </div>
    </section>
  );
}

function ContentPreviewCard({ result }: { result: ContentBrainTestResult }) {
  const seoTitleStep = findStep(result, "seo_title");
  const seoStep = findStep(result, "seo_generation");
  const storyStep = findStep(result, "story_generation");
  const clipStep = findStep(result, "clip_planner");
  const trendStep = findStep(result, "trend_discovery");
  const durationStep = findStep(result, "duration_planner");
  const strategyStep = findStep(result, "topic_classification");

  const seoPayload = (seoTitleStep?.payload || seoStep?.payload || {}) as Record<string, unknown>;
  const seoTitle = String(seoPayload.seo_title || storyStep?.payload?.seo_title || "—");
  const seoDataSource = String(seoPayload.seo_data_source || "—");
  const dataforseoUsed = Boolean(seoPayload.dataforseo_used);
  const serpapiUsed = Boolean(seoPayload.serpapi_used);
  const seoKeywordsUsed = (seoPayload.seo_keywords_used || []) as string[];
  const relatedQueriesUsed = (seoPayload.related_queries_used || []) as string[];
  const story = (storyStep?.payload?.story || {}) as Record<string, unknown>;
  const clips = ((clipStep?.payload?.clips || []) as Array<Record<string, unknown>>) || [];
  const languageCode = String(result.input?.language_code || story.language_code || "—");
  const trendMode = String(trendStep?.payload?.trend_mode || "—");
  const sourcesUsed = (trendStep?.payload?.sources_used || []) as string[];
  const openAiApplied = Boolean(
    (storyStep?.payload?.openai_enrichment as Record<string, unknown> | undefined)?.applied,
  );
  const clipCount = Number(durationStep?.payload?.clip_count || clips.length || 0);
  const clipDuration = Number(durationStep?.payload?.clip_duration_seconds || 10);
  const classification = (strategyStep?.payload?.classification || {}) as Record<string, unknown>;
  const contentStrategy = (strategyStep?.payload?.content_strategy || {}) as Record<string, unknown>;
  const domainKnowledge = (strategyStep?.payload?.domain_knowledge || {}) as Record<string, unknown>;
  const characterBuilder = (strategyStep?.payload?.character_builder || story.character_builder || {}) as Record<
    string,
    unknown
  >;
  const storyStrategy = (strategyStep?.payload?.story_strategy || {}) as Record<string, unknown>;
  const seoCandidates = (seoTitleStep?.payload?.candidates_ranked || seoStep?.payload?.title_candidates || []) as Array<
    Record<string, unknown>
  >;
  const warnings = (result.quality_audit?.warnings || []) as string[];

  return (
    <section className="card cb-test-preview">
      <div className="card-header">
        <h2>Content Preview</h2>
        <span className="pill">Score {result.overall_content_score}</span>
      </div>

      <div className="cb-test-meta-row">
        <span className="cb-test-meta-chip">Language: {languageCode}</span>
        <span className="cb-test-meta-chip">Category: {String(classification.topic_category || "—")}</span>
        <span className="cb-test-meta-chip">Strategy: {String(contentStrategy.strategy_id || story.content_strategy || "—")}</span>
        <span className="cb-test-meta-chip">Trend mode: {trendMode}</span>
        <span className="cb-test-meta-chip">
          Clips: {clipCount} × {clipDuration}s
        </span>
        {openAiApplied && <span className="cb-test-meta-chip pill-live">OpenAI story</span>}
      </div>

      {warnings.length > 0 && (
        <div className="error-banner">
          {warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      )}

      <div className="cb-test-story-grid">
        <div>
          <span className="muted">Character</span>
          <p>{String(story.main_character || characterBuilder.character || "—")}</p>
        </div>
        <div>
          <span className="muted">Domain role source</span>
          <p>{String(characterBuilder.source || "—")}</p>
        </div>
        <div>
          <span className="muted">Story strategy</span>
          <p>{String(storyStrategy.label || "—")}</p>
        </div>
        <div>
          <span className="muted">Domain concepts</span>
          <p>{((domainKnowledge.concepts || []) as string[]).slice(0, 6).join(", ") || "—"}</p>
        </div>
      </div>

      {sourcesUsed.length > 0 && (
        <p className="muted cb-test-sources">API sources: {sourcesUsed.join(", ")}</p>
      )}

      <div className="cb-test-preview-block">
        <span className="cb-test-preview-label">SEO Title</span>
        <div className="cb-test-meta-row">
          <span className="cb-test-meta-chip">Source: {seoDataSource}</span>
          <span className={`cb-test-meta-chip ${dataforseoUsed ? "pill-live" : ""}`}>
            DataForSEO: {dataforseoUsed ? "true" : "false"}
          </span>
          <span className={`cb-test-meta-chip ${serpapiUsed ? "pill-live" : ""}`}>
            SerpAPI: {serpapiUsed ? "true" : "false"}
          </span>
        </div>
        <h3 className="cb-test-seo-title">{seoTitle}</h3>
        {(seoKeywordsUsed.length > 0 || relatedQueriesUsed.length > 0) && (
          <p className="muted">
            Keywords: {seoKeywordsUsed.slice(0, 4).join(", ") || "—"}
            {relatedQueriesUsed.length > 0 && (
              <> · Related: {relatedQueriesUsed.slice(0, 3).join(", ")}</>
            )}
          </p>
        )}
        {seoCandidates.length > 0 && (
          <ul className="cb-test-clip-list">
            {seoCandidates.slice(0, 4).map((candidate) => (
              <li key={String(candidate.title)}>
                <strong>{String(candidate.title)}</strong>
                <span>{String(candidate.reason || "")}</span>
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="cb-test-preview-block">
        <span className="cb-test-preview-label">Story</span>
        <p className="cb-test-story-logline">{String(story.logline || "—")}</p>
        <div className="cb-test-story-grid">
          <div>
            <span className="muted">Character</span>
            <p>{String(story.main_character || "—")}</p>
          </div>
          <div>
            <span className="muted">Setting</span>
            <p>{String(story.setting || "—")}</p>
          </div>
          <div>
            <span className="muted">Conflict</span>
            <p>{String(story.conflict_tension || "—")}</p>
          </div>
          <div>
            <span className="muted">Ending</span>
            <p>{String(story.ending_beat || "—")}</p>
          </div>
        </div>
      </div>

      <div className="cb-test-preview-block">
        <span className="cb-test-preview-label">Clip Beats</span>
        <ol className="cb-test-clip-list">
          {(clips.length > 0
            ? clips.map((clip, index) => ({
                index: Number(clip.clip_index || index + 1),
                purpose: String(clip.purpose || "beat"),
                scene: String(clip.story_beat || clip.scene || "—"),
              }))
            : ((story.clip_beats || []) as string[]).map((beat, index) => ({
                index: index + 1,
                purpose: index === 0 ? "hook" : index === clipCount - 1 ? "payoff" : "escalation",
                scene: beat,
              }))
          ).map((clip) => (
            <li key={clip.index}>
              <strong>
                Clip {clip.index} · {clip.purpose}
              </strong>
              <span>{clip.scene}</span>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

function RunwayPromptsCard({ result }: { result: ContentBrainTestResult }) {
  const promptStep = findStep(result, "prompt_cleanup") || findStep(result, "prompt_generation");
  if (!promptStep) {
    return null;
  }
  const maxChars = Number(promptStep.payload.runway_prompt_max_chars || 5000);
  const starter = String(promptStep.payload.starter_image_prompt || "");
  const starterChars = Number(promptStep.payload.starter_image_prompt_chars || starter.length);
  const clips = (promptStep.payload.clip_prompts || []) as Array<Record<string, unknown>>;

  return (
    <section className="card cb-test-preview">
      <div className="card-header">
        <h2>Runway Prompts (Image / Video)</h2>
        <span className="pill">Max {maxChars} chars</span>
      </div>
      <p className="muted">
        Copy these prompts into Runway. Full text also saved to{" "}
        <code>latest.runway_prompts.txt</code>
      </p>

      <div className="cb-test-preview-block">
        <span className="cb-test-preview-label">
          Starter Image Prompt · {starterChars}/{maxChars} chars
        </span>
        <pre className="cb-test-prompt-text">{starter || "—"}</pre>
      </div>

      {clips.map((clip) => (
        <div key={String(clip.clip_index)} className="cb-test-preview-block">
          <span className="cb-test-preview-label">
            Clip {String(clip.clip_index)} Video Prompt · {String(clip.video_prompt_chars || 0)}/{maxChars} chars
          </span>
          <pre className="cb-test-prompt-text">{String(clip.video_prompt || "—")}</pre>
        </div>
      ))}
    </section>
  );
}

function StepPanel({ step }: { step: ContentBrainTestStep }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="card cb-test-step">
      <button type="button" className="cb-test-step-head" onClick={() => setOpen((value) => !value)}>
        <span>
          Step {step.step} — {step.title}
        </span>
        <span className="muted">{step.duration_ms} ms</span>
      </button>
      {open && (
        <div className="cb-test-step-body">
          {step.api_sources?.length > 0 && (
            <p className="muted">API sources: {step.api_sources.join(", ")}</p>
          )}
          {step.error && <div className="error-banner">{step.error}</div>}
          <pre className="cb-test-json">{JSON.stringify(step.payload, null, 2)}</pre>
        </div>
      )}
    </section>
  );
}

function OpenAIEnhancementPanel({ result }: { result: ContentBrainTestResult }) {
  const audit = (result.quality_audit || {}) as Record<string, unknown>;
  const enhancement = (audit.quality_enhancement || {}) as Record<string, unknown>;
  const before = (audit.scores_before_enhancement || enhancement.before_scores || {}) as Record<string, number>;
  const after = (audit.scores_after_enhancement || enhancement.after_scores || {}) as Record<string, number>;
  const improvement = (audit.improvement_summary || enhancement.improvement_summary || {}) as Record<
    string,
    { before?: number; after?: number; percent?: number }
  >;
  const applied = (enhancement.enhancements_applied || []) as string[];
  const enabled = Boolean(enhancement.enabled);
  const wasApplied = Boolean(enhancement.applied);
  const cacheHit = Boolean(enhancement.cache_hit);
  const cost = Number(enhancement.estimated_cost_usd || 0);

  const scoreLabels: Record<string, string> = {
    seo_title_quality_score: "SEO",
    domain_knowledge_score: "Knowledge",
    story_specificity_score: "Story",
    character_quality_score: "Character",
    prompt_specificity_score: "Prompt",
    narrative_detail_score: "Narrative detail",
    overall_content_score: "Overall",
  };

  return (
    <section className="card cb-test-preview">
      <div className="card-header">
        <h2>OpenAI Enhancement</h2>
        <span className={`pill ${wasApplied ? "pill-live" : ""}`}>
          {enabled ? (wasApplied ? "Applied" : "Enabled") : "Disabled"}
        </span>
      </div>
      <div className="cb-test-meta-row">
        <span className="cb-test-meta-chip">Cache hit: {cacheHit ? "true" : "false"}</span>
        <span className="cb-test-meta-chip">Cost: ${cost.toFixed(6)}</span>
      </div>
      {applied.length > 0 ? (
        <p className="muted">Enhancements applied: {applied.join(", ")}</p>
      ) : (
        <p className="muted">No enhancements applied — local output passed quality thresholds.</p>
      )}
      {Object.keys(improvement).length > 0 && (
        <div className="cb-test-score-grid">
          {Object.entries(improvement).map(([key, item]) => (
            <div key={key} className="cb-test-score-item">
              <span className="muted">{scoreLabels[key] || key}</span>
              <strong>
                {String(item.before ?? before[key] ?? "—")} → {String(item.after ?? after[key] ?? "—")}
                {typeof item.percent === "number" ? ` (+${item.percent}%)` : ""}
              </strong>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function CrossDomainFusionPanel({ result }: { result: ContentBrainTestResult }) {
  const fusionStep = findStep(result, "cross_domain_fusion");
  const fusion = (fusionStep?.payload || {}) as Record<string, unknown>;
  const audit = (result.quality_audit || {}) as Record<string, unknown>;
  if (!fusionStep) {
    return null;
  }
  const weights = (fusion.domain_weights || {}) as Record<string, number>;
  const conceptsByDomain = (fusion.domain_concepts_by_domain || {}) as Record<string, string[]>;
  const warnings = (fusion.missing_domain_warnings || audit.missing_domain_warnings || []) as string[];
  return (
    <section className="card cb-test-preview">
      <div className="card-header">
        <h2>Cross-Domain Fusion</h2>
        <span className={`pill ${fusion.multi_domain ? "pill-live" : ""}`}>
          {fusion.multi_domain ? "Multi-domain" : "Single-domain"}
        </span>
      </div>
      <div className="cb-test-meta-row">
        <span className="cb-test-meta-chip">Primary: {String(fusion.primary_domain || "—")}</span>
        <span className="cb-test-meta-chip">
          Secondary: {((fusion.secondary_domains || []) as string[]).join(", ") || "—"}
        </span>
        <span className="cb-test-meta-chip">Fusion score: {String(audit.cross_domain_fusion_score ?? "—")}</span>
        <span className="cb-test-meta-chip">Balance: {String(audit.domain_balance_score ?? fusion.domain_balance_score ?? "—")}</span>
        <span className="cb-test-meta-chip">OpenAI fusion: {String(fusion.openai_fusion_used ?? false)}</span>
        <span className="cb-test-meta-chip">Cache hit: {String(fusion.cache_hit ?? false)}</span>
        <span className="cb-test-meta-chip">Cost: ${Number(fusion.estimated_cost_usd || 0).toFixed(6)}</span>
      </div>
      <p className="muted">
        Story focus: {String(fusion.story_focus || "—")} · Angle: {String(fusion.strategic_angle || "—")}
      </p>
      {Object.keys(weights).length > 0 && (
        <div className="cb-test-score-grid">
          {Object.entries(weights).map(([domain, weight]) => (
            <div key={domain} className="cb-test-score-item">
              <span className="muted">{domain}</span>
              <strong>{Number(weight).toFixed(2)}</strong>
            </div>
          ))}
        </div>
      )}
      {Object.keys(conceptsByDomain).length > 0 && (
        <div className="cb-test-story-grid">
          {Object.entries(conceptsByDomain).map(([domain, concepts]) => (
            <div key={domain}>
              <h3>{domain}</h3>
              <p>{concepts.slice(0, 6).join("; ")}</p>
            </div>
          ))}
        </div>
      )}
      {warnings.length > 0 && (
        <div className="error-banner">
          {warnings.map((warning) => (
            <div key={warning}>{warning}</div>
          ))}
        </div>
      )}
    </section>
  );
}

function DynamicDomainExpertPanel({ result }: { result: ContentBrainTestResult }) {
  const strategyStep = findStep(result, "topic_classification");
  const expert = (strategyStep?.payload?.dynamic_domain_expert || {}) as Record<string, unknown>;
  const payload = (expert.payload || {}) as Record<string, unknown>;
  const profile = (payload.domain_profile || {}) as Record<string, unknown>;
  const classification = (expert.classification || {}) as Record<string, unknown>;
  const concepts = (profile.core_concepts || []) as string[];
  if (!strategyStep) {
    return null;
  }
  return (
    <section className="card cb-test-preview">
      <div className="card-header">
        <h2>Dynamic Domain Expert</h2>
        <span className={`pill ${expert.used ? "pill-live" : ""}`}>
          {expert.used ? "OpenAI pack applied" : "Not used"}
        </span>
      </div>
      <div className="cb-test-meta-row">
        <span className="cb-test-meta-chip">Used: {String(expert.used ?? false)}</span>
        <span className="cb-test-meta-chip">Model: {String(expert.model || "—")}</span>
        <span className="cb-test-meta-chip">Cache hit: {String(expert.cache_hit ?? false)}</span>
        <span className="cb-test-meta-chip">Category: {String(payload.category || classification.topic_category || "—")}</span>
        <span className="cb-test-meta-chip">Strategy: {String(payload.strategy || classification.content_strategy || "—")}</span>
        <span className="cb-test-meta-chip">Confidence: {String(payload.confidence ?? "—")}</span>
        <span className="cb-test-meta-chip">Cost: ${Number(expert.estimated_cost_usd || 0).toFixed(6)}</span>
      </div>
      <p className="muted">
        Trigger: {String(expert.trigger_reason || "—")} · Expert role: {String(profile.expert_role || "—")}
      </p>
      {concepts.length > 0 && (
        <p className="muted">Domain concepts: {concepts.slice(0, 8).join("; ")}</p>
      )}
      {String(profile.setting || "").trim() && (
        <p className="muted">Setting: {String(profile.setting)}</p>
      )}
    </section>
  );
}

function ConceptDistributionPanel({ result }: { result: ContentBrainTestResult }) {
  const step = findStep(result, "concept_distribution");
  if (!step) {
    return null;
  }
  const payload = (step.payload || {}) as Record<string, unknown>;
  const distribution = (payload.concept_distribution || {}) as Record<string, unknown>;
  const assignments = (distribution.clip_assignments || payload.clip_assigned_concepts || {}) as Record<
    string,
    { primary?: string[]; secondary?: string[]; role?: string }
  >;
  const audit = (result.quality_audit || {}) as Record<string, unknown>;
  return (
    <section className="card cb-test-preview">
      <div className="card-header">
        <h2>Concept Distribution</h2>
        <span className="pill">Diversity {String(audit.prompt_diversity_score ?? "—")}</span>
      </div>
      <div className="cb-test-meta-row">
        <span className="cb-test-meta-chip">Source: {String(distribution.source || "—")}</span>
        <span className="cb-test-meta-chip">OpenAI: {String(distribution.openai_distribution_used ?? false)}</span>
        <span className="cb-test-meta-chip">Cache hit: {String(distribution.cache_hit ?? false)}</span>
      </div>
      <div className="cb-test-story-grid">
        {Object.entries(assignments).map(([clipIndex, bucket]) => (
          <div key={clipIndex}>
            <h3>
              Clip {clipIndex}
              {bucket.role ? ` (${bucket.role})` : ""}
            </h3>
            <p>
              <strong>Primary:</strong> {(bucket.primary || []).join("; ") || "—"}
            </p>
            <p className="muted">
              <strong>Secondary:</strong> {(bucket.secondary || []).join("; ") || "—"}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function PromptCleanupPanel({ result }: { result: ContentBrainTestResult }) {
  const step = findStep(result, "prompt_cleanup");
  if (!step) {
    return null;
  }
  const payload = (step.payload || {}) as Record<string, unknown>;
  const audit = (result.quality_audit || {}) as Record<string, unknown>;
  const originalLength = Number(payload.original_total_chars ?? payload.original_length ?? 0);
  const cleanedLength = Number(payload.cleaned_total_chars ?? payload.cleaned_length ?? 0);
  const charactersSaved = Number(payload.characters_saved ?? Math.max(0, originalLength - cleanedLength));
  return (
    <section className="card cb-test-preview">
      <div className="card-header">
        <h2>Prompt Cleanup</h2>
        <span className="pill">Noise {String(audit.prompt_noise_score ?? payload.prompt_noise_score ?? "—")}</span>
      </div>
      <div className="cb-test-score-grid">
        <div className="cb-test-score-item">
          <span className="muted">Original length</span>
          <strong>{originalLength}</strong>
        </div>
        <div className="cb-test-score-item">
          <span className="muted">Cleaned length</span>
          <strong>{cleanedLength}</strong>
        </div>
        <div className="cb-test-score-item">
          <span className="muted">Characters saved</span>
          <strong>{charactersSaved}</strong>
        </div>
        <div className="cb-test-score-item">
          <span className="muted">Efficiency</span>
          <strong>{String(audit.prompt_efficiency_score ?? payload.prompt_efficiency_score ?? "—")}</strong>
        </div>
      </div>
      <div className="cb-test-meta-row">
        <span className="cb-test-meta-chip">Cleanup applied: {String(payload.cleanup_applied ?? false)}</span>
        <span className="cb-test-meta-chip">OpenAI cleanup: {String(payload.openai_cleanup_used ?? false)}</span>
        <span className="cb-test-meta-chip">Reduction: {String(payload.reduction_percent ?? "0")}%</span>
        <span className="cb-test-meta-chip">Source: {String(payload.source || "local_rules")}</span>
      </div>
      {Boolean(payload.prompt_cleanup_gate_failures && (payload.prompt_cleanup_gate_failures as string[]).length > 0) && (
        <div className="error-banner">
          {(payload.prompt_cleanup_gate_failures as string[]).map((failure) => (
            <div key={failure}>{failure}</div>
          ))}
        </div>
      )}
    </section>
  );
}

function TopicLabelPanel({ result }: { result: ContentBrainTestResult }) {
  const step = findStep(result, "concept_distribution");
  const storyStep = findStep(result, "story_generation");
  const audit = (result.quality_audit || {}) as Record<string, unknown>;
  const labelPayload = (step?.payload?.topic_label || {}) as Record<string, unknown>;
  const story = (storyStep?.payload?.story || {}) as Record<string, unknown>;
  const label = String(labelPayload.label || story.topic_label || (story.topic_story_detail as Record<string, unknown>)?.subject || "—");
  if (!step && !label) {
    return null;
  }
  return (
    <section className="card cb-test-preview">
      <div className="card-header">
        <h2>Topic Label</h2>
        <span className="pill">Quality {String(audit.topic_label_quality_score ?? labelPayload.quality_score ?? "—")}</span>
      </div>
      <p>
        <strong>{label}</strong>
      </p>
      <p className="muted">Source: {String(labelPayload.source || "local_rules")}</p>
    </section>
  );
}

function PipelineSummary({ result }: { result: ContentBrainTestResult }) {
  const audit = result.quality_audit || {};
  return (
    <section className="card">
      <div className="card-header">
        <h2>Quality Audit</h2>
        <span className="pill">Overall {result.overall_content_score}</span>
      </div>
      <div className="cb-test-score-grid">
        {(
          [
            ["Topic preservation", audit.topic_preservation_score],
            ["Language authority", audit.language_authority_score],
            ["Domain knowledge", audit.domain_knowledge_score],
            ["Character quality", audit.character_quality_score],
            ["Story specificity", audit.story_specificity_score],
            ["Strategy alignment", audit.strategy_alignment_score],
            ["SEO title quality", audit.seo_title_quality_score],
            ["Clip specificity", audit.clip_specificity_score],
            ["Prompt specificity", audit.prompt_specificity_score],
            ["Narrative detail", audit.narrative_detail_score],
            ["Cross-domain fusion", audit.cross_domain_fusion_score],
            ["Domain balance", audit.domain_balance_score],
            ["Prompt diversity", audit.prompt_diversity_score],
            ["Prompt noise", audit.prompt_noise_score],
            ["Prompt efficiency", audit.prompt_efficiency_score],
            ["Topic label quality", audit.topic_label_quality_score],
            ["Continuity", audit.continuity_score],
          ] as Array<[string, unknown]>
        ).map(([label, value]) => (
          <div key={label} className="cb-test-score-item">
            <span className="muted">{label}</span>
            <strong>{String(value ?? "—")}</strong>
          </div>
        ))}
      </div>
    </section>
  );
}

export function ContentBrainTestStudioPage() {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ContentBrainTestResult | null>(null);
  const [preflight, setPreflight] = useState<ContentBrainPreflightResponse | null>(null);
  const [preflightLoading, setPreflightLoading] = useState(true);
  const [preflightError, setPreflightError] = useState<string | null>(null);
  const [openExportMessage, setOpenExportMessage] = useState<string | null>(null);

  const sortedSteps = useMemo(
    () => [...(result?.steps || [])].sort((a, b) => a.step - b.step),
    [result],
  );

  useEffect(() => {
    let cancelled = false;
    async function loadPreflight() {
      setPreflightLoading(true);
      setPreflightError(null);
      try {
        const payload = await fetchContentBrainTestStudioPreflight();
        if (!cancelled) {
          setPreflight(payload);
        }
      } catch (err) {
        if (!cancelled) {
          setPreflightError(err instanceof Error ? err.message : "Preflight failed");
        }
      } finally {
        if (!cancelled) {
          setPreflightLoading(false);
        }
      }
    }
    void loadPreflight();
    return () => {
      cancelled = true;
    };
  }, []);

  async function runTest() {
    setRunning(true);
    setError(null);
    setOpenExportMessage(null);
    try {
      const response = await postContentBrainTestStudioRun({
        topic: form.topic.trim(),
        duration_seconds: Number(form.duration_seconds),
        platform: form.platform,
        niche: form.niche.trim() || "general",
        mood: form.mood.trim() || "emotional",
        clip_length_preference: form.clip_length_preference
          ? Number(form.clip_length_preference)
          : null,
      });
      setResult(response.result);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Run failed");
      setResult(null);
    } finally {
      setRunning(false);
    }
  }

  async function openExportFolder() {
    setOpenExportMessage(null);
    try {
      const exportPath = result?.export_paths?.json
        ? result.export_paths.json.replace(/[/\\][^/\\]+$/, "")
        : undefined;
      const response = await postContentBrainOpenExportFolder(exportPath || null);
      setOpenExportMessage(response.message || "Export folder opened.");
    } catch (err) {
      setOpenExportMessage(err instanceof Error ? err.message : "Could not open export folder.");
    }
  }

  return (
    <div className="cb-test-studio">
      <PreflightPanel preflight={preflight} loading={preflightLoading} error={preflightError} />

      <section className="card">
        <div className="card-header">
          <h2>Content Brain Test Studio</h2>
          <span className="muted">No Runway · No media · Live APIs when configured</span>
        </div>
        <p className="muted">
          Topic → Trends → SEO Title → Story → Duration → Clips → Prompts → SEO package
        </p>
        <div className="cb-test-form-grid">
          <label>
            Topic
            <textarea
              rows={3}
              value={form.topic}
              onChange={(event) => setForm({ ...form, topic: event.target.value })}
            />
          </label>
          <label>
            Duration (seconds)
            <input
              type="number"
              min={5}
              max={600}
              value={form.duration_seconds}
              onChange={(event) =>
                setForm({ ...form, duration_seconds: Number(event.target.value) })
              }
            />
          </label>
          <label>
            Platform
            <select
              value={form.platform}
              onChange={(event) => setForm({ ...form, platform: event.target.value })}
            >
              <option value="youtube_shorts">youtube_shorts</option>
              <option value="tiktok">tiktok</option>
              <option value="instagram_reels">instagram_reels</option>
            </select>
          </label>
          <label>
            Niche
            <input value={form.niche} onChange={(event) => setForm({ ...form, niche: event.target.value })} />
          </label>
          <label>
            Mood
            <input value={form.mood} onChange={(event) => setForm({ ...form, mood: event.target.value })} />
          </label>
          <label>
            Clip length preference (optional)
            <input
              type="number"
              placeholder="10"
              value={form.clip_length_preference}
              onChange={(event) =>
                setForm({ ...form, clip_length_preference: event.target.value })
              }
            />
          </label>
        </div>
        <div className="cb-test-actions">
          <button type="button" disabled={running || !form.topic.trim()} onClick={() => void runTest()}>
            {running ? "Running pipeline…" : "Run Content Brain E2E Test"}
          </button>
          <button type="button" onClick={() => void openExportFolder()}>
            Open Export Folder
          </button>
        </div>
        {error && <div className="error-banner">{error}</div>}
        {openExportMessage && <p className="muted success-text">{openExportMessage}</p>}
      </section>

      {result && (
        <>
          <section className="card">
            <div className="card-header">
              <h2>Run Summary</h2>
              <span className="muted mono">{result.run_id}</span>
            </div>
            <p className="muted">
              {result.started_at} → {result.completed_at} · {result.total_duration_ms} ms total
            </p>
            {result.export_paths?.json && (
              <p className="muted export-path">Exported JSON: {result.export_paths.json}</p>
            )}
            {result.export_paths?.latest_runway_prompts && (
              <p className="muted export-path">Runway prompts: {result.export_paths.latest_runway_prompts}</p>
            )}
          </section>
          <ContentPreviewCard result={result} />
          <RunwayPromptsCard result={result} />
          <PipelineSummary result={result} />
          <CrossDomainFusionPanel result={result} />
          <DynamicDomainExpertPanel result={result} />
          <ConceptDistributionPanel result={result} />
          <PromptCleanupPanel result={result} />
          <TopicLabelPanel result={result} />
          <OpenAIEnhancementPanel result={result} />
          <section className="card">
            <div className="card-header">
              <h2>Technical Steps</h2>
              <span className="muted">JSON payloads</span>
            </div>
          </section>
          {sortedSteps.map((step) => (
            <StepPanel key={`${step.step_key}-${step.step}`} step={step} />
          ))}
        </>
      )}
    </div>
  );
}
