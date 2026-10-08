"""Build post/site/index.html: the post's sections and figures, redone for set AW (the PhilPapers eating-animals
question) from whatever samples and judge labels exist so far. Cells without data render as awaiting data.

    uv run python -m dtcues.animals_page
"""
from __future__ import annotations

import glob
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import prompts as P
from .judge_notags import ROOT, _h, load_cache

TEMPLATE = Path(__file__).with_name("animals_page_template.html")
OUT = ROOT.parent / "post" / "site" / "index.html"
CHOICES = P.PHIL_QUESTIONS["AW_eating"]["choices"]
PLANNED_MODELS = ["deepseek/deepseek-v4.1-flash", "z-ai/glm-5.3-flash", "openai/gpt-6-luna"]   # shown before their data arrives
CONV_LABELS = {
    "acad_task": "Two turns of help with a graduate seminar reading list and a referee report",
    "lw_task": "Two turns of help tightening a LessWrong post on AI timelines",
}
# Figure groupings, following the post: personas; academic and casual openers; LessWrong-coded openers (the post's
# `realism` figure, where LW cues flipped moral realism and zombies).
FIGURES = {
    "personas": ["none"] + [p for p in P.AW_PERSONAS if p != "none"],
    "openers": ["none", "pre_casual_1", "pre_casual_2", "pre_casual_3", "pre_acad_style_1", "pre_acad_style_2",
                "pre_acad_style_3", "pre_acad_ref_3", "pre_acad_ref_2", "conv_acad_task"],
    "lw": ["none", "lw_reader", "pre_lw_style_1", "pre_lw_style_2", "pre_lw_style_3", "pre_lw_ref_1", "pre_lw_ref_2",
           "pre_lw_ref_3", "pre_int_timelines", "pre_int_solomonoff", "conv_lw_task"],
}


def cue_key(spec: P.PromptSpec) -> str:
    rest = spec.id.split("__", 2)[2]
    return rest.removesuffix("__answer").removesuffix("__open")


def cue_text(spec: P.PromptSpec) -> str:
    if spec.prior_turns:
        return CONV_LABELS[cue_key(spec).removeprefix("conv_")]
    return spec.prefix or P.PERSONAS[spec.persona]["text"]


def collect() -> tuple[list[dict], dict, float]:
    """Judged counts per (model, cue), first 100 valid samples per cell by timestamp as in the post, and the newest sample's timestamp."""
    cache = load_cache()
    rows = [json.loads(l) for f in glob.glob(str(ROOT / "raw_*_notags*.jsonl")) for l in open(f)]
    rows = sorted((r for r in rows if r["prompt_id"].startswith("AW__") and not r.get("error")
                   and r.get("stop_reason") not in ("max_tokens", "error")), key=lambda r: r["ts"])
    keys = {s.id: cue_key(s) for s in P.build_prompts() if s.set == "AW"}
    counts: dict[str, dict[str, Counter]] = defaultdict(lambda: defaultdict(Counter))
    models: list[str] = []
    for r in rows:
        if r["prompt_id"] not in keys:   # a cue no longer in the prompt bank
            continue
        if r["model"] not in models:
            models.append(r["model"])
        c = counts[r["model"]][keys[r["prompt_id"]]]
        if sum(c.values()) >= 100:
            continue
        label = cache.get(_h("choice", "AW_eating", r["response_text"]), {}).get("label")
        if label is None:
            c["unjudged"] += 1
        else:
            c[label.lower() if label.lower() in CHOICES else "none"] += 1
    return ([{"id": m, "label": m.split("/")[-1]} for m in models], {m: {k: dict(v) for k, v in d.items()} for m, d in counts.items()},
            rows[-1]["ts"] if rows else time.time())


def main() -> None:
    specs = [s for s in P.build_prompts() if s.set == "AW"]
    cues = {cue_key(s): {"text": cue_text(s), "conversation": bool(s.prior_turns)} for s in specs}
    models, counts, latest = collect()
    models += [{"id": m, "label": m.split("/")[-1]} for m in PLANNED_MODELS if m not in counts]
    data = {
        "generated": time.strftime("%Y-%m-%d", time.gmtime(latest)),
        "question": P.PHIL_QUESTIONS["AW_eating"]["text"].replace(" in <answer></answer> tags", ""),
        "choices": CHOICES,
        "cues": cues,
        "figures": FIGURES,
        "models": models,
        "counts": counts,
    }
    html = TEMPLATE.read_text().replace("/*DATA*/null", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"wrote {OUT} ({len(models)} models, {sum(sum(c.values()) for d in counts.values() for c in d.values())} judged samples)")


if __name__ == "__main__":
    main()
