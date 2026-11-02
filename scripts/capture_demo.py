"""Record real answers from the running API into demo/, for the static GitHub Pages replay.

Run after `make up && make ingest-sample`. Nothing in demo/data.json is written by hand.
"""

import io
import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import httpx
from PIL import Image

from insight.config import Settings

DEMO_DIR = Path(__file__).parent.parent / "demo"
SLIDE_MAX_SIDE = 1000

QUESTIONS = [
    ("Chart", "What was revenue in Q2 2026?"),
    ("Table", "What was the gross margin for accessories?"),
    ("Picture of a chart", "What share of customers are in the East region?"),
    ("Diagram", "Which component connects the Order API to the Tulsa factory?"),
    ("Speaker notes", "When does the Tulsa factory start full production?"),
    ("Multiple slides", "How does Q3 revenue compare with the Q4 guidance?"),
    ("Unanswerable", "Who is the CEO of Northwind Kites?"),
]


def _hardware() -> str:
    chip = subprocess.run(
        ["sysctl", "-n", "machdep.cpu.brand_string"], capture_output=True, text=True
    ).stdout.strip()
    return chip or platform.machine()


def _save_slide(api: httpx.Client, slide_id: str, name: str) -> None:
    image = Image.open(io.BytesIO(api.get(f"/slides/{slide_id}/image").raise_for_status().content))
    image = image.convert("RGB")
    image.thumbnail((SLIDE_MAX_SIDE, SLIDE_MAX_SIDE))
    image.save(DEMO_DIR / "slides" / name, format="JPEG", quality=85)


def main() -> None:
    settings = Settings()
    api = httpx.Client(base_url=settings.api_url, timeout=settings.llm_timeout_seconds + 30)
    (DEMO_DIR / "slides").mkdir(parents=True, exist_ok=True)

    recorded = []
    model = ""
    for category, question in QUESTIONS:
        response = api.post("/query", json={"question": question, "pipeline": "A"})
        result = response.raise_for_status().json()
        model = result["model"]
        retrieved = []
        for slide in result["retrieved"]:
            name = f"{slide['slide_no']}.jpg"
            _save_slide(api, slide["slide_id"], name)
            retrieved.append(
                {
                    "slide_no": slide["slide_no"],
                    "title": slide["title"],
                    "score": round(slide["score"], 3),
                    "image": f"slides/{name}",
                }
            )
        recorded.append(
            {
                "category": category,
                "question": question,
                "answer": result["answer"],
                "abstained": result["abstained"],
                "cited_slides": [c["slide_no"] for c in result["citations"]],
                "retrieved": retrieved,
                "timings_ms": {k: round(v) for k, v in result["timings_ms"].items()},
            }
        )
        print(f"{category}: {result['answer']}")

    sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout
    data = {
        "recorded_on": datetime.now(UTC).date().isoformat(),
        "git_sha": sha.strip(),
        "model": model,
        "pipeline": "A",
        "top_k": settings.default_top_k,
        "context_format": "both",
        "hardware": _hardware(),
        "questions": recorded,
    }
    (DEMO_DIR / "data.json").write_text(json.dumps(data, indent=2) + "\n")


if __name__ == "__main__":
    main()
