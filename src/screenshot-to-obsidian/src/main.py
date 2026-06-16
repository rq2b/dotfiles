import os
import base64
import mimetypes
import sys
import requests
from pathlib import Path


def load_env(path):
    if not Path(path).exists():
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


load_env(str(Path.home()) / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    raise RuntimeError("GEMINI_API_KEY not found in environment or .env file")

if len(sys.argv) < 2:
    raise SystemExit("Usage: python ocr.py /path/to/image.png")

image_path = sys.argv[1]
mime_type, _ = mimetypes.guess_type(image_path)
if mime_type is None:
    # default guess
    mime_type = "image/png"

with open(image_path, "rb") as f:
    b64 = base64.b64encode(f.read()).decode("utf-8")

url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"
headers = {"Content-Type": "application/json", "X-goog-api-key": API_KEY}

data = {
    "contents": [
        {
            "parts": [
                {
                    "text": (
                        """
                        You are an OCR + math transcription engine.

                        Task:
                        - Extract ALL visible text from the image EXACTLY as written.
                        - Preserve the original reading order and line breaks as closely as possible.
                        - Do NOT summarize, explain, correct, or rephrase anything.

                        Math / formulas:
                        - If something is a mathematical expression (equations, fractions, integrals, limits, roots, exponents, matrices, chemical-like notation, etc.), output it as LaTeX wrapped exactly like this on its own line:
                        ## $<LATEX HERE>$
                        - Keep math out of normal lines whenever it’s clearly standalone math.
                        - If a line mixes normal words + a small inline expression, keep the words as text and put ONLY the math part as inline LaTeX: $...$

                        Code:
                        - If the OCR contents are code - put them into code blocks, and specify the language for a codeblock (```python ...)

                        Markdown:
                        - Reproduce visible structure:
                          - Headings if the image clearly shows a title (use # or ##)
                          - Bullet/numbered lists if present
                          - Bold/italics ONLY if the image shows emphasis (e.g., bold text, underlines, italics). Do not invent emphasis.

                        Output rules:
                        - Output ONLY the transcription in Markdown for Obsidian.
                        - No extra commentary.
                        - If any part is unreadable, write: [illegible]

                        """
                    )
                },
                {"inline_data": {"mime_type": mime_type, "data": b64}},
            ]
        }
    ]
}

r = requests.post(url, headers=headers, json=data, timeout=60)
j = r.json()

if "error" in j:
    raise SystemExit(f"Error {j['error'].get('code')}: {j['error'].get('message')}")

print(j["candidates"][0]["content"]["parts"][0]["text"])
