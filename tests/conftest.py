"""Shared pytest fixtures."""
import pytest


@pytest.fixture
def sample_input_csv(tmp_path):
    p = tmp_path / "input.csv"
    p.write_text("Nama Perusahaan\nPT Maju Jaya\nPT Sentosa\n")
    return p