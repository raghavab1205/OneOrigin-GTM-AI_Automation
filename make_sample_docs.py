import pathlib, json

D = pathlib.Path("data/internal_docs")
D.mkdir(parents=True, exist_ok=True)

DOCS = {
"airr_overview.md": """---
doc_id: airr-overview
title: AIRR product overview
doc_type: product_doc
product: airr
doc_date: 2026-06-01
status: current
---
# What AIRR does
AIRR reads transcripts in PDF, image, EDI and PESC formats and extracts every course, grade and credit into structured data.

# Policy checking and exceptions
AIRR checks extracted data against the institution's own transfer policies. Matches it is confident about are accepted. Exceptions go to a human reviewer with a full audit trail.

# What AIRR does not do
AIRR does not make final decisions on exceptions. A human reviewer always resolves them. [SAMPLE DOC invented for the exercise]
""",
"airr_config_2024.md": """---
doc_id: airr-config-2024
title: AIRR configuration notes 2024
doc_type: config
product: airr
doc_date: 2024-03-10
status: superseded
---
# Auto-accept setting
In 2024, AIRR auto-accepted matches at a fixed confidence of 0.90 for all institutions. [SAMPLE DOC invented for the exercise; superseded]
""",
"airr_config_2026.md": """---
doc_id: airr-config-2026
title: AIRR configuration 2026
doc_type: config
product: airr
doc_date: 2026-05-15
status: current
---
# Auto-accept setting
The auto-accept confidence threshold is configurable per institution. Each institution sets its own policy rules. [SAMPLE DOC invented for the exercise]
""",
"transferme_overview.md": """---
doc_id: transferme-overview
title: TransferMe product overview
doc_type: product_doc
product: transferme
doc_date: 2026-06-01
status: current
---
# What TransferMe does
TransferMe is a student-facing portal. A prospective transfer student uploads an unofficial transcript and immediately sees what is likely to carry over, before applying.

# Lead capture
Every upload becomes a qualified enrollment lead for the institution.

# Limits
The result is an estimate of likely credit transfer, not a guarantee. Final decisions rest with the institution. [SAMPLE DOC invented for the exercise]
""",
"discarc_overview.md": """---
doc_id: discarc-overview
title: DiscArc product overview
doc_type: product_doc
product: discarc
doc_date: 2026-06-01
status: current
---
# What DiscArc does
DiscArc takes a validated transcript and suggests course equivalencies ranked by confidence. It accounts for course catalogs that change over time.

# Human confirmation
Every suggestion goes to a reviewer to confirm. Confirmations accumulate into an auditable institutional memory.

# Limits
DiscArc never applies an equivalency without reviewer confirmation. [SAMPLE DOC invented for the exercise]
""",
"integrations.md": """---
doc_id: integrations
title: Integration notes
doc_type: product_doc
product: all
doc_date: 2026-04-20
status: current
---
# Student information systems
Integration with Banner and PeopleSoft is supported through standard export and import. Other systems are handled case by case. [SAMPLE DOC invented for the exercise]
""",
"call_2026_07.md": """---
doc_id: call-2026-07
title: Internal product sync call notes
doc_type: meeting_transcript
product: airr
doc_date: 2026-07-14
status: current
---
Rep: A prospect asked whether AIRR has a real-time API.
Product lead: Not yet. It is on the roadmap for next year but nothing is committed.
Rep: So I should not promise it.
Product lead: Correct. Do not promise it to anyone.
Rep: What about scanned transcripts?
Product lead: Image input is supported today.
Rep: Good. I will say that.
Product lead: Yes, and mention exceptions still go to a reviewer.
[SAMPLE DOC invented for the exercise]
""",
"email_pesc_2026_08.md": """---
doc_id: email-pesc-2026-08
title: Email thread about PESC files
doc_type: email_thread
product: airr
doc_date: 2026-08-02
status: current
---
Subject: Question about PESC support
From: Prospect registrar
Date: 2026-08-01
Do you accept PESC XML transcripts directly?
From: OneOrigin support
Date: 2026-08-02
Yes, PESC is one of the supported formats. Custom variants may need a quick check by our team.
[SAMPLE DOC invented for the exercise]
""",
}
for name, text in DOCS.items():
    (D / name).write_text(text, encoding="utf-8")

TICKETS = [
 {"ticket_id": "T-101", "product": "airr", "status": "closed", "opened": "2026-02-11",
  "summary": "PESC file failed to parse", "resolution": "Fixed in parser update"},
 {"ticket_id": "T-102", "product": "discarc", "status": "open", "opened": "2026-08-30",
  "summary": "Catalog year mismatch on equivalency suggestion", "resolution": ""},
]
(D / "tickets.json").write_text(json.dumps(TICKETS, indent=2), encoding="utf-8")
print("Sample docs created")