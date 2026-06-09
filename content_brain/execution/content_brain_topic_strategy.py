"""
Topic classification + content strategy selection for Content Brain.

Answers "what type of content is this?" before story/SEO generation.
Preserves topic intent — not just topic words.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.content_brain_topic_authority import extract_topic_domain
from content_brain.execution.content_brain_topic_locale import extract_topic_anchor_tokens
from content_brain.execution.domain_knowledge_layer import get_domain_profile
from content_brain.execution.story_strategy_library import resolve_story_strategy

STRATEGY_INSTRUCTIONAL_FISHING = "instructional_fishing"
STRATEGY_RECIPE_TUTORIAL = "recipe_tutorial"
STRATEGY_EDUCATIONAL_TECH = "educational_tech"
STRATEGY_DOCUMENTARY = "documentary"
STRATEGY_NARRATIVE_MYSTERY = "narrative_mystery"
STRATEGY_HORROR_STORY = "horror_storytelling"
STRATEGY_JOURNALISTIC = "journalistic"
STRATEGY_EDUCATIONAL_LIFESTYLE = "educational_lifestyle"
STRATEGY_INSTRUCTIONAL_GENERAL = "instructional_general"
STRATEGY_HISTORICAL_INVESTIGATION = "historical_investigation"
STRATEGY_BUSINESS_CASE_STUDY = "business_case_study"
STRATEGY_FUTURE_ANALYSIS = "future_analysis"
STRATEGY_BUSINESS_DEBATE = "business_debate"
STRATEGY_TECHNOLOGY_FORECAST = "technology_forecast"
STRATEGY_SCIENTIFIC_EXPLANATION = "scientific_explanation"
STRATEGY_CINEMATIC_NARRATIVE = "cinematic_narrative"

HISTORICAL_INVESTIGATION_PATTERNS: tuple[str, ...] = (
    r"what really happened",
    r"what happened to",
    r"what happened at",
    r"what happened in",
    r"disappearance of",
    r"vanished",
    r"lost colony",
)

HISTORICAL_INVESTIGATION_WEAK_PATTERNS: tuple[str, ...] = (
    r"why did",
    r"who was",
    r"mystery of",
)

HISTORY_CONTEXT_KEYWORDS: tuple[str, ...] = (
    "historical",
    "history",
    "ancient",
    "colony",
    "colonial",
    "empire",
    "archaeological",
    "archival",
    "excavation",
    "artifact",
    "settler",
    "settlers",
    "roanoke",
    "croatoan",
)

HISTORY_MYSTERY_TOPIC_KEYWORDS: tuple[str, ...] = (
    "roanoke",
    "colony",
    "croatoan",
    "colonist",
    "colonists",
    "settler",
    "settlers",
    "colonial settlement",
    "archaeological",
    "excavation",
    "artifact",
    "historical records",
)

SHORT_TOPIC_KEYWORD_MAX_LEN = 3

INSTRUCTIONAL_INTENT_MARKERS: tuple[str, ...] = (
    "method",
    "technique",
    "tutorial",
    "how to",
    "how-to",
    "guide",
    "tips",
    "trick",
    "step",
    "setup",
    "recipe",
    "learn",
    "training",
    "روش",
    "آموزش",
    "نحوه",
    "راهنما",
)

GENERIC_CINEMATIC_FILLER: tuple[str, ...] = (
    "walking on the shore",
    "walking along the shore",
    "staring at the horizon",
    "emotional journey",
    "contemplation",
    "holds a final stillness",
    "frame-ready end pose",
    "compelling lead subject",
    "emotional readability",
    "discover the first narrative clue",
    "environment reacts to rising pressure",
    "danger and possibility coexisting",
)

TOPIC_CATEGORY_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("fishing", ("fish", "fishing", "zander", "pike", "bass", "trout", "lure", "angler", "bait", "hook", "ماهی", "صید"), STRATEGY_INSTRUCTIONAL_FISHING),
    ("cooking", ("cook", "recipe", "kitchen", "bake", "food", "dish", "meal", "آشپزی", "غذا"), STRATEGY_RECIPE_TUTORIAL),
    ("history_mystery", HISTORY_MYSTERY_TOPIC_KEYWORDS, STRATEGY_HISTORICAL_INVESTIGATION),
    ("business_history", ("blockbuster", "netflix", "kodak", "business", "startup", "market disruption", "bankruptcy"), STRATEGY_BUSINESS_CASE_STUDY),
    ("history", ("history", "historical", "ancient", "war", "empire", "archival", "timeline"), STRATEGY_DOCUMENTARY),
    ("mystery", ("mystery", "unsolved", "detective", "clue", "cold case"), STRATEGY_NARRATIVE_MYSTERY),
    ("technology", ("tech", "software", "app", "gadget", "ai", "code", "programming", "laptop", "phone"), STRATEGY_EDUCATIONAL_TECH),
    ("horror", ("horror", "haunted", "creepy", "nightmare", "paranormal"), STRATEGY_HORROR_STORY),
    ("news", ("news", "breaking", "headline", "report", "update", "today"), STRATEGY_JOURNALISTIC),
    ("self_care", ("self care", "self-care", "skincare", "wellness", "meditation", "routine"), STRATEGY_EDUCATIONAL_LIFESTYLE),
    ("fitness", ("workout", "gym", "exercise", "training", "fitness", "yoga"), STRATEGY_INSTRUCTIONAL_GENERAL),
)

STRATEGY_PROFILES: dict[str, dict[str, Any]] = {
    STRATEGY_INSTRUCTIONAL_FISHING: {
        "label": "Instructional fishing strategy",
        "purpose": "teach or demonstrate a fishing method step by step",
        "niche_style": "documentary",
        "mood_override": "instructional",
        "required_terms_en": (
            "lure",
            "cast",
            "casting",
            "hook",
            "line",
            "depth",
            "technique",
            "method",
            "strike",
            "fish",
            "fishing",
            "tackle",
            "rod",
            "reel",
            "zander",
        ),
        "clip_roles_en": (
            "Setup — lure selection, rig preparation, fishing spot choice, and ready-to-cast preparation for {topic}.",
            "Technique — casting method, lure movement, retrieve rhythm, and water-depth strategy for {topic}.",
            "Result — fish strike, hook set, landing moment, and clear takeaway lesson from {topic}.",
        ),
        "clip_roles_fa": (
            "آماده‌سازی — انتخاب قلاب، تنظیم وسایل، انتخاب محل ماهیگیری و آماده‌سازی برای {topic}.",
            "تکنیک — روش پرتاب، حرکت قلاب، ریتم بازی خط و استراتژی عمق آب برای {topic}.",
            "نتیجه — لحظه strike، hook set، land کردن ماهی و جمع‌بندی آموزشی {topic}.",
        ),
        "conflict_en": "Will this exact {anchor} method produce a bite before conditions change?",
        "visual_hook_en": "Macro on lure, hook knot, and rod setup that instantly signals a teachable fishing method.",
        "seo_templates_en": (
            "How to {topic} (step-by-step)",
            "{topic}: lure, cast, and hook-set method",
            "The {anchor} fishing method explained in 30 seconds",
        ),
    },
    STRATEGY_RECIPE_TUTORIAL: {
        "label": "Recipe/tutorial strategy",
        "purpose": "teach preparation and cooking steps",
        "niche_style": "documentary",
        "mood_override": "instructional",
        "required_terms_en": ("ingredient", "step", "cook", "prepare", "mix", "heat", "serve", "recipe"),
        "clip_roles_en": (
            "Prep — ingredients, tools, and setup for {topic}.",
            "Process — core cooking technique and timing for {topic}.",
            "Result — plated outcome and final tip for {topic}.",
        ),
        "clip_roles_fa": (
            "آماده‌سازی — مواد، ابزار و setup برای {topic}.",
            "پخت — تکنیک اصلی و زمان‌بندی {topic}.",
            "نتیجه — خروجی نهایی و نکته پایانی {topic}.",
        ),
        "conflict_en": "Can this {anchor} method deliver the intended result on the first try?",
        "visual_hook_en": "Hands preparing the key ingredient that defines {topic}.",
        "seo_templates_en": (
            "How to make {topic}",
            "{topic} — easy step-by-step method",
        ),
    },
    STRATEGY_EDUCATIONAL_TECH: {
        "label": "Educational tech strategy",
        "purpose": "explain a tool, feature, or workflow",
        "niche_style": "documentary",
        "mood_override": "instructional",
        "required_terms_en": ("step", "feature", "tool", "setup", "method", "workflow", "demo"),
        "clip_roles_en": (
            "Problem/setup — why {topic} matters and initial context.",
            "Demonstration — core steps of {topic} shown clearly.",
            "Outcome — result, benefit, and takeaway for {topic}.",
        ),
        "clip_roles_fa": (
            "مسئله/setup — چرا {topic} مهم است.",
            "دموی تکنیک — مراحل اصلی {topic}.",
            "نتیجه — خروجی و takeaway برای {topic}.",
        ),
        "conflict_en": "Does this {anchor} workflow solve the viewer's problem quickly?",
        "visual_hook_en": "Screen or device detail that makes {topic} immediately understandable.",
        "seo_templates_en": ("How {topic} works", "{topic} explained fast"),
    },
    STRATEGY_DOCUMENTARY: {
        "label": "Documentary strategy",
        "purpose": "inform through evidence and context",
        "niche_style": "documentary",
        "mood_override": "documentary",
        "required_terms_en": ("history", "evidence", "context", "timeline", "fact"),
        "clip_roles_en": (
            "Hook — the central question behind {topic}.",
            "Evidence — the detail that reframes {topic}.",
            "Payoff — what {topic} means now.",
        ),
        "clip_roles_fa": (
            "قلاب — سوال اصلی درباره {topic}.",
            "مدرک — جزئیتی که {topic} را عوض می‌کند.",
            "نتیجه — معنای {topic} امروز.",
        ),
        "conflict_en": "What hidden detail changes our understanding of {topic}?",
        "visual_hook_en": "Archival or evidence detail tied directly to {topic}.",
        "seo_templates_en": ("The truth about {topic}", "What really happened: {topic}"),
    },
    STRATEGY_HISTORICAL_INVESTIGATION: {
        "label": "Historical investigation strategy",
        "purpose": "investigate a historical mystery through evidence and records",
        "niche_style": "documentary",
        "mood_override": "documentary",
        "required_terms_en": (
            "historical",
            "evidence",
            "records",
            "archaeological",
            "settlement",
            "colony",
            "investigation",
            "theory",
            "disappearance",
        ),
        "clip_roles_en": (
            "Hook — the historical question behind {subject}.",
            "Evidence — archival records, artifacts, or settlement details about {subject}.",
            "Payoff — the strongest theory or unresolved detail in {subject}.",
        ),
        "clip_roles_fa": (
            "قلاب — سوال تاریخی درباره {subject}.",
            "مدرک — سوابق، آثار یا جزئیات مربوط به {subject}.",
            "نتیجه — قوی‌ترین نظریه یا جزئیت حل‌نشده {subject}.",
        ),
        "conflict_en": "What do the historical records and archaeological evidence reveal about {subject}?",
        "visual_hook_en": "Archival map, settlement ruins, or carved clue tied directly to {subject}.",
        "seo_templates_en": ("What Really Happened to {subject}?", "The Lost {subject} Explained"),
    },
    STRATEGY_BUSINESS_CASE_STUDY: {
        "label": "Business case study strategy",
        "purpose": "explain a business rise, fall, or strategic mistake",
        "niche_style": "documentary",
        "mood_override": "documentary",
        "required_terms_en": (
            "business",
            "market",
            "strategy",
            "competition",
            "disruption",
            "model",
            "failure",
            "growth",
            "decision",
        ),
        "clip_roles_en": (
            "Hook — the business question behind {subject}.",
            "Evidence — the strategic mistake or market shift around {subject}.",
            "Payoff — what {subject} teaches about adaptation.",
        ),
        "clip_roles_fa": (
            "قلاب — سوال کسب‌وکار درباره {subject}.",
            "مدرک — اشتباه استراتژیک یا تغییر بازار در {subject}.",
            "نتیجه — درس {subject} برای سازگاری.",
        ),
        "conflict_en": "What strategic decision or market shift explains {subject}?",
        "visual_hook_en": "Business artifact, storefront, or product detail tied to {subject}.",
        "seo_templates_en": ("Why {subject} Failed", "How {subject} Changed the Market", "The Mistake Behind {subject}"),
    },
    STRATEGY_FUTURE_ANALYSIS: {
        "label": "Future analysis strategy",
        "purpose": "analyze a future threat, opportunity, or industry shift",
        "niche_style": "documentary",
        "mood_override": "documentary",
        "required_terms_en": (
            "future",
            "trend",
            "forecast",
            "prediction",
            "evidence",
            "impact",
            "change",
            "outcome",
            "2026",
            "automation",
        ),
        "clip_roles_en": (
            "Threat or opportunity — frame the future question behind {subject}.",
            "Evidence and trends — show the data, workflow shifts, or market signals around {subject}.",
            "Prediction and verdict — deliver the most likely outcome and what it means.",
        ),
        "clip_roles_fa": (
            "تهدید یا فرصت — سوال آینده درباره {subject}.",
            "مدرک و روند — داده‌ها و تغییرات پیرامون {subject}.",
            "پیش‌بینی — محتمل‌ترین نتیجه و معنای آن.",
        ),
        "conflict_en": "What future outcome is most likely for {subject}, and why?",
        "visual_hook_en": "Headline-worthy future signal tied directly to {subject}.",
        "seo_templates_en": (
            "Will {subject} by 2026?",
            "The Future of {subject} Explained",
            "What {subject} Means by 2026",
            "Why {subject} Could Change Everything",
        ),
    },
    STRATEGY_BUSINESS_DEBATE: {
        "label": "Business debate strategy",
        "purpose": "present a claim, evidence, and counterargument about an industry shift",
        "niche_style": "documentary",
        "mood_override": "documentary",
        "required_terms_en": (
            "claim",
            "evidence",
            "market",
            "industry",
            "agency",
            "business",
            "disruption",
            "automation",
            "strategy",
            "economics",
        ),
        "clip_roles_en": (
            "Claim — state the boldest business question about {subject}.",
            "Evidence — show supporting trends, economics, or workflow changes around {subject}.",
            "Counterargument and conclusion — stress-test the claim and deliver a nuanced verdict.",
        ),
        "clip_roles_fa": (
            "ادعا — جسورانه‌ترین سوال کسب‌وکار درباره {subject}.",
            "مدرک — روندها و شواهد پیرامون {subject}.",
            "نتیجه — آزمون ادعا و جمع‌بندی.",
        ),
        "conflict_en": "Does the evidence really support the disruption claim about {subject}?",
        "visual_hook_en": "Business artifact or workflow detail that makes the claim feel urgent.",
        "seo_templates_en": (
            "Will AI Replace {subject}?",
            "Can {subject} Survive the AI Revolution?",
            "The AI Threat Most {subject} Ignore",
            "Why AI Could Disrupt {subject}",
        ),
    },
    STRATEGY_TECHNOLOGY_FORECAST: {
        "label": "Technology forecast strategy",
        "purpose": "forecast how technology changes a role, workflow, or industry",
        "niche_style": "documentary",
        "mood_override": "documentary",
        "required_terms_en": (
            "ai",
            "workflow",
            "automation",
            "future",
            "tool",
            "role",
            "design",
            "replace",
            "adapt",
            "forecast",
        ),
        "clip_roles_en": (
            "Current reality — show how {subject} works today.",
            "Emerging change — reveal the AI tools, automation, or workflow shifts hitting {subject}.",
            "Future outcome — forecast which tasks survive and which disappear.",
        ),
        "clip_roles_fa": (
            "واقعیت فعلی — وضعیت امروزی {subject}.",
            "تغییر در راه — ابزارها و اتوماسیون در {subject}.",
            "آینده — چه چیزی باقی می‌ماند و چه چیزی حذف می‌شود.",
        ),
        "conflict_en": "Which parts of {subject} will humans still own after AI adoption?",
        "visual_hook_en": "Screen or workflow detail showing AI changing {subject} in real time.",
        "seo_templates_en": (
            "Will AI Replace {subject}?",
            "The Future of {subject} in an AI World",
            "What AI Still Cannot Do for {subject}",
            "Which {subject} Jobs AI Will Change First",
        ),
    },
    STRATEGY_SCIENTIFIC_EXPLANATION: {
        "label": "Scientific explanation strategy",
        "purpose": "explain the mechanism behind a why/how question",
        "niche_style": "documentary",
        "mood_override": "instructional",
        "required_terms_en": (
            "why",
            "because",
            "science",
            "notes",
            "molecule",
            "skin",
            "longevity",
            "concentration",
            "evidence",
            "mechanism",
        ),
        "clip_roles_en": (
            "Question — pose the why question with visible evidence and mechanism stakes behind {subject}.",
            "Mechanism — explain the science because molecules, concentration, skin chemistry, and note volatility drive {subject}.",
            "Takeaway — translate longevity, concentration, and evidence into a clear scientific conclusion about {subject}.",
        ),
        "clip_roles_fa": (
            "سوال — معمای why/how درباره {subject}.",
            "مکانیسم — توضیح علمی یا علت.",
            "نتیجه — جمع‌بندی برای بیننده.",
        ),
        "conflict_en": "What scientific mechanism actually explains {subject}?",
        "visual_hook_en": "Close-up detail that makes the scientific mechanism, concentration, and evidence visible.",
        "seo_templates_en": (
            "Why {subject}",
            "The Science Behind {subject}",
            "What Makes {subject} Work",
        ),
    },
    STRATEGY_NARRATIVE_MYSTERY: {
        "label": "Narrative mystery strategy",
        "purpose": "build curiosity and reveal",
        "niche_style": "mystery",
        "mood_override": "mysterious",
        "required_terms_en": ("clue", "mystery", "reveal", "secret", "question"),
        "clip_roles_en": (
            "Hook — unsettling clue about {topic}.",
            "Escalation — evidence intensifies around {topic}.",
            "Reveal — partial answer to {topic}.",
        ),
        "clip_roles_fa": (
            "قلاب — سرنخ مرموز درباره {topic}.",
            "تشدید — شواهد بیشتر برای {topic}.",
            "افشا — بخشی از پاسخ {topic}.",
        ),
        "conflict_en": "What does {anchor} hide about {topic}?",
        "visual_hook_en": "One unexplained detail in frame that demands answers about {topic}.",
        "seo_templates_en": ("What Really Happened at {subject}?", "Why {subject} Remains Unsolved"),
    },
    STRATEGY_HORROR_STORY: {
        "label": "Horror storytelling strategy",
        "purpose": "dread and payoff",
        "niche_style": "mystery",
        "mood_override": "mysterious",
        "required_terms_en": ("fear", "dark", "dread", "shadow", "silence"),
        "clip_roles_en": (
            "Dread setup for {topic}.",
            "Escalation around {topic}.",
            "Horror payoff for {topic}.",
        ),
        "clip_roles_fa": (
            "ایجاد ترس برای {topic}.",
            "تشدید ترس در {topic}.",
            "payoff ترسناک {topic}.",
        ),
        "conflict_en": "Something wrong is closing in around {topic}.",
        "visual_hook_en": "Wrong detail in frame tied to {topic}.",
        "seo_templates_en": ("{topic} gets worse fast", "Do not ignore {topic}"),
    },
    STRATEGY_JOURNALISTIC: {
        "label": "Journalistic strategy",
        "purpose": "report facts and implications",
        "niche_style": "documentary",
        "mood_override": "documentary",
        "required_terms_en": ("report", "update", "fact", "source", "impact"),
        "clip_roles_en": (
            "Lead — what happened in {topic}.",
            "Context — why {topic} matters.",
            "Impact — what changes because of {topic}.",
        ),
        "clip_roles_fa": (
            "خبر — چه اتفاقی در {topic}.",
            "زمینه — چرا {topic} مهم است.",
            "پیامد — چه چیزی عوض می‌شود.",
        ),
        "conflict_en": "What is the most important unanswered part of {topic}?",
        "visual_hook_en": "Headline-worthy visual tied to {topic}.",
        "seo_templates_en": ("{topic}: what you need to know", "Latest on {topic}"),
    },
    STRATEGY_EDUCATIONAL_LIFESTYLE: {
        "label": "Educational lifestyle strategy",
        "purpose": "teach a practical routine or habit",
        "niche_style": "documentary",
        "mood_override": "instructional",
        "required_terms_en": ("routine", "step", "habit", "tip", "method"),
        "clip_roles_en": (
            "Why {topic} matters.",
            "How to do {topic}.",
            "Result and routine takeaway for {topic}.",
        ),
        "clip_roles_fa": (
            "چرا {topic} مهم است.",
            "چگونه {topic} انجام دهیم.",
            "نتیجه و takeaway {topic}.",
        ),
        "conflict_en": "Will this {anchor} routine actually work for the viewer?",
        "visual_hook_en": "Clear before/after or routine detail for {topic}.",
        "seo_templates_en": ("{topic} routine that works", "Try this {topic} method"),
    },
    STRATEGY_INSTRUCTIONAL_GENERAL: {
        "label": "Instructional general strategy",
        "purpose": "teach steps for the topic",
        "niche_style": "documentary",
        "mood_override": "instructional",
        "required_terms_en": ("step", "method", "technique", "how", "setup", "result"),
        "clip_roles_en": (
            "Setup and preparation for {topic}.",
            "Core technique demonstration for {topic}.",
            "Result and takeaway for {topic}.",
        ),
        "clip_roles_fa": (
            "آماده‌سازی {topic}.",
            "نمایش تکنیک اصلی {topic}.",
            "نتیجه و takeaway {topic}.",
        ),
        "conflict_en": "Can the viewer replicate {topic} using this method?",
        "visual_hook_en": "Hands-on detail that teaches {topic} immediately.",
        "seo_templates_en": ("How to {topic}", "{topic} method step-by-step"),
    },
    STRATEGY_CINEMATIC_NARRATIVE: {
        "label": "Cinematic narrative strategy",
        "purpose": "character-driven visual story",
        "niche_style": "cinematic",
        "mood_override": "",
        "required_terms_en": (),
        "clip_roles_en": (
            "Opening beat for {topic}.",
            "Escalation around {topic}.",
            "Payoff for {topic}.",
        ),
        "clip_roles_fa": (
            "شروع {topic}.",
            "تشدید {topic}.",
            "payoff {topic}.",
        ),
        "conflict_en": "What is at stake in {topic}?",
        "visual_hook_en": "Strong visual detail tied to {topic}.",
        "seo_templates_en": ("{topic}", "Why {topic} matters"),
    },
}


TUTORIAL_STRATEGIES = frozenset(
    {
        STRATEGY_RECIPE_TUTORIAL,
        STRATEGY_INSTRUCTIONAL_FISHING,
        STRATEGY_INSTRUCTIONAL_GENERAL,
        STRATEGY_EDUCATIONAL_TECH,
    }
)


@dataclass
class TopicClassification:
    topic: str
    topic_category: str
    content_strategy: str
    instructional_intent: bool = False
    confidence: float = 0.0
    reasoning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "topic_category": self.topic_category,
            "content_strategy": self.content_strategy,
            "instructional_intent": self.instructional_intent,
            "confidence": round(self.confidence, 4),
            "reasoning": self.reasoning,
        }


@dataclass
class ContentStrategyPlan:
    strategy_id: str
    label: str
    purpose: str
    niche_style: str
    effective_mood: str
    clip_beats: list[str]
    conflict: str
    visual_hook: str
    seo_title_candidates: list[str]
    required_terms: tuple[str, ...]
    forbidden_filler: tuple[str, ...] = GENERIC_CINEMATIC_FILLER

    def to_dict(self) -> dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "label": self.label,
            "purpose": self.purpose,
            "niche_style": self.niche_style,
            "effective_mood": self.effective_mood,
            "clip_beats": list(self.clip_beats),
            "conflict": self.conflict,
            "visual_hook": self.visual_hook,
            "seo_title_candidates": list(self.seo_title_candidates),
            "required_terms": list(self.required_terms),
            "forbidden_filler": list(self.forbidden_filler),
        }


@dataclass
class TopicStrategyAlignmentResult:
    topic: str
    content_strategy: str
    topic_strategy_alignment_score: float = 0.0
    seo_alignment: float = 0.0
    story_alignment: float = 0.0
    clip_alignment: float = 0.0
    prompt_alignment: float = 0.0
    generic_filler_hits: list[str] = field(default_factory=list)
    required_term_hits: list[str] = field(default_factory=list)
    passed: bool = False
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic": self.topic,
            "content_strategy": self.content_strategy,
            "topic_strategy_alignment_score": round(self.topic_strategy_alignment_score, 4),
            "seo_alignment": round(self.seo_alignment, 4),
            "story_alignment": round(self.story_alignment, 4),
            "clip_alignment": round(self.clip_alignment, 4),
            "prompt_alignment": round(self.prompt_alignment, 4),
            "generic_filler_hits": list(self.generic_filler_hits),
            "required_term_hits": list(self.required_term_hits),
            "passed": self.passed,
            "notes": list(self.notes),
        }


def classify_topic(topic: str, *, language_code: str = "en") -> TopicClassification:
    cleaned = _normalize(topic)
    instructional = _has_instructional_intent(cleaned)

    if _detect_historical_investigation(cleaned):
        return TopicClassification(
            topic=topic,
            topic_category="history_mystery",
            content_strategy=STRATEGY_HISTORICAL_INVESTIGATION,
            instructional_intent=False,
            confidence=0.96,
            reasoning="Historical investigation question pattern detected (what happened / mystery / disappearance).",
        )

    domain = extract_topic_domain(topic)
    category = domain or "general"
    strategy = STRATEGY_CINEMATIC_NARRATIVE
    confidence = 0.55
    reasoning = "Default cinematic narrative fallback."

    for cat, keywords, mapped_strategy in TOPIC_CATEGORY_RULES:
        if any(topic_keyword_matches(keyword, cleaned) for keyword in keywords):
            category = cat
            strategy = mapped_strategy
            confidence = 0.88
            reasoning = f"Matched category '{cat}' from topic keywords."
            break

    if instructional and strategy == STRATEGY_CINEMATIC_NARRATIVE:
        strategy = STRATEGY_INSTRUCTIONAL_GENERAL
        confidence = 0.72
        reasoning = "Instructional intent detected without specific domain."

    if category == "fishing" or ("fish" in cleaned and instructional):
        category = "fishing"
        strategy = STRATEGY_INSTRUCTIONAL_FISHING
        confidence = 0.95
        reasoning = "Fishing topic with instructional/method intent."

    if "perfume" in cleaned or "fragrance" in cleaned or "scent" in cleaned:
        category = "perfume"
        strategy = STRATEGY_EDUCATIONAL_LIFESTYLE
        if "best" in cleaned or "review" in cleaned or "winter" in cleaned or "summer" in cleaned:
            strategy = STRATEGY_CINEMATIC_NARRATIVE
        confidence = max(confidence, 0.9)
        reasoning = "Perfume/fragrance topic detected."

    if "pizza" in cleaned or "dough" in cleaned or "bread" in cleaned:
        category = "cooking"
        strategy = STRATEGY_RECIPE_TUTORIAL if instructional else STRATEGY_RECIPE_TUTORIAL
        confidence = max(confidence, 0.9)
        reasoning = "Cooking/baking topic detected."

    return TopicClassification(
        topic=topic,
        topic_category=category,
        content_strategy=strategy,
        instructional_intent=instructional,
        confidence=confidence,
        reasoning=reasoning,
    )


def build_content_strategy_plan(
    topic: str,
    classification: TopicClassification,
    *,
    language_code: str = "en",
    mood: str = "emotional",
    clip_count: int = 3,
) -> ContentStrategyPlan:
    profile = dict(STRATEGY_PROFILES.get(classification.content_strategy) or STRATEGY_PROFILES[STRATEGY_CINEMATIC_NARRATIVE])
    lang = language_code.split("-")[0] if language_code else "en"
    anchor = " ".join(extract_topic_anchor_tokens(topic, limit=2))
    domain_profile = get_domain_profile(topic, topic_category=classification.topic_category)
    story_strategy = resolve_story_strategy(classification.content_strategy)
    roles_key = "clip_roles_fa" if lang == "fa" else "clip_roles_en"
    roles = list(profile.get(roles_key) or profile.get("clip_roles_en") or ())
    if domain_profile.instructional_beats_en and (
        classification.content_strategy.startswith("instructional")
        or classification.content_strategy in {STRATEGY_RECIPE_TUTORIAL, STRATEGY_EDUCATIONAL_TECH, STRATEGY_EDUCATIONAL_LIFESTYLE}
        or classification.content_strategy
        in {
            STRATEGY_HISTORICAL_INVESTIGATION,
            STRATEGY_DOCUMENTARY,
            STRATEGY_NARRATIVE_MYSTERY,
            STRATEGY_BUSINESS_CASE_STUDY,
            STRATEGY_FUTURE_ANALYSIS,
            STRATEGY_BUSINESS_DEBATE,
            STRATEGY_TECHNOLOGY_FORECAST,
            STRATEGY_SCIENTIFIC_EXPLANATION,
        }
    ):
        roles = list(domain_profile.instructional_beats_en)
    elif domain_profile.review_beats_en and any(
        marker in topic.lower() for marker in ("best", "review", "winter", "summer", "vs", "comparison")
    ):
        roles = list(domain_profile.review_beats_en)
    elif not roles:
        roles = list(story_strategy.clip_beat_structure)
    beats: list[str] = []
    for index in range(max(1, clip_count)):
        template = roles[min(index, len(roles) - 1)] if roles else f"Beat {index + 1} for {topic}."
        beats.append(_normalize(template.format(topic=topic, anchor=anchor or topic, subject=_strategy_subject_phrase(topic, anchor))))

    conflict_key = "conflict_en"
    hook_key = "visual_hook_en"
    seo_key = "seo_templates_en"
    subject = _strategy_subject_phrase(topic, anchor)
    conflict = str(profile.get(conflict_key) or "What is the core question behind {topic}?").format(
        topic=topic,
        anchor=anchor or topic,
        subject=subject,
    )
    visual_hook = str(profile.get(hook_key) or "Visual detail that teaches {topic}.").format(
        topic=topic,
        anchor=anchor or topic,
        subject=subject,
    )
    seo_candidates = [
        _normalize(
            item.format(
                topic=topic,
                anchor=anchor or topic,
                subject=_strategy_subject_phrase(topic, anchor),
            )
        )
        for item in profile.get(seo_key) or (topic,)
    ]
    mood_override = str(profile.get("mood_override") or "").strip()
    effective_mood = mood_override or mood

    return ContentStrategyPlan(
        strategy_id=classification.content_strategy,
        label=str(profile.get("label") or classification.content_strategy),
        purpose=str(profile.get("purpose") or ""),
        niche_style=str(profile.get("niche_style") or "documentary"),
        effective_mood=effective_mood,
        clip_beats=beats[:clip_count],
        conflict=conflict,
        visual_hook=visual_hook,
        seo_title_candidates=seo_candidates,
        required_terms=tuple(profile.get("required_terms_en") or ()),
    )


def audit_topic_strategy_alignment(
    topic: str,
    strategy_plan: ContentStrategyPlan,
    *,
    seo_title: str = "",
    story_payload: dict[str, Any] | None = None,
    clip_payloads: list[dict[str, Any]] | None = None,
    prompt_texts: list[str] | None = None,
) -> TopicStrategyAlignmentResult:
    story = dict(story_payload or {})
    clips = list(clip_payloads or [])
    prompts = list(prompt_texts or [])
    corpus_parts = [
        seo_title,
        str(story.get("title") or ""),
        str(story.get("logline") or ""),
        str(story.get("conflict_tension") or ""),
        str(story.get("visual_hook") or ""),
        str(story.get("main_character") or ""),
        str(story.get("setting") or ""),
    ]
    corpus_parts.extend(str(b) for b in story.get("clip_beats") or [])
    for clip in clips:
        corpus_parts.append(str(clip.get("story_beat") or clip.get("scene") or ""))
    corpus_parts.extend(prompts)
    corpus = _normalize(" ".join(part for part in corpus_parts if part))

    required_hits = [term for term in strategy_plan.required_terms if term in corpus]
    filler_hits = [phrase for phrase in strategy_plan.forbidden_filler if phrase in corpus]

    seo_alignment = _score_required_terms(seo_title, strategy_plan.required_terms)
    story_alignment = _score_required_terms(
        " ".join(
            [
                str(story.get("logline") or ""),
                str(story.get("conflict_tension") or ""),
                str(story.get("visual_hook") or ""),
            ]
        ),
        strategy_plan.required_terms,
    )
    clip_alignment = _score_required_terms(
        " ".join(str(b) for b in story.get("clip_beats") or []),
        strategy_plan.required_terms,
    )
    if clips:
        clip_alignment = max(
            clip_alignment,
            _score_required_terms(
                " ".join(str(c.get("story_beat") or c.get("scene") or "") for c in clips),
                strategy_plan.required_terms,
            ),
        )
    prompt_alignment = _score_required_terms(" ".join(prompts), strategy_plan.required_terms)

    alignment = (
        seo_alignment * 0.15
        + story_alignment * 0.3
        + clip_alignment * 0.35
        + prompt_alignment * 0.2
    )
    if filler_hits and strategy_plan.strategy_id != STRATEGY_CINEMATIC_NARRATIVE:
        alignment = max(0.0, alignment - 0.12 * len(filler_hits))
    if strategy_plan.strategy_id.startswith("instructional") or "instructional" in strategy_plan.strategy_id:
        if clip_alignment < 0.45:
            alignment = min(alignment, 0.49)

    passed = alignment >= 0.55 and (not filler_hits or alignment >= 0.7)
    if strategy_plan.strategy_id == STRATEGY_INSTRUCTIONAL_FISHING:
        passed = alignment >= 0.6 and clip_alignment >= 0.5 and len(required_hits) >= 3

    notes: list[str] = []
    if filler_hits:
        notes.append(f"generic_filler_detected:{len(filler_hits)}")
    if len(required_hits) < 2 and strategy_plan.required_terms:
        notes.append("low_required_term_coverage")
    if not passed:
        notes.append("topic_strategy_alignment_failed")

    return TopicStrategyAlignmentResult(
        topic=topic,
        content_strategy=strategy_plan.strategy_id,
        topic_strategy_alignment_score=round(min(1.0, max(0.0, alignment)), 4),
        seo_alignment=round(seo_alignment, 4),
        story_alignment=round(story_alignment, 4),
        clip_alignment=round(clip_alignment, 4),
        prompt_alignment=round(prompt_alignment, 4),
        generic_filler_hits=filler_hits,
        required_term_hits=required_hits,
        passed=passed,
        notes=notes,
    )


def audit_post_prompt_strategy_alignment(
    topic: str,
    strategy_plan: ContentStrategyPlan,
    *,
    seo_title: str = "",
    story_payload: dict[str, Any] | None = None,
    clip_payloads: list[dict[str, Any]] | None = None,
    prompt_texts: list[str] | None = None,
) -> TopicStrategyAlignmentResult:
    """Recalculate strategy alignment after prompt generation with prompt-forward weighting."""
    base = audit_topic_strategy_alignment(
        topic,
        strategy_plan,
        seo_title=seo_title,
        story_payload=story_payload,
        clip_payloads=clip_payloads,
        prompt_texts=prompt_texts,
    )
    alignment = (
        base.seo_alignment * 0.12
        + base.story_alignment * 0.23
        + base.clip_alignment * 0.30
        + base.prompt_alignment * 0.35
    )
    passed = alignment >= 0.80 and base.prompt_alignment >= 0.70
    notes = list(base.notes)
    if not passed:
        notes.append("post_prompt_strategy_alignment_failed")
    return TopicStrategyAlignmentResult(
        topic=base.topic,
        content_strategy=base.content_strategy,
        topic_strategy_alignment_score=round(min(1.0, max(0.0, alignment)), 4),
        seo_alignment=base.seo_alignment,
        story_alignment=base.story_alignment,
        clip_alignment=base.clip_alignment,
        prompt_alignment=base.prompt_alignment,
        generic_filler_hits=base.generic_filler_hits,
        required_term_hits=base.required_term_hits,
        passed=passed,
        notes=notes,
    )


def _has_instructional_intent(text: str) -> bool:
    return any(marker in text for marker in INSTRUCTIONAL_INTENT_MARKERS)


def _score_required_terms(text: str, required_terms: tuple[str, ...], *, weight: float = 1.0) -> float:
    del weight
    if not required_terms:
        return 0.75
    lowered = _normalize(text)
    if not lowered:
        return 0.0
    hits = sum(1 for term in required_terms if term in lowered)
    target = max(3, min(len(required_terms), 8))
    return min(1.0, hits / target)


def _strategy_subject_phrase(topic: str, anchor: str) -> str:
    try:
        from content_brain.execution.content_brain_topic_story_detail import _extract_subject_phrase

        return _extract_subject_phrase(topic)
    except ImportError:  # pragma: no cover
        return anchor or topic


def topic_keyword_matches(keyword: str, text: str) -> bool:
    token = str(keyword or "").strip().lower()
    cleaned = str(text or "").strip().lower()
    if not token or not cleaned:
        return False
    if len(token) <= SHORT_TOPIC_KEYWORD_MAX_LEN:
        return bool(re.search(rf"(?<![\w-]){re.escape(token)}(?![\w-])", cleaned))
    return token in cleaned


def _detect_historical_investigation(text: str) -> bool:
    cleaned = _normalize(text)
    if any(re.search(pattern, cleaned) for pattern in HISTORICAL_INVESTIGATION_PATTERNS):
        return True
    if any(topic_keyword_matches(keyword, cleaned) for keyword in HISTORY_MYSTERY_TOPIC_KEYWORDS):
        return True
    if any(re.search(pattern, cleaned) for pattern in HISTORICAL_INVESTIGATION_WEAK_PATTERNS):
        return any(topic_keyword_matches(keyword, cleaned) for keyword in HISTORY_CONTEXT_KEYWORDS)
    return False


def _normalize(text: str) -> str:
    return " ".join(str(text or "").split()).strip().lower()


__all__ = [
    "ContentStrategyPlan",
    "TopicClassification",
    "TopicStrategyAlignmentResult",
    "audit_post_prompt_strategy_alignment",
    "audit_topic_strategy_alignment",
    "build_content_strategy_plan",
    "classify_topic",
    "STRATEGY_BUSINESS_CASE_STUDY",
    "STRATEGY_FUTURE_ANALYSIS",
    "STRATEGY_BUSINESS_DEBATE",
    "STRATEGY_TECHNOLOGY_FORECAST",
    "STRATEGY_SCIENTIFIC_EXPLANATION",
    "TUTORIAL_STRATEGIES",
]
