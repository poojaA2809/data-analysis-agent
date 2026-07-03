from google import genai
from google.genai import types


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-flash"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
        ) if system else None
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        # A blocked/empty candidate makes `response.text` None. Surface a clear
        # error the calling node's try/except can catch — never propagate None
        # (which would crash downstream string handling in the graph).
        text = getattr(response, "text", None)
        if text is None:
            reason = getattr(response, "prompt_feedback", None)
            raise RuntimeError(
                f"Gemini returned no text (empty or blocked response). "
                f"prompt_feedback={reason!r}"
            )
        return text
