"""Verify Xinference config fields exist with correct defaults."""

import os

import pytest

from app.core.config import Settings


def test_default_xinference_endpoint():
    s = Settings()
    assert s.xinference_endpoint == "http://xinference:9997"


def test_default_xinference_model():
    s = Settings()
    assert s.xinference_embedding_model == "bge-m3"


def test_env_override_xinference_endpoint():
    os.environ["XINFERENCE_ENDPOINT"] = "http://custom:9997"
    try:
        s = Settings()
        assert s.xinference_endpoint == "http://custom:9997"
    finally:
        del os.environ["XINFERENCE_ENDPOINT"]
