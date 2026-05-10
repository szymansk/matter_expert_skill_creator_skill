import subprocess
import sys

from pathlib import Path


def test_cli_estimate_subcommand(sample_input_dir, tmp_path):
    """`estimate` produces a cost breakdown without running the build."""
    result = subprocess.run(
        [
            sys.executable, "-m", "builder.integration.cli",
            "estimate",
            "--input", str(sample_input_dir),
        ],
        capture_output=True, text=True, check=True,
    )
    assert "Estimated costs" in result.stdout
    assert "Ingest" in result.stdout
    assert "Total" in result.stdout


def test_cli_help_lists_subcommands():
    result = subprocess.run(
        [sys.executable, "-m", "builder.integration.cli", "--help"],
        capture_output=True, text=True, check=True,
    )
    assert "estimate" in result.stdout
    assert "build" in result.stdout
