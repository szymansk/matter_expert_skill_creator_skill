"""Validates that the example vault fixture is structurally correct.
This is a tripwire test — if it fails, the fixture is broken."""
from matter_expert.paths import VaultPaths
from matter_expert.validators import Severity, validate_vault


def test_example_vault_has_no_errors(example_vault_paths: VaultPaths):
    issues = validate_vault(example_vault_paths)
    errors = [i for i in issues if i.severity == Severity.ERROR]
    assert errors == [], f"Example vault has errors: {errors}"


def test_example_vault_has_expected_concept_count(example_vault_paths: VaultPaths):
    concept_files = list(example_vault_paths.concepts.glob("*.md"))
    assert len(concept_files) == 7
