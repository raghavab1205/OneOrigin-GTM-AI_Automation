from core import retrieval
from core.logger import start_run, end_run

start_run("retrieval_test")
n = retrieval.build_index()
print("chunks indexed:", n)

def show(q, **kw):
    print("\nQ:", q, kw)
    hits = retrieval.search(q, k=2, **kw)
    if not hits:
        print("  (no hits within cutoff)")
    for h in hits:
        print(" ", h["cite"], h["doc_type"], h["doc_date"],
              "stale" if h["stale"] else "", "| dist", h["distance"],
              "|", h["text"][:70].replace("\n", " "))

show("auto accept confidence threshold", product="airr")
show("auto accept confidence threshold", product="airr", include_superseded=True)
show("is there a real-time API", product="airr")
show("is there a real-time API", product="airr", doc_types=retrieval.INFORMAL)
show("does it guarantee credit transfer", product="transferme")
show("what is the capital of France", product="airr")
print("\nopen discarc tickets:", retrieval.find_tickets("discarc", "open"))

end_run("ok", chunks=n)