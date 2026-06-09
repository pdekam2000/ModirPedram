"""
Topic Knowledge Graph V1 — lightweight domain expansion graph.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from content_brain.execution.domain_knowledge_layer import resolve_domain


@dataclass
class KnowledgeGraphNode:
    node_id: str
    label: str
    node_type: str = "concept"
    related: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "label": self.label,
            "node_type": self.node_type,
            "related": list(self.related),
        }


GRAPH_DATA: dict[str, tuple[KnowledgeGraphNode, ...]] = {
    "fishing": (
        KnowledgeGraphNode("zander", "zander", "species", ("lure fishing", "night fishing", "depth strategy")),
        KnowledgeGraphNode("pike", "pike", "species", ("lure fishing", "weed edges")),
        KnowledgeGraphNode("carp", "carp", "species", ("bait fishing", "lake fishing")),
        KnowledgeGraphNode("bass", "bass", "species", ("lure fishing", "drop-offs")),
        KnowledgeGraphNode("lure fishing", "lure fishing", "technique", ("retrieve", "depth strategy")),
        KnowledgeGraphNode("night fishing", "night fishing", "technique", ("shallow water", "zander")),
        KnowledgeGraphNode("knots", "fishing knots", "technique", ("line", "hook set")),
        KnowledgeGraphNode("depth strategy", "depth strategy", "technique", ("water temperature", "current")),
    ),
    "perfume": (
        KnowledgeGraphNode("oud", "oud", "material", ("accord building", "niche perfume")),
        KnowledgeGraphNode("vanilla", "vanilla", "material", ("base notes", "longevity")),
        KnowledgeGraphNode("amber", "amber", "material", ("accord building", "projection")),
        KnowledgeGraphNode("projection", "projection", "concept", ("longevity", "layering")),
        KnowledgeGraphNode("maceration", "maceration", "process", ("blending", "raw materials")),
        KnowledgeGraphNode("layering", "layering", "technique", ("top notes", "heart notes")),
    ),
    "cooking": (
        KnowledgeGraphNode("dough", "dough", "concept", ("hydration", "kneading", "proofing")),
        KnowledgeGraphNode("fermentation", "fermentation", "process", ("proofing", "yeast")),
        KnowledgeGraphNode("hydration", "hydration", "concept", ("flour", "gluten")),
        KnowledgeGraphNode("crust", "crust", "result", ("oven spring", "baking")),
        KnowledgeGraphNode("toppings", "toppings", "concept", ("sauce", "baking")),
    ),
    "dog_training": (
        KnowledgeGraphNode("recall", "recall", "command", ("leash", "reward", "timing")),
        KnowledgeGraphNode("crate training", "crate training", "technique", ("consistency", "puppy")),
        KnowledgeGraphNode("leash", "leash", "tool", ("timing", "correction")),
    ),
    "technology": (
        KnowledgeGraphNode("workflow", "workflow", "concept", ("automation", "productivity")),
        KnowledgeGraphNode("prompt", "prompt", "concept", ("tool", "use case")),
        KnowledgeGraphNode("comparison", "comparison", "format", ("review", "setup")),
    ),
}


def get_knowledge_graph(topic: str, *, topic_category: str = "") -> dict[str, Any]:
    domain = resolve_domain(topic, topic_category=topic_category)
    if "dog" in topic.lower() or "puppy" in topic.lower():
        domain = "dog_training"
    nodes = list(GRAPH_DATA.get(domain, ()))
    matched = [node for node in nodes if node.node_id in topic.lower() or node.label in topic.lower()]
    related_labels: list[str] = []
    for node in matched or nodes[:4]:
        related_labels.extend(list(node.related))
    keywords = list(dict.fromkeys([node.label for node in nodes[:8]] + related_labels))[:12]
    return {
        "domain": domain,
        "nodes": [node.to_dict() for node in nodes],
        "matched_nodes": [node.to_dict() for node in matched],
        "related_concepts": related_labels[:10],
        "seo_keywords": keywords,
    }


__all__ = ["get_knowledge_graph"]
