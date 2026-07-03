from collections.abc import Iterator

from google import genai
from google.genai import types


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def _config(self, system: str | None):
        return types.GenerateContentConfig(system_instruction=system) if system else None

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        text, _pt, _ct = self.call_model_metered(prompt, system=system)
        return text

    def call_model_metered(
        self, prompt: str, *, system: str | None = None
    ) -> tuple[str, int, int]:
        """Return (text, prompt_tokens, completion_tokens)."""
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=self._config(system),
        )
        text = getattr(response, "text", None)
        if text is None:
            reason = getattr(response, "prompt_feedback", None)
            raise RuntimeError(
                f"Gemini returned no text (empty or blocked response). "
                f"prompt_feedback={reason!r}"
            )
        pt, ct = _usage(response)
        return text, pt, ct

    def stream_model(
        self, prompt: str, *, system: str | None = None
    ) -> Iterator[str]:
        """Yield answer text chunks live from Gemini streaming."""
        stream = self._client.models.generate_content_stream(
            model=self._model,
            contents=prompt,
            config=self._config(system),
        )
        for chunk in stream:
            piece = getattr(chunk, "text", None)
            if piece:
                yield piece


def _usage(response) -> tuple[int, int]:
    meta = getattr(response, "usage_metadata", None)
    if meta is None:
        return 0, 0
    pt = getattr(meta, "prompt_token_count", None) or 0
    ct = getattr(meta, "candidates_token_count", None) or 0
    return int(pt), int(ct)
