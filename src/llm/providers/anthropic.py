import anthropic as _sdk


class AnthropicProvider:
    DEFAULT_MODEL = "claude-sonnet-4-6"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = _sdk.Anthropic(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        text, _pt, _ct = self.call_model_metered(prompt, system=system)
        return text

    def call_model_metered(
        self, prompt: str, *, system: str | None = None
    ) -> tuple[str, int, int]:
        kwargs: dict = dict(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        msg = self._client.messages.create(**kwargs)
        usage = getattr(msg, "usage", None)
        pt = getattr(usage, "input_tokens", 0) or 0 if usage else 0
        ct = getattr(usage, "output_tokens", 0) or 0 if usage else 0
        return msg.content[0].text, int(pt), int(ct)

    def stream_model(self, prompt: str, *, system: str | None = None):
        kwargs: dict = dict(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system
        with self._client.messages.stream(**kwargs) as stream:
            for text in stream.text_stream:
                if text:
                    yield text
