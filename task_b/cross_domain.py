"""Cross-domain preference bridge for Task B."""

from __future__ import annotations

from task_b.schemas import RecommendRequest, RecommendationItem


class CrossDomainBridge:
    def expand_candidates(
        self,
        request: RecommendRequest,
        candidates: list[RecommendationItem],
    ) -> list[RecommendationItem]:
        if not request.enable_cross_domain:
            return candidates

        expanded = list(candidates)
        bridge_map = {
            "historical fiction": "cultural dining",
            "self-help": "productivity tools",
            "electronics": "smart accessories",
            "restaurant": "local experiences",
        }
        for item in candidates:
            mapped = bridge_map.get(item.category.lower())
            if mapped and len(expanded) < request.top_k + len(candidates):
                expanded.append(
                    RecommendationItem(
                        item_id=f"bridge-{item.item_id}",
                        title=f"Cross-domain pick inspired by {item.title}",
                        category=mapped,
                        score=max(0.4, item.score - 0.1),
                        explanation="Added through cross-domain preference transfer from the user's adjacent interests.",
                        source="cross_domain",
                    )
                )
        return expanded
