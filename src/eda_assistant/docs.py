"""Local search over technical documentation (procedures, specs, guides).

Documents are split into sections (by Markdown heading) and ranked with
TF-IDF. Retrieval runs locally, so documents never leave the machine; only the
few passages relevant to a question are passed to the LLM, with their source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class Passage:
    source: str
    section: str
    text: str


def split_markdown(source: str, text: str) -> list[Passage]:
    passages, section, lines = [], "Introduction", []
    for line in text.splitlines():
        match = re.match(r"^#{1,6}\s+(.*)", line)
        if match:
            if "".join(lines).strip():
                passages.append(Passage(source, section, "\n".join(lines).strip()))
            section, lines = match.group(1).strip(), []
        else:
            lines.append(line)
    if "".join(lines).strip():
        passages.append(Passage(source, section, "\n".join(lines).strip()))
    return passages


class DocumentIndex:
    def __init__(self, passages: list[Passage]):
        if not passages:
            raise ValueError("No document passages to index")
        self.passages = passages
        self._vectorizer = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True)
        self._matrix = self._vectorizer.fit_transform([f"{p.section}\n{p.text}" for p in passages])

    @classmethod
    def from_folder(cls, folder: str | Path) -> "DocumentIndex":
        passages = []
        for path in sorted(Path(folder).glob("**/*")):
            if path.suffix.lower() in {".md", ".txt"}:
                passages += split_markdown(path.name, path.read_text(encoding="utf-8"))
        return cls(passages)

    @classmethod
    def from_texts(cls, texts: dict[str, str]) -> "DocumentIndex":
        passages = []
        for name, text in texts.items():
            passages += split_markdown(name, text)
        return cls(passages)

    def search(self, query: str, top_k: int = 3) -> list[dict]:
        scores = cosine_similarity(self._vectorizer.transform([query]), self._matrix)[0]
        ranked = scores.argsort()[::-1][:top_k]
        return [
            {
                "source": self.passages[i].source,
                "section": self.passages[i].section,
                "score": round(float(scores[i]), 3),
                "text": self.passages[i].text,
            }
            for i in ranked
            if scores[i] > 0
        ]
