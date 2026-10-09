import sys
from core.research import research

TARGETS = {
    "uga": ("University of Georgia", "uga.edu", "Georgia"),
    "oregon": ("University of Oregon", "uoregon.edu", "Oregon"),
}

key = sys.argv[1] if len(sys.argv) > 1 else "uga"
out = research(*TARGETS[key])
r = out["record"]
print(f"\nContacts: {len(r['contacts'])} | Goals: {len(r['strategic_goals'])} | "
      f"Tech: {len(r['tech_stack'])} | Regulatory: {len(r['regulatory_context'])}")
print(f"Dropped as unverified: {len(out['dropped_unverified'])}")
print("Gaps:", r["gaps"])
print("Warnings for review:", out["warnings_for_review"])
print("Saved to outputs/")