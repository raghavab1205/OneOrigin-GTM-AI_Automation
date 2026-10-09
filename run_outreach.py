import sys, json
from core import outreach

FILES = {"uga": "outputs/university_of_georgia_research.json",
         "oregon": "outputs/university_of_oregon_research.json"}

key = sys.argv[1] if len(sys.argv) > 1 else "uga"
data = json.load(open(FILES[key], encoding="utf-8"))
contacts = data["record"]["contacts"]

if len(sys.argv) < 3:
    for i, c in enumerate(contacts):
        print(i, "|", c["name"], "|", c["title"], "|", outreach.pick_persona(c["title"]))
    print("\nUsage: python run_outreach.py <uga|oregon> <contact number> [registrar|enrollment]")
    sys.exit()

persona = sys.argv[3] if len(sys.argv) > 3 else None
out = outreach.generate(data, contacts[int(sys.argv[2])]["name"], persona)
print(out["status"], out["problems"])
print("Saved:", out["markdown_path"])