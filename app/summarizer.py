
import os
import subprocess


# Ollama model to call
MODEL = "qwen2.5vl:3b"
CMD   = ["ollama", "run", MODEL]

def summarize_image(image_path: str) -> str:
    """
    Given a local image path, call Ollama/Qwen to produce a concise
    summary of the dashboard/diagram and return that text.
    """
    # 1) Verify the image exists
    if not os.path.isfile(image_path):
        raise FileNotFoundError(f"Image not found: {image_path}")

    # 2) Build the prompt
    prompt = (
        f"[Image: {image_path}]\n"
        "You are a dashboard and flow diagram analyst. Study this dashboard or diagram carefully and "
        "provide a concise but comprehensive summary of all the information it contains."
    )

    # 3) Run Ollama CLI
    proc = subprocess.run(
        CMD + [prompt],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )

    # 4) Error handling
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="ignore")
        raise RuntimeError(f"Ollama failed:\n{err}")

    # 5) Return the summary text
    return proc.stdout.decode("utf-8", errors="ignore").strip()



