"""Concise integrated disease-management recommendations."""

from __future__ import annotations

DISEASE_SOLUTIONS = {
    "rust": (
        "Plant resistant corn hybrids where available, scout regularly to track "
        "pustule development, and use a locally registered foliar fungicide only "
        "when disease pressure and expected yield loss justify treatment."
    ),
    "gray_leaf": (
        "Rotate away from corn, manage infected crop residue to reduce carryover, "
        "and favor resistant hybrids. Consider a locally registered fungicide "
        "when susceptible plants face high disease pressure."
    ),
    "blight": (
        "Use resistant corn hybrids, rotate with a non-host crop, and encourage "
        "breakdown of infected residue. Apply a locally registered foliar "
        "fungicide only when scouting and economics support treatment."
    ),
    "Black Rot Grape Vine": (
        "Remove mummified fruit and infected prunings, destroy or bury diseased "
        "material, and prune the canopy to improve airflow and drying. Follow a "
        "preventive, locally approved fungicide program during susceptible growth "
        "stages when black rot risk is present."
    ),
    "Blight Grape Vine": (
        "Remove infected shoots, leaves, and fruit during dry weather, sanitize "
        "pruning tools, and improve canopy ventilation. Avoid prolonged leaf "
        "wetness and use a locally registered fungicide recommended for the "
        "confirmed grape blight pathogen."
    ),
}


def get_recommendation(disease_name: str) -> str | None:
    """Return no recommendation for healthy or unknown classes."""
    return DISEASE_SOLUTIONS.get(disease_name)
