from __future__ import annotations

_CAPTCHA_SIGNALS = [
    "recaptcha",
    "hcaptcha",
    "cf-challenge",
    "cf_chl_opt",
    "challenge-running",
    "distil_identify",
    "px-captcha",
    "__ddg",
    "datadome",
    "arkoselabs",
]


def is_captcha_page(html: str) -> bool:
    lower = html.lower()
    return any(sig in lower for sig in _CAPTCHA_SIGNALS)
