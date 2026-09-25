from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.ai_provider import OpenAIProvider, configured_provider_name, get_ai_provider


def _reset() -> None:
    get_ai_provider.cache_clear()


def test_openai_is_default_provider() -> None:
    _reset()
    with patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=False):
        with patch("app.services.ai_provider.OpenAI"):
            provider = get_ai_provider()
            assert provider.name == "openai"
            assert configured_provider_name() == "openai"
    _reset()


def test_unknown_provider_fails_closed() -> None:
    _reset()
    with patch.dict("os.environ", {"AI_PROVIDER": "unknown-provider"}, clear=False):
        with pytest.raises(RuntimeError, match="Unsupported AI_PROVIDER"):
            get_ai_provider()
    _reset()


def test_provider_requires_server_side_api_key() -> None:
    with patch.dict(
        "os.environ",
        {"AI_EXTERNAL_PROCESSING_ENABLED": "true", "OPENAI_API_KEY": ""},
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            OpenAIProvider()


def test_external_processing_can_be_disabled() -> None:
    with patch.dict(
        "os.environ",
        {"AI_EXTERNAL_PROCESSING_ENABLED": "false", "OPENAI_API_KEY": "test-key"},
        clear=False,
    ):
        with pytest.raises(RuntimeError, match="disabled"):
            OpenAIProvider()
