"""Embedding text with the engine LACC already talks to (ADR-061).

No new Python dependency. This project installs with seven packages, and a local embedding
stack would cost that to everyone who never asks a question of a corpus. The same host rule
applies as to generation: loopback needs no permission, anything else needs `network_access`
and an address written in the configuration.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

from local_ai_control_center.ports.embedder import Embedder, EmbeddingError

_BATCH = 64
"""Texts per round trip.

The cost is dominated by the round trip rather than by the text: the real corpus of 654
quotations embeds in 48 seconds this way against several minutes one at a time. Larger
batches stopped helping and start risking a request big enough to time out.
"""

_TIMEOUT_SECONDS = 600.0
"""Generous, because this is called once and cached (ADR-061).

A corpus embeds in under a minute warm and takes longer on a cold model that has to be
loaded first. Killing that at ninety seconds would mean a first run never succeeds.
"""


class OllamaEmbedder(Embedder):
    """Turn text into vectors using an embedding model on an Ollama host."""

    def __init__(self, model: str, host: str) -> None:
        """Embed with ``model`` on ``host``, both named by the configuration."""
        self._model = model
        self._host = host.rstrip("/")

    @property
    def name(self) -> str:
        """Identify the engine and the model, which is what a stored vector set records."""
        return f"ollama:{self._model}"

    def embed(self, texts: tuple[str, ...]) -> tuple[tuple[float, ...], ...]:
        """Return one vector per text, in order, in batches.

        Refuses a short or ragged answer rather than returning it. A caller lines vectors
        up with passages by position, so one missing vector would mis-attribute every
        passage after it - a silent, confident wrongness of exactly the kind this project
        spends its records refusing.
        """
        if not texts:
            return ()
        vectors: list[tuple[float, ...]] = []
        for start in range(0, len(texts), _BATCH):
            vectors.extend(self._batch(texts[start : start + _BATCH]))

        if len(vectors) != len(texts):
            raise EmbeddingError(
                f"{self.name} returned {len(vectors)} vectors for {len(texts)} texts. "
                "Nothing was stored: a vector set that does not line up with its passages "
                "would attribute the wrong words to the wrong document."
            )
        widths = {len(vector) for vector in vectors}
        if len(widths) > 1:
            raise EmbeddingError(
                f"{self.name} returned vectors of differing lengths ({sorted(widths)}), "
                "which cannot be compared with each other."
            )
        return tuple(vectors)

    def _batch(self, texts: tuple[str, ...]) -> list[tuple[float, ...]]:
        """One round trip, with the engine's failures translated into one exception."""
        body = json.dumps({"model": self._model, "input": list(texts)}).encode("utf-8")
        request = urllib.request.Request(
            f"{self._host}/api/embed", data=body, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
                answered = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise EmbeddingError(
                f"{self._host} refused to embed with {self._model!r} (HTTP {error.code}). "
                f"Check that the model is installed: `ollama pull {self._model}`."
            ) from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            raise EmbeddingError(f"Cannot reach {self._host} to embed: {error}") from error
        except ValueError as error:
            raise EmbeddingError(f"Unexpected answer from {self._host}: {error}") from error

        returned = answered.get("embeddings")
        if not isinstance(returned, list):
            raise EmbeddingError(
                f"{self._host} answered without embeddings. A model that generates text is "
                f"not an embedding model; {self._model!r} may be the wrong one."
            )
        return [tuple(float(value) for value in vector) for vector in returned]
