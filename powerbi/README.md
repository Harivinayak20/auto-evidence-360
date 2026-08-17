# Power BI Build Assets

## Theme

Import `auto-evidence-360-theme.json` from **View > Themes > Browse for themes**.

Priority formatting is deliberately separate from the normal chart palette:

| Priority | Color | Hex |
|---|---|---|
| Critical | Dark red | `#B42318` |
| High | Amber | `#D97706` |
| Review | Blue | `#1E5AA8` |
| Monitor | Slate | `#64748B` |

Always pair priority color with its text label. Do not communicate urgency by color alone.

## First-page hierarchy

1. Hero cards: Critical, High, total review queue, data-quality status.
2. Trend: selected evidence signal over its correctly labeled source date.
3. Diagnosis: priority reason and evidence topic.
4. Detail: make/model/year review queue with drill-through.

Use `measures.dax` for explicit measures and `docs/POWER_BI_BLUEPRINT.md` for relationships and page specifications.
