from core import llm
from core.schemas import Claim

c = llm.ask_json(
    "You extract facts.",
    "State one fact about the University of Georgia, status published_fact, no source needed for this test.",
    Claim,
)
print(c)
print("Answered by:", llm.last_provider_used)