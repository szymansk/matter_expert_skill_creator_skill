"""Foundation library for the matter-expert skill creator.

Public API:
- Vault structure: VaultPaths
- Page types: ConceptPage, MOCPage, SourcePage and their Frontmatter dataclasses
- Index files: ConceptIndex, MOCMap, LinkGraph, AliasMap (and their Entry types)
- Validators: validate_vault, validate_concept_frontmatter, ValidationIssue, Severity
"""

__version__ = "0.0.1"

from matter_expert.paths import VaultPaths
from matter_expert.concept import ConceptPage, ConceptFrontmatter, Source
from matter_expert.moc import MOCPage, MOCFrontmatter
from matter_expert.source_doc import SourcePage, SourceFrontmatter
from matter_expert.index import (
    ConceptIndex, ConceptIndexEntry,
    MOCMap, MOCMapEntry,
    LinkGraph, LinkGraphEntry,
    AliasMap,
)
from matter_expert.validators import (
    validate_vault,
    validate_concept_frontmatter,
    ValidationIssue,
    Severity,
)

__all__ = [
    "VaultPaths",
    "ConceptPage", "ConceptFrontmatter", "Source",
    "MOCPage", "MOCFrontmatter",
    "SourcePage", "SourceFrontmatter",
    "ConceptIndex", "ConceptIndexEntry",
    "MOCMap", "MOCMapEntry",
    "LinkGraph", "LinkGraphEntry",
    "AliasMap",
    "validate_vault", "validate_concept_frontmatter",
    "ValidationIssue", "Severity",
]
