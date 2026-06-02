"""
Phase 12J-D-B — Topic-class visual grammar for Story Intelligence.

Loads beat × topic_class cinematography from config; resolves topic_class from profile/topic/niche.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GRAMMAR_VERSION = "12j_d_b_v1"
ENGINE_NAME = "TopicClassGrammarEngine"

VALID_TOPIC_CLASSES = frozenset(
    {
        "animal",
        "football",
        "mystery",
        "horror",
        "history",
        "science",
        "finance",
        "self_care",
        "travel",
        "technology",
        "general_investigation",
    }
)

REQUIRED_BEATS = frozenset(
    {
        "HOOK_BEAT",
        "CONTEXT_BEAT",
        "ESCALATION_BEAT",
        "PATTERN_BREAK",
        "PAYOFF_BEAT",
        "LOOP_SEED",
    }
)

NICHE_CLASS_MAP: dict[str, str] = {
    "football": "football",
    "dark_mystery": "horror",
    "storytelling": "horror",
    "horror": "horror",
    "mystery": "mystery",
}

SEMANTIC_DOMAIN_CLASS_MAP: dict[str, str] = {
    "football": "football",
    "horror": "horror",
    "dark_mystery": "horror",
    "education": "science",
    "perfume": "general_investigation",
}

TOPIC_HEURISTIC_RULES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "football",
        (
            "football",
            "soccer",
            "premier league",
            "champions league",
            "world cup",
            "goalkeeper",
            "striker",
            "penalty",
            "var review",
            "offside",
        ),
    ),
    (
        "animal",
        (
            "dog",
            "cat",
            "bird",
            "wildlife",
            "pet",
            "puppy",
            "kitten",
            "horse",
            "wolf",
            "animal",
            "zoo",
        ),
    ),
    (
        "horror",
        ("horror", "haunted", "creepy", "nightmare", "demonic", "paranormal"),
    ),
    (
        "mystery",
        ("mystery", "unsolved", "detective", "clue", "cold case", "whodunit"),
    ),
    (
        "history",
        (
            "history",
            "historical",
            "ancient",
            "century",
            "archival",
            "world war",
            "civil war",
            "empire",
            "timeline",
        ),
    ),
    (
        "science",
        (
            "science",
            "scientific",
            "experiment",
            "laboratory",
            "physics",
            "chemistry",
            "biology",
            "molecule",
            "hypothesis",
        ),
    ),
    (
        "finance",
        (
            "finance",
            "financial",
            "stock",
            "market",
            "crypto",
            "bitcoin",
            "trading",
            "inflation",
            "recession",
            "portfolio",
        ),
    ),
    (
        "self_care",
        (
            "self care",
            "self-care",
            "skincare",
            "wellness",
            "meditation",
            "mental health",
            "morning routine",
            "habit",
        ),
    ),
    (
        "travel",
        (
            "travel",
            "destination",
            "airport",
            "road trip",
            "backpack",
            "landmark",
            "itinerary",
            "city guide",
        ),
    ),
    (
        "technology",
        (
            "technology",
            "tech",
            "gadget",
            "smartphone",
            "software",
            "hardware",
            "app",
            "laptop",
            "processor",
            "ai tool",
        ),
    ),
)

# Legacy Story Intelligence tables (12J-D-A regression anchor).
LEGACY_GENERAL_INVESTIGATION: dict[str, dict[str, str]] = {
    "HOOK_BEAT": {
        "camera": "Tight macro on evidence detail, shallow depth of field",
        "motion": "Snap focus rack to evidence detail",
        "framing": "Evidence-forward macro framing",
        "action": "Reveal {anchor} detail entering frame",
        "reveal_style": "Partial evidence visible before context",
        "escalation_style": "",
        "payoff_style": "",
        "visual_texture": "topic-specific object in sharp focus",
        "pacing": "curiosity",
        "subject": "{anchor} evidence element",
        "environment": "{niche_label} setting anchored to {anchor}",
    },
    "CONTEXT_BEAT": {
        "camera": "Medium-wide establishing with subject in lower third",
        "motion": "Gentle lateral slide across environment",
        "framing": "Establishing context frame",
        "action": "Show {anchor} in situ within environment",
        "reveal_style": "",
        "escalation_style": "",
        "payoff_style": "",
        "visual_texture": "environmental texture tied to claim",
        "pacing": "grounding",
        "subject": "{anchor} evidence element",
        "environment": "{niche_label} setting anchored to {anchor}",
    },
    "ESCALATION_BEAT": {
        "camera": "Slow push-in on contradicting detail",
        "motion": "Controlled push-in as tension builds",
        "framing": "Contradiction-forward push-in",
        "action": "Contrast two readings of {anchor}",
        "reveal_style": "",
        "escalation_style": "Contradiction between two readings of {anchor}",
        "payoff_style": "",
        "visual_texture": "contrasting before/after frame",
        "pacing": "tension",
        "subject": "{anchor} evidence element",
        "environment": "{niche_label} setting anchored to {anchor}",
    },
    "PATTERN_BREAK": {
        "camera": "Whip-pan or split-diopter between two frames",
        "motion": "Abrupt perspective shift or frame swap",
        "framing": "Perspective break frame",
        "action": "Swap or overlay frame to reframe {anchor}",
        "reveal_style": "",
        "escalation_style": "",
        "payoff_style": "",
        "visual_texture": "annotated screen capture",
        "pacing": "surprise",
        "subject": "{anchor} evidence element",
        "environment": "{niche_label} setting anchored to {anchor}",
    },
    "PAYOFF_BEAT": {
        "camera": "Locked-off hero frame with decisive reveal element centered",
        "motion": "Hold steady; micro-movement only on reveal",
        "framing": "Decisive hero framing",
        "action": "Hold on decisive {anchor} evidence",
        "reveal_style": "",
        "escalation_style": "",
        "payoff_style": "Decisive proof centered on {anchor}",
        "visual_texture": "evidence detail macro shot",
        "pacing": "payoff",
        "subject": "{anchor} evidence element",
        "environment": "{niche_label} setting anchored to {anchor}",
    },
    "LOOP_SEED": {
        "camera": "Pull-back reveal leaving one element unresolved at frame edge",
        "motion": "Slow drift away from incomplete detail",
        "framing": "Open-loop edge framing",
        "action": "Leave {anchor} partially obscured at frame edge",
        "reveal_style": "",
        "escalation_style": "",
        "payoff_style": "",
        "visual_texture": "incomplete detail at frame edge",
        "pacing": "open_loop",
        "subject": "{anchor} evidence element",
        "environment": "{niche_label} setting anchored to {anchor}",
    },
}


def _grammar_config_path() -> Path:
    return Path(__file__).resolve().parent.parent / "config" / "topic_class_grammar_v1.json"


def _normalize_topic(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


@dataclass
class TopicClassResolution:
    topic_class: str
    resolution_source: str
    grammar_version: str = GRAMMAR_VERSION


@dataclass
class VisualGrammarMetadata:
    topic_class: str
    resolution_source: str
    grammar_version: str
    beat_grammar_used: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "topic_class": self.topic_class,
            "resolution_source": self.resolution_source,
            "grammar_version": self.grammar_version,
            "beat_grammar_used": list(self.beat_grammar_used),
        }


class TopicClassGrammarEngine:
    """Resolve topic class and provide beat-level visual grammar cells."""

    def __init__(self, *, config_path: Path | None = None) -> None:
        self._config_path = config_path or _grammar_config_path()
        self._config = self._load_config()
        self.resolved_topic_class: str = "general_investigation"
        self.resolution_source: str = "fallback:general_investigation"
        self.beat_grammar_used: list[dict[str, str]] = []

    @property
    def grammar_version(self) -> str:
        return str(self._config.get("grammar_version") or GRAMMAR_VERSION)

    def _load_config(self) -> dict[str, Any]:
        if self._config_path.is_file():
            raw = json.loads(self._config_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
        return {"grammar_version": GRAMMAR_VERSION, "classes": {"general_investigation": LEGACY_GENERAL_INVESTIGATION}}

    def resolve_topic_class(
        self,
        topic: str,
        niche: str,
        profile: dict[str, Any] | None = None,
        *,
        semantic_domain: str | None = None,
    ) -> TopicClassResolution:
        profile = _dict(profile)
        topic_norm = _normalize_topic(topic)
        niche_norm = str(niche or profile.get("niche") or "general").strip().lower()

        explicit = str(profile.get("topic_class") or "").strip().lower()
        if explicit in VALID_TOPIC_CLASSES:
            self.resolved_topic_class = explicit
            self.resolution_source = "explicit:profile.topic_class"
            return TopicClassResolution(explicit, self.resolution_source, self.grammar_version)

        brief = _dict(profile.get("brief_snapshot"))
        run_context = _dict(brief.get("run_context"))
        explicit_rc = str(run_context.get("topic_class") or "").strip().lower()
        if explicit_rc in VALID_TOPIC_CLASSES:
            self.resolved_topic_class = explicit_rc
            self.resolution_source = "explicit:run_context.topic_class"
            return TopicClassResolution(explicit_rc, self.resolution_source, self.grammar_version)

        if niche_norm in NICHE_CLASS_MAP:
            mapped = NICHE_CLASS_MAP[niche_norm]
            self.resolved_topic_class = mapped
            self.resolution_source = f"niche_map:{niche_norm}"
            return TopicClassResolution(mapped, self.resolution_source, self.grammar_version)

        for class_id, phrases in TOPIC_HEURISTIC_RULES:
            if any(phrase in topic_norm for phrase in phrases):
                self.resolved_topic_class = class_id
                self.resolution_source = f"topic_heuristics:{class_id}"
                return TopicClassResolution(class_id, self.resolution_source, self.grammar_version)

        domain = str(semantic_domain or "").strip().lower()
        if not domain:
            semantic = profile.get("semantic_universe")
            if isinstance(semantic, dict):
                domain = str(semantic.get("domain") or "").strip().lower()

        if domain in SEMANTIC_DOMAIN_CLASS_MAP:
            mapped = SEMANTIC_DOMAIN_CLASS_MAP[domain]
            self.resolved_topic_class = mapped
            self.resolution_source = f"semantic_domain:{domain}"
            return TopicClassResolution(mapped, self.resolution_source, self.grammar_version)

        self.resolved_topic_class = "general_investigation"
        self.resolution_source = "fallback:general_investigation"
        return TopicClassResolution(
            self.resolved_topic_class,
            self.resolution_source,
            self.grammar_version,
        )

    def get_grammar(self, topic_class: str, beat_id: str) -> dict[str, str]:
        normalized_class = str(topic_class or "").strip().lower()
        if normalized_class not in VALID_TOPIC_CLASSES:
            normalized_class = "general_investigation"

        classes = _dict(self._config.get("classes"))
        class_block = _dict(classes.get(normalized_class))
        cell = _dict(class_block.get(beat_id))

        if not cell and normalized_class != "general_investigation":
            cell = _dict(_dict(classes.get("general_investigation")).get(beat_id))

        if not cell:
            cell = dict(LEGACY_GENERAL_INVESTIGATION.get(beat_id, {}))

        return {key: str(value) for key, value in cell.items()}

    def format_action(
        self,
        template: str,
        *,
        anchor: str,
        topic: str,
        niche_label: str,
    ) -> str:
        return (
            str(template or "")
            .replace("{anchor}", anchor or "subject")
            .replace("{topic}", topic or anchor or "topic")
            .replace("{niche_label}", niche_label or "setting")
        )

    def apply_beat_grammar(
        self,
        beat_id: str,
        *,
        topic_class: str | None = None,
        anchor: str,
        topic: str,
        niche_label: str,
        scene_role: str,
        fallback_lexicon: str,
    ) -> dict[str, str]:
        resolved_class = topic_class or self.resolved_topic_class
        cell = self.get_grammar(resolved_class, beat_id)
        pacing = cell.get("pacing") or "tension"
        texture = cell.get("visual_texture") or fallback_lexicon
        visual_description = (
            f"{texture} highlighting {anchor} during {scene_role} — "
            f"specific to {topic}, not generic stock footage."
        )

        entry = {
            "topic_class": resolved_class,
            "beat_id": beat_id,
            "camera": cell.get("camera", ""),
            "motion": cell.get("motion", ""),
        }
        self.beat_grammar_used.append(entry)

        return {
            "camera_direction": cell.get("camera", "Purposeful medium shot"),
            "motion_direction": cell.get("motion", "Deliberate camera move supporting beat purpose"),
            "framing": cell.get("framing", ""),
            "action": self.format_action(
                cell.get("action", "Show {anchor} with narrative purpose"),
                anchor=anchor,
                topic=topic,
                niche_label=niche_label,
            ),
            "visual_description": visual_description,
            "pacing": pacing,
            "subject": self.format_action(
                cell.get("subject", "{anchor} evidence element"),
                anchor=anchor,
                topic=topic,
                niche_label=niche_label,
            ),
            "environment": self.format_action(
                cell.get("environment", "{niche_label} setting anchored to {anchor}"),
                anchor=anchor,
                topic=topic,
                niche_label=niche_label,
            ),
            "reveal_style": cell.get("reveal_style", ""),
            "escalation_style": cell.get("escalation_style", ""),
            "payoff_style": cell.get("payoff_style", ""),
        }

    def metadata(self) -> VisualGrammarMetadata:
        return VisualGrammarMetadata(
            topic_class=self.resolved_topic_class,
            resolution_source=self.resolution_source,
            grammar_version=self.grammar_version,
            beat_grammar_used=list(self.beat_grammar_used),
        )


def build_default_grammar_config() -> dict[str, Any]:
    """Build full v1 grammar config (used by config file generator and tests)."""

    def cell(
        camera: str,
        motion: str,
        framing: str,
        action: str,
        *,
        reveal: str = "",
        escalation: str = "",
        payoff: str = "",
        texture: str = "",
        pacing: str = "tension",
        subject: str = "{anchor} focal subject",
        environment: str = "{niche_label} setting with {anchor}",
    ) -> dict[str, str]:
        return {
            "camera": camera,
            "motion": motion,
            "framing": framing,
            "action": action,
            "reveal_style": reveal,
            "escalation_style": escalation,
            "payoff_style": payoff,
            "visual_texture": texture,
            "pacing": pacing,
            "subject": subject,
            "environment": environment,
        }

    classes: dict[str, dict[str, dict[str, str]]] = {
        "general_investigation": dict(LEGACY_GENERAL_INVESTIGATION),
        "animal": {
            "HOOK_BEAT": cell(
                "Eye-level close on {anchor}, shallow depth of field",
                "Slow approach as {anchor} notices lens",
                "Intimate observer framing",
                "Capture {anchor} behavioral surprise entering frame",
                reveal="Ear flick, freeze, or direct look from {anchor}",
                texture="fur texture, paw detail, natural light",
                pacing="curiosity",
                subject="{anchor} as living subject",
                environment="natural habitat with {anchor}",
            ),
            "CONTEXT_BEAT": cell(
                "Wide habitat establishing, {anchor} small in frame",
                "Gentle pan across environment",
                "Naturalistic documentary framing",
                "Show {anchor} moving through habitat context",
                texture="environmental texture, natural light",
                pacing="grounding",
            ),
            "ESCALATION_BEAT": cell(
                "Tracking medium shot following {anchor}",
                "Follow-cam at subject pace",
                "Motion-led animal framing",
                "Show {anchor} behavior that contradicts expectation",
                escalation="Behavior contradicts what viewer assumed about {anchor}",
                texture="motion blur at ground level, breath vapor",
                pacing="tension",
            ),
            "PATTERN_BREAK": cell(
                "Over-shoulder POV alternate angle on {anchor}",
                "Whip to new angle on {anchor}",
                "Subjective switch framing",
                "Reframe meaning of {anchor} behavior",
                pacing="surprise",
            ),
            "PAYOFF_BEAT": cell(
                "Close on decisive {anchor} behavior moment",
                "Hold with micro-expressions",
                "Emotional animal beat framing",
                "Hold on single behavior that tells the story",
                payoff="One clear {anchor} behavior delivers the answer",
                texture="eye catchlight, whisker detail",
                pacing="payoff",
            ),
            "LOOP_SEED": cell(
                "{anchor} exits frame or looks away",
                "Slow pull-back from {anchor}",
                "Open animal ending frame",
                "Leave {anchor} with unresolved behavior cue",
                pacing="open_loop",
            ),
        },
        "football": {
            "HOOK_BEAT": cell(
                "Broadcast tight on ball and player contact",
                "Fast cut-in from wide angle",
                "TV sports incident framing",
                "Freeze decisive contact moment with {anchor}",
                reveal="Foul, save, or deflection visible in frame",
                texture="pitch texture, kit fabric, stadium light",
                pacing="hype",
                subject="match incident involving {anchor}",
                environment="stadium pitch under match lights",
            ),
            "CONTEXT_BEAT": cell(
                "Wide stadium or tunnel establishing shot",
                "Crane or steadicam sweep",
                "Epic match scale framing",
                "Establish match context around {anchor}",
                texture="crowd blur, tunnel lights",
                pacing="grounding",
            ),
            "ESCALATION_BEAT": cell(
                "Sideline tracking parallel to play",
                "High-speed lateral tracking",
                "Action tracking sports frame",
                "Replay angle shows controversy over {anchor}",
                escalation="Replay reframes the {anchor} incident",
                texture="replay monitor glow, chalk line",
                pacing="tension",
            ),
            "PATTERN_BREAK": cell(
                "Split-screen or broadcast angle swap",
                "Hard cut between camera angles",
                "Multi-cam broadcast framing",
                "VAR or referee frame reframes {anchor} incident",
                pacing="surprise",
            ),
            "PAYOFF_BEAT": cell(
                "Goal-line or net camera hero frame",
                "Snap zoom settle on proof",
                "Decisive sports payoff framing",
                "Show ball or decision proof for {anchor}",
                payoff="Decisive match outcome visible",
                pacing="payoff",
            ),
            "LOOP_SEED": cell(
                "Crowd reaction wide shot",
                "Slow motion crowd rise",
                "Social reaction framing",
                "Hold unanswered fan reaction to {anchor}",
                pacing="open_loop",
            ),
        },
        "mystery": {
            "HOOK_BEAT": cell(
                "Macro on anomalous object tied to {anchor}",
                "Rack focus to hidden clue",
                "Clue-forward mystery framing",
                "Reveal partial clue about {anchor} with meaning withheld",
                reveal="Clue visible but context withheld",
                texture="annotated photo, timestamp, map pin",
                pacing="curiosity",
            ),
            "ESCALATION_BEAT": cell(
                "Over-shoulder examining evidence on {anchor}",
                "Push-in on contradicting detail",
                "Investigation framing",
                "Present two clues about {anchor} that cannot both be true",
                escalation="Two readings of {anchor} contradict",
                pacing="tension",
            ),
            "PAYOFF_BEAT": cell(
                "Locked evidence board with {anchor} centered",
                "Static hold on proof object",
                "Deduction payoff framing",
                "Connect clues into answer about {anchor}",
                payoff="Clue connection makes {anchor} clear",
                pacing="payoff",
            ),
            "PATTERN_BREAK": cell(
                "Mirror or reflection reveal of {anchor}",
                "Perspective flip",
                "Uncanny reframe",
                "New witness angle reframes {anchor}",
                pacing="surprise",
            ),
            "LOOP_SEED": cell(
                "Door ajar with redacted label near {anchor}",
                "Drift off evidence",
                "Open case framing",
                "Leave one detail about {anchor} unreadable",
                pacing="open_loop",
            ),
        },
        "horror": {
            "HOOK_BEAT": cell(
                "Low angle on wrong detail near {anchor}",
                "Slow creep-in",
                "Dread framing with negative space",
                "Reveal wrong detail in normal room around {anchor}",
                reveal="Shadow or reflection wrong near {anchor}",
                texture="flicker, door gap, stain texture",
                pacing="dread",
            ),
            "ESCALATION_BEAT": cell(
                "Handheld micro-shake close on {anchor}",
                "Jitter push-in",
                "Subjective fear framing",
                "Show space around {anchor} violating prior logic",
                escalation="Geometry or presence around {anchor} breaks logic",
                pacing="panic",
            ),
            "PAYOFF_BEAT": cell(
                "Extreme close on disturbing detail of {anchor}",
                "Freeze on aftershock",
                "Horror payoff framing",
                "Imply horror outcome for {anchor} without explanation",
                payoff="Implication lands on {anchor}",
                pacing="aftershock",
            ),
            "PATTERN_BREAK": cell(
                "Sudden wide after tight on {anchor}",
                "Violent perspective jump",
                "Jump-cut dread framing",
                "Impossible presence related to {anchor}",
                pacing="surprise",
            ),
            "LOOP_SEED": cell(
                "Light dies at edge near {anchor}",
                "Slow retreat",
                "Unresolved threat framing",
                "Sound continues off-screen near {anchor}",
                pacing="open_loop",
            ),
        },
        "history": {
            "HOOK_BEAT": cell(
                "Archival photo or artifact macro of {anchor}",
                "Ken Burns slow zoom",
                "Documentary archival framing",
                "Reveal date or inscription on {anchor} before context",
                reveal="Date or inscription legible on {anchor}",
                texture="yellowed paper, museum placard, stamp",
                pacing="authoritative",
            ),
            "ESCALATION_BEAT": cell(
                "Split-era comparison frame on {anchor}",
                "Dissolve or wipe transition",
                "Temporal contrast framing",
                "Show two eras disagree on {anchor}",
                escalation="Sources disagree about {anchor}",
                pacing="tension",
            ),
            "PAYOFF_BEAT": cell(
                "Primary source document hero on {anchor}",
                "Hold on underlined proof",
                "Verdict documentary framing",
                "Confirm claim about {anchor} with primary source",
                payoff="Primary source confirms {anchor}",
                pacing="clarity",
            ),
            "PATTERN_BREAK": cell(
                "Modern location match to archival {anchor}",
                "Match cut between eras",
                "Then-and-now framing",
                "Geography reframes reading of {anchor}",
                pacing="surprise",
            ),
            "LOOP_SEED": cell(
                "Unlabeled archive box near {anchor}",
                "Pull-back from archive shelf",
                "Sequel hook framing",
                "Missing page corner on {anchor}",
                pacing="open_loop",
            ),
        },
        "science": {
            "HOOK_BEAT": cell(
                "Macro on phenomenon related to {anchor}",
                "Focus pull to phenomenon",
                "Lab demonstration framing",
                "Show effect of {anchor} before mechanism named",
                reveal="Effect visible before explanation",
                texture="beaker meniscus, LED readout, grid paper",
                pacing="wonder",
            ),
            "ESCALATION_BEAT": cell(
                "Side-by-side control vs test on {anchor}",
                "Split dolly between setups",
                "Comparative proof framing",
                "Control fails while test of {anchor} succeeds",
                escalation="Control vs test diverge for {anchor}",
                pacing="rigor",
            ),
            "PAYOFF_BEAT": cell(
                "Graph or reaction peak hero for {anchor}",
                "Locked chart hold",
                "QED framing",
                "Data threshold crossed for {anchor}",
                payoff="Measurement confirms {anchor}",
                pacing="satisfaction",
            ),
            "PATTERN_BREAK": cell(
                "Microscope or monitor insert of {anchor}",
                "Cut to new scale",
                "Scale shift framing",
                "Micro structure explains macro {anchor}",
                pacing="surprise",
            ),
            "LOOP_SEED": cell(
                "Experiment still running on {anchor}",
                "Time-lapse hint motion",
                "Open question framing",
                "Unread measurement on {anchor}",
                pacing="open_loop",
            ),
        },
        "finance": {
            "HOOK_BEAT": cell(
                "Screen macro on red candle or balance for {anchor}",
                "Snap scroll stop on chart",
                "Data hook framing",
                "Alert or number on {anchor} visible before story",
                reveal="Number flashes before narrative context",
                texture="ticker tape, card chip, invoice highlight",
                pacing="urgency",
            ),
            "ESCALATION_BEAT": cell(
                "Chart comparison wipe on {anchor}",
                "Accelerated timeline scrub",
                "Volatility framing",
                "Correlation breaks assumption about {anchor}",
                escalation="Chart pattern contradicts {anchor} thesis",
                pacing="anxiety",
            ),
            "PAYOFF_BEAT": cell(
                "Portfolio or account hero number for {anchor}",
                "Hold on final figure",
                "Consequence framing",
                "Gain or loss realized on screen for {anchor}",
                payoff="Final figure settles {anchor} story",
                pacing="resolution",
            ),
            "PATTERN_BREAK": cell(
                "Receipt or contract flash about {anchor}",
                "Hard cut insert",
                "Paper trail framing",
                "Hidden fee or clause exposed for {anchor}",
                pacing="surprise",
            ),
            "LOOP_SEED": cell(
                "Notification ping unresolved for {anchor}",
                "Pull to black",
                "Cliffhanger finance framing",
                "Pending transfer related to {anchor}",
                pacing="open_loop",
            ),
        },
        "self_care": {
            "HOOK_BEAT": cell(
                "Bathroom mirror close on {anchor} routine",
                "Soft handheld settle",
                "Relatable intimate framing",
                "Show small visible change in {anchor} routine",
                reveal="Subtle visible change in {anchor}",
                texture="steam, water drop, fabric texture",
                pacing="gentle",
            ),
            "ESCALATION_BEAT": cell(
                "Before/after split on {anchor} routine",
                "Gentle morph cut",
                "Transformation tension framing",
                "Routine step missing breaks {anchor} result",
                escalation="Missing step changes {anchor} outcome",
                pacing="friction",
            ),
            "PAYOFF_BEAT": cell(
                "Calm hero portrait after {anchor} routine",
                "Stable hold",
                "Relief payoff framing",
                "Visible calm payoff after {anchor}",
                payoff="Calm state proves {anchor} routine",
                pacing="calm",
            ),
            "PATTERN_BREAK": cell(
                "POV hands performing {anchor} ritual",
                "Top-down hands motion",
                "Tutorial intimacy framing",
                "Technique reframe for {anchor}",
                pacing="surprise",
            ),
            "LOOP_SEED": cell(
                "Alarm or calendar next-day cue for {anchor}",
                "Drift to window light",
                "Habit loop framing",
                "Tomorrow challenge for {anchor} teased",
                pacing="open_loop",
            ),
        },
        "travel": {
            "HOOK_BEAT": cell(
                "Landmark tease through foreground occlusion",
                "Reveal dolly toward {anchor}",
                "Destination hook framing",
                "Location almost recognizable around {anchor}",
                reveal="Destination nearly revealed",
                texture="cobblestone, foreign signage, transit blur",
                pacing="wanderlust",
            ),
            "ESCALATION_BEAT": cell(
                "Street-level culture contrast near {anchor}",
                "Walking steadicam follow",
                "Immersion travel framing",
                "Expectation vs reality mismatch for {anchor}",
                escalation="Reality contradicts expectation about {anchor}",
                pacing="surprise",
            ),
            "PAYOFF_BEAT": cell(
                "Golden hour hero vista of {anchor}",
                "Slow orbit on vista",
                "Awe payoff framing",
                "Definitive view proves {anchor} worth it",
                payoff="Hero vista confirms {anchor}",
                pacing="awe",
            ),
            "PATTERN_BREAK": cell(
                "Local detail vs tourist cliché at {anchor}",
                "Whip pan to local spot",
                "Cultural reframe",
                "Hidden spot locals use near {anchor}",
                pacing="surprise",
            ),
            "LOOP_SEED": cell(
                "Departure gate or suitcase near {anchor}",
                "Pull away from place",
                "Next journey framing",
                "Unread ticket stub for {anchor}",
                pacing="open_loop",
            ),
        },
        "technology": {
            "HOOK_BEAT": cell(
                "Product silhouette or LED edge on {anchor}",
                "Snap light-on reveal",
                "Product hook framing",
                "Device powers on or UI wakes for {anchor}",
                reveal="Device or UI wakes",
                texture="brushed aluminum, RGB edge, pixel grid",
                pacing="hype",
            ),
            "ESCALATION_BEAT": cell(
                "Stress test montage on {anchor}",
                "Fast insert cuts",
                "Torture test framing",
                "Old gen fails same test as {anchor}",
                escalation="Comparison undermines prior assumption about {anchor}",
                pacing="skepticism",
            ),
            "PAYOFF_BEAT": cell(
                "Hero product 360 or UI win state for {anchor}",
                "Locked hero orbit",
                "Spec payoff framing",
                "Benchmark or feature proof for {anchor}",
                payoff="Benchmark proves {anchor}",
                pacing="proof",
            ),
            "PATTERN_BREAK": cell(
                "Teardown slice interior of {anchor}",
                "Cutaway interior motion",
                "Insider teardown framing",
                "Hidden component justifies {anchor}",
                pacing="surprise",
            ),
            "LOOP_SEED": cell(
                "Firmware pending notification on {anchor}",
                "Pull to cable port",
                "Upgrade tease framing",
                "Feature still gated on {anchor}",
                pacing="open_loop",
            ),
        },
    }

    for class_id, beats in list(classes.items()):
        if class_id == "general_investigation":
            continue
        for beat_id in REQUIRED_BEATS:
            if beat_id not in beats:
                if beat_id in LEGACY_GENERAL_INVESTIGATION:
                    beats[beat_id] = dict(LEGACY_GENERAL_INVESTIGATION[beat_id])

    return {"grammar_version": GRAMMAR_VERSION, "classes": classes}


__all__ = [
    "TopicClassGrammarEngine",
    "TopicClassResolution",
    "VisualGrammarMetadata",
    "GRAMMAR_VERSION",
    "LEGACY_GENERAL_INVESTIGATION",
    "build_default_grammar_config",
]
