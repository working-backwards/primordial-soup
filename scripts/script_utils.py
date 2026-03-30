"""Shared utilities for simulation scripts.

This module provides common infrastructure used across scripts in the
scripts/ directory. It is not part of the primordial_soup package —
it supports the script layer only.

Current utilities:
    - create_results_dir: Create a timestamped results subdirectory.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

# All simulation output goes under this directory (gitignored).
RESULTS_ROOT = Path("results")


def create_results_dir(
    script_name: str,
    /,
    **label_parts: object,
) -> Path:
    """Create a timestamped results subdirectory and return the path.

    Builds a directory name from the script name, label parts, and a
    UTC timestamp, ensuring each run gets a unique non-colliding
    directory under results/.

    The directory is created immediately (including parents).

    Args:
        script_name: Short identifier for the script (e.g., "trajectories",
            "campaign", "fragility"). Used as the directory name prefix.
        **label_parts: Key-value pairs appended to the directory name
            for human readability (e.g., archetype="balanced", seed=42).
            Values are converted to strings. Underscore-separated.

    Returns:
        Path to the newly created directory.

    Examples:
        >>> create_results_dir("trajectories", archetype="balanced", seed=42)
        PosixPath('results/trajectories_balanced_42_20260327_143022')

        >>> create_results_dir("fragility")
        PosixPath('results/fragility_20260327_143022')
    """
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")

    # Build directory name: script_name + label values + timestamp.
    parts = [script_name]
    for value in label_parts.values():
        parts.append(str(value))
    parts.append(timestamp)

    dir_name = "_".join(parts)
    output_dir = RESULTS_ROOT / dir_name
    output_dir.mkdir(parents=True, exist_ok=True)

    return output_dir
