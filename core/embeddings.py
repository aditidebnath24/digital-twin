"""
Lightweight hashed n-gram embedder + pure-NumPy cosine store.

No FAISS required — runs offline with numpy only.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


def _tokenize_hash_vector(text: str, dim: int = 384) -> np.ndarray:
    text = text.lower()

    tokens = re.findall(r"[a-z0-9.\-_]+", text)

    vec = np.zeros(dim, dtype=np.float32)

    for t in tokens:
        for n in (2, 3, 4):
            for i in range(max(0, len(t) - n + 1)):
                gram = t[i : i + n]
                h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
                vec[h % dim] += 1.0

        h = int(hashlib.md5(t.encode()).hexdigest(), 16)
        vec[h % dim] += 1.5

    for i in range(len(tokens) - 1):
        bigram = tokens[i] + "_" + tokens[i + 1]
        h = int(hashlib.md5(bigram.encode()).hexdigest(), 16)
        vec[h % dim] += 1.2

    norm = np.linalg.norm(vec)

    if norm > 0:
        vec /= norm

    return vec


class SimpleEmbedder:
    def __init__(self, dim: int = 384):
        self.dim = dim

    def embed(self, texts: List[str]) -> np.ndarray:
        return np.vstack(
            [_tokenize_hash_vector(t, self.dim) for t in texts]
        )

    def embed_query(self, text: str) -> np.ndarray:
        return _tokenize_hash_vector(text, self.dim)


class EquationStore:
    def __init__(self, name: str, embedder: SimpleEmbedder):
        self.name = name
        self.embedder = embedder
        self.equations: List[Dict[str, Any]] = []
        self.vectors: Optional[np.ndarray] = None

    def add_equations(self, equations: List[Dict[str, Any]]):
        self.equations = equations

        texts = []

        for eq in equations:
            parts = [
                eq.get("title", ""),
                eq.get("description", ""),
                " ".join(eq.get("tags", [])),
                " ".join(eq.get("species", [])),
                eq.get("domain", ""),
                eq.get("delhi_notes", ""),
                eq.get("scale", ""),
                eq.get("temporal", ""),
            ]

            texts.append(" ".join(parts))

        self.vectors = self.embedder.embed(texts)

    def search(
        self,
        query: str,
        top_k: int = 3,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[Dict[str, Any], float]]:

        assert self.vectors is not None

        qv = self.embedder.embed_query(query)

        # Cosine similarity
        scores = self.vectors @ qv

        q_lower = query.lower()

        # ---------------------------------------------------------
        # Scenario-aware retrieval boosts
        # ---------------------------------------------------------

        scenario_words = [
            "scenario",
            "what if",
            "change",
            "increase",
            "decrease",
            "reduce",
            "cut",
            "impact",
        ]

        if any(word in q_lower for word in scenario_words):

            for i, eq in enumerate(self.equations):

                eq_id = eq.get("id")

                # Traffic scenario
                if (
                    "traffic" in q_lower
                    and eq_id == "sim_traffic_source_coupling_01"
                ):
                    scores[i] += 0.12

                # Stubble-burning scenario
                if (
                    any(
                        word in q_lower
                        for word in [
                            "stubble",
                            "burning",
                            "biomass",
                            "parali",
                        ]
                    )
                    and eq_id == "sim_stubble_source_coupling_01"
                ):
                    scores[i] += 0.12

                # Combined traffic + stubble scenario
                if (
                    "traffic" in q_lower
                    and any(
                        word in q_lower
                        for word in [
                            "stubble",
                            "burning",
                            "biomass",
                            "parali",
                        ]
                    )
                    and eq_id == "sim_total_source_aggregation_01"
                ):
                    scores[i] += 0.10

                # Control vs scenario comparison
                if eq_id == "sim_scenario_delta_01":
                    scores[i] += 0.18

        # ---------------------------------------------------------
        # Ranking + filtering
        # ---------------------------------------------------------

        ranked: List[Tuple[int, float]] = []

        for i, score in enumerate(scores.tolist()):

            eq = self.equations[i]

            if filters:

                species = filters.get("species")

                if species:
                    if not any(
                        s in eq.get("species", [])
                        for s in species
                    ):
                        continue

                scale = filters.get("scale")

                if scale and scale not in str(
                    eq.get("scale", "")
                ):
                    # Soft filter: keep the result.
                    pass

            ranked.append((i, float(score)))

        ranked.sort(
            key=lambda x: x[1],
            reverse=True,
        )

        out: List[Tuple[Dict[str, Any], float]] = []

        for i, score in ranked[:top_k]:
            out.append(
                (
                    self.equations[i],
                    score,
                )
            )

        return out


def build_dual_stores(
    simulation_eqs: List[Dict[str, Any]],
    prediction_eqs: List[Dict[str, Any]],
) -> Tuple[EquationStore, EquationStore]:

    embedder = SimpleEmbedder()

    sim = EquationStore(
        "simulation",
        embedder,
    )

    pred = EquationStore(
        "prediction",
        embedder,
    )

    sim.add_equations(simulation_eqs)
    pred.add_equations(prediction_eqs)

    return sim, pred