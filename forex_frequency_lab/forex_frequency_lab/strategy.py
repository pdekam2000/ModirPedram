def derive_strategies_from_catalog(catalog, scheme, top_n=5, min_count=8, min_edge=0.15):
    """Turn frequency-catalog entries with a real win-rate edge into trade
    rules: long if the pattern's forward win-rate leans up, short if it
    leans down. Ranked by |edge| * occurrence count.
    """
    candidates = []
    for r in catalog:
        win_rate = r.get("forward_win_rate")
        if win_rate is None or r["count"] < min_count:
            continue
        edge = win_rate - 0.5
        if abs(edge) < min_edge:
            continue
        candidates.append((abs(edge) * r["count"], r, edge))
    candidates.sort(key=lambda t: t[0], reverse=True)

    strategies = []
    for _score, r, edge in candidates[:top_n]:
        strategies.append(
            {
                "name": f"{scheme}:{r['pattern_code']}@{r['window_size']}(catalog)",
                "scheme": scheme,
                "pattern_code": r["pattern_code"],
                "window_size": r["window_size"],
                "direction": "long" if edge > 0 else "short",
                "source": "catalog",
                "discovery_count": r["count"],
                "discovery_win_rate": win_rate,
            }
        )
    return strategies


def derive_strategies_from_reverse(reverse_result, scheme, top_n=5, min_lift=3.0, min_occurrences=4):
    """Turn reverse-engineered precursors (patterns disproportionately seen
    right before big moves) into trade rules: long for precursors of big up
    moves, short for precursors of big down moves.
    """
    if reverse_result is None:
        return []

    strategies = []
    sides = [
        ("precursors_before_big_up_moves", "long"),
        ("precursors_before_big_down_moves", "short"),
    ]
    for key, direction in sides:
        records = reverse_result.get(key, [])
        picked = [
            r
            for r in records
            if r["lift"] is not None and r["lift"] >= min_lift and r["occurrences_before_outcome"] >= min_occurrences
        ]
        picked.sort(key=lambda r: r["lift"], reverse=True)
        for r in picked[:top_n]:
            strategies.append(
                {
                    "name": f"{scheme}:{r['pattern_code']}@{reverse_result['window_size']}(reverse-{direction})",
                    "scheme": scheme,
                    "pattern_code": r["pattern_code"],
                    "window_size": reverse_result["window_size"],
                    "direction": direction,
                    "source": "reverse",
                    "discovery_count": r["occurrences_before_outcome"],
                    "discovery_lift": r["lift"],
                }
            )
    return strategies
