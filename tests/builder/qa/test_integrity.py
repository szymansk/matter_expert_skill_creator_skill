from builder.qa.integrity import VaultIntegrityValidator
from builder.qa.report import Severity


def test_passes_for_well_formed_vault(populated_vault):
    v = VaultIntegrityValidator()
    result = v.validate(vault=populated_vault)
    assert result.severity == Severity.PASS


def test_fails_for_missing_required_directory(populated_vault):
    # Delete the MOCs directory.
    import shutil
    shutil.rmtree(populated_vault.mocs)

    v = VaultIntegrityValidator()
    result = v.validate(vault=populated_vault)
    assert result.severity == Severity.FAIL
