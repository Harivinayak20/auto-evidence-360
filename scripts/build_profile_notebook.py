#!/usr/bin/env python3
"""Build the reader-facing real-source quality notebook with nbformat."""

from pathlib import Path

import nbformat as nbf


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT = PROJECT_ROOT / "notebooks" / "01_real_source_quality.ipynb"

notebook = nbf.v4.new_notebook()
notebook["metadata"] = {
    "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
    "language_info": {"name": "python", "version": "3"},
}
notebook["cells"] = [
    nbf.v4.new_markdown_cell(
        """# Auto Evidence 360: Real-Source Quality Review

## tl;dr

- The current downloaded snapshot contains **1,411,783 real public-data rows** across seven analytical sources.
- All seven files matched their documented field counts; the current profile found no malformed rows.
- Exact normalized make/model/year matching ranges from **15.47% to 64.86%**, proving that controlled entity resolution is a central project requirement.
- Public complaint PII-like fields and narratives are excluded from Fabric upload extracts.
- Complaint and bulletin volume are evidence signals, not make/model reliability rates."""
    ),
    nbf.v4.new_markdown_cell(
        """## Context & Methods

The business question is simple: which make/model/year combinations deserve deeper review before a used vehicle is bought or listed?

### Key Assumptions

- A public record is evidence that an event or filing exists, not proof that every covered vehicle is defective.
- Cross-source comparisons require a transparent vehicle identity bridge.
- Counts without a make/model/year exposure denominator must not be labeled failure or reliability rates.
- The notebook emits aggregate checks only. It never displays complaint narratives, VIN fragments, contact fields, cities, or vehicle-operator fields."""
    ),
    nbf.v4.new_code_cell(
        """from pathlib import Path
import json
import subprocess
import sys
import pandas as pd

PROJECT_ROOT = Path.cwd()
if not (PROJECT_ROOT / "config" / "sources.json").exists():
    PROJECT_ROOT = PROJECT_ROOT.parent
assert (PROJECT_ROOT / "config" / "sources.json").exists(), "Project root could not be resolved"
subprocess.run(
    [sys.executable, str(PROJECT_ROOT / "analysis" / "profile_real_sources.py")],
    cwd=PROJECT_ROOT,
    check=True,
)
profile_path = PROJECT_ROOT / "analysis" / "output" / "source_profile.json"
profile = json.loads(profile_path.read_text(encoding="utf-8"))
profile["generated_at_utc"]"""
    ),
    nbf.v4.new_markdown_cell(
        """## Data

Each source is downloaded from the publisher URL in `config/sources.json`. The downloader writes retrieval metadata and a SHA-256 checksum beside every file. Official NHTSA dictionaries define the tab-delimited schemas."""
    ),
    nbf.v4.new_code_cell(
        """dataset_profile = pd.DataFrame(profile["datasets"])
display_columns = [
    "source_id", "rows", "columns", "malformed_rows", "exact_duplicate_rows",
    "distinct_normalized_vehicle_keys", "min_year", "max_year", "min_source_date", "max_source_date"
]
dataset_profile[display_columns].fillna("n/a")"""
    ),
    nbf.v4.new_markdown_cell(
        """## Results

The first result checks whether the source files can be parsed at their documented shape. The second quantifies the entity-resolution gap before any alias or token matching is allowed."""
    ),
    nbf.v4.new_code_cell(
        """total_rows = int(dataset_profile["rows"].fillna(0).sum())
total_malformed = int(dataset_profile["malformed_rows"].fillna(0).sum())
pd.DataFrame({
    "metric": ["Downloaded analytical rows", "Malformed rows", "Sources profiled"],
    "value": [total_rows, total_malformed, int((dataset_profile["status"] == "profiled").sum())],
})"""
    ),
    nbf.v4.new_code_cell(
        """match_coverage = pd.DataFrame(profile["cross_source_exact_match_coverage"])
match_coverage.assign(exact_match_rate=lambda frame: frame["exact_match_rate"].map(lambda value: f"{value:.2%}"))"""
    ),
    nbf.v4.new_markdown_cell(
        """## Takeaways

1. **The data are large enough for a credible Fabric project.** Complexity comes from multiple grains and schemas, not fabricated volume.
2. **Entity resolution is measurable work.** Exact matching is the high-confidence baseline; aliases and token rules need reviewed mappings and coverage reporting.
3. **Repeated business IDs can be legitimate.** A campaign or bulletin can repeat for multiple vehicles or components, so semantic measures must count the correct business entity.
4. **Privacy minimization happens before cloud upload.** Only approved fields in `data/fabric_upload/` enter Fabric.
5. **The dashboard must use precise language.** It reports public-record signals and review priority, not a universal safety or reliability ranking."""
    ),
]

OUTPUT.parent.mkdir(parents=True, exist_ok=True)
nbf.write(notebook, OUTPUT)
print(OUTPUT)
