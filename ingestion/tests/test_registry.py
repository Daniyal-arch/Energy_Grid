"""Framework smoke tests: registration, lookup, credential gating."""

import ingestion.sources  # noqa: F401 — trigger registration
import pytest
from ingestion.base import MissingCredentialsError
from ingestion.registry import get_source, list_sources


def test_phase1_sources_registered():
    names = {cls.meta.name for cls in list_sources()}
    assert {"brightsky", "gee", "mastr"} <= names


def test_unknown_source_raises_with_available_list():
    with pytest.raises(KeyError, match="brightsky"):
        get_source("nope")


def test_credential_gating(monkeypatch):
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_EMAIL", raising=False)
    monkeypatch.delenv("GEE_SERVICE_ACCOUNT_KEY_FILE", raising=False)
    gee = get_source("gee")
    with pytest.raises(MissingCredentialsError, match="GEE_SERVICE_ACCOUNT_EMAIL"):
        gee.check_credentials()


def test_keyless_source_passes_credential_check():
    get_source("brightsky").check_credentials()
