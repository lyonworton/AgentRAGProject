"""Verify Xinference config fields exist with correct defaults."""

import os

import pytest

from app.core.config import Settings


def test_default_embedding_backend_is_local():
    s = Settings()
    assert s.embedding_backend == "local"


def test_default_xinference_endpoint():
    s = Settings()
    assert s.xinference_endpoint == "http://xinference:9997"


def test_default_xinference_model():
    s = Settings()
    assert s.xinference_embedding_model == "bge-m3"


def test_env_override_embedding_backend():
    os.environ["EMBEDDING_BACKEND"] = "xinference"
    try:
        s = Settings()
        assert s.embedding_backend == "xinference"
    finally:
        del os.environ["EMBEDDING_BACKEND"]
