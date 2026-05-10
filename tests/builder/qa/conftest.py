"""QA test fixtures: CannedAgent + populated vault."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import pytest

from builder.ingest.protocols import AgentResponse
from matter_expert import (
    ConceptFrontmatter, ConceptPage, MOCFrontmatter, MOCPage,
    Source, SourceFrontmatter, SourcePage, VaultPaths,
)


@dataclass
class CannedAgent:
    recipes: dict[str, str] = field(default_factory=dict)
    default: str = "{}"
    canned_input_tokens: int = 100
    canned_output_tokens: int = 50
    calls: list[dict] = field(default_factory=list)

    def call(self, prompt, *, model="haiku", images=None) -> AgentResponse:
        self.calls.append({"prompt": prompt, "model": model})
        for needle, text in self.recipes.items():
            if needle in prompt:
                return AgentResponse(
                    text=text,
                    input_tokens=self.canned_input_tokens,
                    output_tokens=self.canned_output_tokens,
                )
        return AgentResponse(
            text=self.default,
            input_tokens=self.canned_input_tokens,
            output_tokens=self.canned_output_tokens,
        )


@pytest.fixture
def canned_agent() -> CannedAgent:
    return CannedAgent()


def _make_concept(paths: VaultPaths, name: str, title: str, body: str = "",
                  sources=None, tags=None, related=None):
    fm = ConceptFrontmatter(
        title=title,
        sources=list(sources or [Source(file=f"{name}.md", sections=[])]),
        tags=list(tags or []),
        created=date(2026, 5, 10),
        related=list(related or []),
    )
    paths.concepts.mkdir(parents=True, exist_ok=True)
    ConceptPage(
        frontmatter=fm,
        body=body or f"# {title}\n\nContent of {title}.\n",
        path=paths.concept_for(name),
    ).write()


def _make_source(paths: VaultPaths, name: str):
    paths.sources.mkdir(parents=True, exist_ok=True)
    fm = SourceFrontmatter(
        title=name,
        original_file=f"{name}.pdf",
        original_format="pdf",
        page_count=1,
        extraction_method="text",
        language_detected="en",
        ingested=date(2026, 5, 10),
    )
    SourcePage(frontmatter=fm, body=f"# {name}\n\nSource body of {name}.\n",
               path=paths.source_for(name)).write()


@pytest.fixture
def populated_vault(tmp_path: Path) -> VaultPaths:
    """A vault with 3 concepts, 2 sources, 1 MOC — used by validator tests."""
    paths = VaultPaths(root=tmp_path / "vault")
    paths.concepts.mkdir(parents=True)
    paths.mocs.mkdir()
    paths.sources.mkdir()

    _make_source(paths, "handbook")
    _make_source(paths, "security_guide")

    _make_concept(paths, "oauth2-flow", "OAuth2 Flow",
                  body="# OAuth2 Flow\n\nOAuth2 separates authn from authz.\n",
                  sources=[Source(file="handbook.md", sections=["3.1"])],
                  tags=["auth"], related=["jwt-tokens"])
    _make_concept(paths, "jwt-tokens", "JWT Tokens",
                  body="# JWT Tokens\n\nJSON Web Tokens are signed JSON.\n",
                  sources=[Source(file="security_guide.md", sections=["2.4"])],
                  tags=["auth"], related=["oauth2-flow"])
    _make_concept(paths, "encryption-fundamentals", "Encryption",
                  body="# Encryption\n\nSymmetric and asymmetric encryption.\n",
                  sources=[Source(file="security_guide.md", sections=["1.1"])],
                  tags=["crypto"])

    moc = MOCPage(
        frontmatter=MOCFrontmatter(
            title="Authentication",
            children=["oauth2-flow", "jwt-tokens"],
            parents=[],
            related_mocs=[],
            created=date(2026, 5, 10),
        ),
        body="# Authentication MOC\n\n- [[oauth2-flow]]\n- [[jwt-tokens]]\n",
        path=paths.mocs / "auth.md",
    )
    moc.write()
    return paths
