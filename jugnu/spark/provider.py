from __future__ import annotations

from typing import Any

from jugnu.observability.cost_ledger import CostLedger
from jugnu.observability.trace import EventKind, emit


class LLMProvider:
    """Thin wrapper around litellm. Only imported by jugnu/spark/.

    Every call is logged to the trace stream and (if attached) the cost ledger.
    """

    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20241022",
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout: int = 60,
        max_retries: int = 2,
        extra_params: dict | None = None,
        cost_ledger: CostLedger | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._max_retries = max_retries
        self._extra = extra_params or {}
        self._ledger = cost_ledger

    def attach_ledger(self, ledger: CostLedger | None) -> None:
        self._ledger = ledger

    async def complete(self, messages: list[dict], **kwargs: Any) -> dict:
        """Call litellm and return the response dict. Never raises — returns error dict."""
        stage = str(kwargs.pop("stage", "")) or "unspecified"
        url = str(kwargs.pop("url", "") or "")
        skill = str(kwargs.pop("skill", "") or "")
        try:
            import litellm  # noqa: PLC0415

            params = {
                "model": self._model,
                "messages": messages,
                "temperature": self._temperature,
                "max_tokens": self._max_tokens,
                "timeout": self._timeout,
                **self._extra,
                **kwargs,
            }
            response = await litellm.acompletion(**params)
            content = response.choices[0].message.content or ""
            cost = 0.0
            try:
                cost = litellm.completion_cost(completion_response=response)
            except Exception:  # noqa: BLE001
                pass

            in_tokens = 0
            out_tokens = 0
            try:
                usage = getattr(response, "usage", None)
                if usage is not None:
                    in_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                    out_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            except Exception:  # noqa: BLE001
                pass

            emit(
                EventKind.LLM_CALLED,
                url=url,
                skill=skill,
                stage=stage,
                model=self._model,
                cost_usd=float(cost or 0.0),
                input_tokens=in_tokens,
                output_tokens=out_tokens,
            )
            if self._ledger is not None:
                self._ledger.record(
                    stage=stage,
                    cost_usd=float(cost or 0.0),
                    url=url,
                    skill=skill,
                    model=self._model,
                    input_tokens=in_tokens,
                    output_tokens=out_tokens,
                )
            return {"content": content, "cost_usd": cost, "error": None}
        except Exception as exc:  # noqa: BLE001
            emit(
                EventKind.LLM_CALLED,
                url=url,
                skill=skill,
                stage=stage,
                model=self._model,
                error=str(exc),
            )
            return {"content": "", "cost_usd": 0.0, "error": str(exc)}

    @classmethod
    def from_settings(cls, settings: object) -> LLMProvider:
        return cls(
            model=getattr(settings, "model", "claude-3-5-sonnet-20241022"),
            temperature=getattr(settings, "temperature", 0.0),
            max_tokens=getattr(settings, "max_tokens", 4096),
            timeout=getattr(settings, "timeout_seconds", 60),
            max_retries=getattr(settings, "max_retries", 2),
            extra_params=getattr(settings, "extra_params", {}),
        )
