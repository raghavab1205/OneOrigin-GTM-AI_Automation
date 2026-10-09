import sys, json
from core import qa

q = sys.argv[1]
product = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
informal = "--informal" in sys.argv
print(json.dumps(qa.ask(q, product, informal), indent=2))