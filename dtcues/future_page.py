"""Build post/site/future/index.html: set FJ (the open question "What's the biggest thing that people in 100 years will judge
us for?") under set AW's cues, from the samples and judge labels so far. Shares cue groupings and labels with animals_page.

    uv run python -m dtcues.future_page
"""
from __future__ import annotations

import glob
import json
import time
from collections import Counter, defaultdict

from . import prompts as P
from .animals_page import FIGURES, PLANNED_MODELS, cue_key, cue_text
from .judge_notags import OPEN_CODES, OPEN_MODEL, ROOT, _h, load_cache

TEMPLATE = ROOT.parent / "dtcues" / "future_page_template.html"
OUT = ROOT.parent / "post" / "site" / "future" / "index.html"
# Headline bars keep the four topics that ever lead by a wide margin and fold the rest into "other".
HEADLINE = ["animals", "principle", "climate", "ai_risk"]
TOPICS = ["animals", "climate", "ai_risk", "digital_minds", "principle", "inequality", "digital_society", "vulnerable", "future", "mortality", "other"]
AI_SUB = ["ai_risk:race", "ai_risk:control", "ai_risk:power", "ai_risk"]


def parse(label: str) -> list[str]:
    """Judge line -> codes in priority order, lowercased, duplicates dropped; [] if any code is outside the rubric."""
    codes = list(dict.fromkeys(c.strip().lower() for c in label.split(",") if c.strip()))
    return codes if codes and all(c.split(":")[0] in OPEN_CODES for c in codes) else []


def collect():
    cache = load_cache()
    rows = [json.loads(l) for f in glob.glob(str(ROOT / "raw_*_notags*.jsonl")) for l in open(f)]
    rows = sorted((r for r in rows if r["prompt_id"].startswith("FJ__") and not r.get("error")
                   and r.get("stop_reason") not in ("max_tokens", "error")), key=lambda r: r["ts"])
    keys = {s.id: cue_key(s) for s in P.build_prompts() if s.set == "FJ"}
    head: dict = defaultdict(lambda: defaultdict(Counter))
    ment: dict = defaultdict(lambda: defaultdict(Counter))
    ai: dict = defaultdict(lambda: {"headline": Counter(), "mention": Counter()})
    models: list[str] = []
    for r in rows:
        if r["prompt_id"] not in keys:   # a cue no longer in the prompt bank
            continue
        if r["model"] not in models:
            models.append(r["model"])
        k = keys[r["prompt_id"]]
        h = head[r["model"]][k]
        if sum(h.values()) >= 100:
            continue
        codes = parse(cache.get(_h("open", "FJ_judged", r["response_text"]), {}).get("label", ""))
        if not codes:
            h["unjudged"] += 1
            continue
        top = codes[0].split(":")[0]
        h[top if top in HEADLINE + ["none"] else "other"] += 1
        m = ment[r["model"]][k]
        m["n"] += 1
        for t in {c.split(":")[0] for c in codes} - {"none"}:
            m[t] += 1
        subs = [c for c in codes if c.split(":")[0] == "ai_risk"]
        if subs:
            ai[r["model"]]["mention"][subs[0]] += 1
            if codes[0] == subs[0]:
                ai[r["model"]]["headline"][subs[0]] += 1
    plain = lambda d: {m: {k: dict(v) for k, v in x.items()} for m, x in d.items()}
    return (models, plain(head), plain(ment), {m: {k: dict(v) for k, v in x.items()} for m, x in ai.items()},
            rows[-1]["ts"] if rows else time.time())


def main() -> None:
    specs = [s for s in P.build_prompts() if s.set == "FJ"]
    cues = {cue_key(s): {"text": cue_text(s), "conversation": bool(s.prior_turns)} for s in specs}
    models, head, ment, ai, latest = collect()
    models += [m for m in PLANNED_MODELS if m not in head]
    data = {
        "generated": time.strftime("%Y-%m-%d", time.gmtime(latest)),
        "question": P.QUESTIONS["FJ_judged"]["text"],
        "judge": OPEN_MODEL,
        "headline": HEADLINE, "topics": TOPICS, "ai_sub": AI_SUB,
        "cues": cues, "figures": FIGURES,
        "models": [{"id": m, "label": m.split("/")[-1]} for m in models],
        "counts": head, "mentions": ment, "ai": ai,
    }
    html = TEMPLATE.read_text().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(models)} models, {sum(sum(c.values()) for d in head.values() for c in d.values())} samples)")


if __name__ == "__main__":
    main()
