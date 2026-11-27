"""Grid-search the commit policy on dev.jsonl. Not part of the submission agent."""
import itertools, json, sys
import evaluate, agent
from search import load_catalogue

reqs = [json.loads(l) for l in open("dev.jsonl")]
parsing_brands = {p["brand"] for p in load_catalogue() if p["brand"]}

rows = []
for quiet, cue, mintok, closer in itertools.product(
        (1, 2, 3), (3, 4, 5), (6,), (True, False)):
    agent.QUIET_WORDS = quiet
    agent.CUE_WINDOW, agent.MIN_TOKENS = cue, mintok
    agent.REQUIRE_WRAP = closer
    results, _ = evaluate.run(agent.Agent, reqs)
    s = evaluate.summarise(results)
    rows.append((s["score"], s["wrong_commits"], s["early_share"], s["searches"],
                 quiet, cue, mintok, closer))
rows.sort(reverse=True)
print("score  wrong  early%  searches | quiet cue mintok closer")
for r in rows[:20]:
    print(f"{r[0]:5.1f}  {r[1]:5d}  {r[2]:6.1%}  {r[3]:8.2f} | {r[4]} {r[5]} {r[6]} {r[7]}")
print("...")
for r in rows[-5:]:
    print(f"{r[0]:5.1f}  {r[1]:5d}  {r[2]:6.1%}  {r[3]:8.2f} | {r[4]} {r[5]} {r[6]} {r[7]}")
