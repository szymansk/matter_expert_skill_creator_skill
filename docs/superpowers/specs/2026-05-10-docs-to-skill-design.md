# docs-to-skill — Design Document

**Status:** Draft v1
**Datum:** 2026-05-10
**Autor:** Marc Szymanski (mit Claude Opus 4.7)

---

## 1. Zweck

Ein Skill, der aus heterogenen Quelldokumenten einen verlinkten Obsidian-Vault aufbaut und daraus einen eigenständigen, installierbaren **Experten-Skill** erzeugt. Der erzeugte Skill beantwortet Fragen mit Quellenangabe und unterstützt hypothesengetriebenes Brainstorming auf Basis des im Vault dokumentierten Wissens.

## 2. Kernanforderungen

| ID | Anforderung |
|----|-------------|
| R1 | Input ist ein Verzeichnis mit gemischten Formaten (Markdown, PDF, DOCX, HTML, TXT) plus optionale URL-Liste |
| R2 | Vault-Größe: bis ca. ein Fachbuch + Begleitdokumente (~500 Seiten) pro Build |
| R3 | Output ist ein eigenständiges Plugin mit Vault, Index und SKILL.md, im Plugin gebündelt |
| R4 | Vault ist menschenlesbar in Obsidian, nutzt typisierte Verlinkung und MOCs |
| R5 | Nach Import ist der Vault immutable — Memory ist mutable und liegt außerhalb des Vaults |
| R6 | Alle Inhalte werden beim Import auf Englisch übersetzt |
| R7 | Antworten erfolgen in der Sprache des Nutzers, mit klar markiertem Vault- vs. Weltwissen |
| R8 | Jede Aussage ist über Source-Attribution auf eine konkrete Stelle im Quellmaterial zurückführbar |
| R9 | Pipeline ist resumable — Phasen-Failures verlieren keinen Fortschritt |
| R10 | Pipeline kommuniziert geschätzte Kosten vor Start, tatsächliche Kosten nach jeder Phase |
| R11 | Modell und Effort-Level sind pro Pipeline-Phase konfigurierbar |
| R12 | Qualität priorisiert über Geschwindigkeit — "einmal richtig statt dreimal billig" |

## 3. Architektur-Überblick

Das System besteht aus zwei eigenständigen Produkten:

- **`docs-to-skill`** (Builder-Skill): orchestriert die Import-Pipeline, generiert das Output-Plugin
- **Experten-Skill** (generiertes Plugin): beantwortet Fragen und unterstützt Brainstorming

```
┌────────────────────────────────────────────────────────────────────┐
│  BUILDER (docs-to-skill)                                            │
│                                                                    │
│  Input → [Ingest] → [Transform] → [Link] → [QA] → [Emit] → Plugin │
│           Haiku     Haiku          Sonnet  Mixed   Sonnet         │
│           low       medium         high    var.    high           │
│         (+Sonnet                                                  │
│          für Vision-                                              │
│          Fallback)                                                │
└────────────────────────────────────────────────────────────────────┘
                                                          │
                                                          ▼
┌────────────────────────────────────────────────────────────────────┐
│  EXPERTEN-SKILL (Plugin)                                            │
│                                                                    │
│  Frage → [vault_locate] → [vault_search] → [vault_traverse]       │
│          (lokal, gratis)   (ripgrep)        (graph-walk)          │
│                              │                                      │
│                              ▼                                      │
│                          Synthese (Q&A oder Hypothesen)            │
│                          → Antwort mit Citations                    │
│                          → memory_update                           │
└────────────────────────────────────────────────────────────────────┘
```

## 4. Builder-Pipeline

### 4.1 Phasen im Überblick

| Phase | Modell | Effort | Hauptaufgabe |
|-------|--------|--------|--------------|
| Ingest | Haiku | low | Konvertierung CLI-Tools, Plausibilitätscheck |
| Ingest (Vision-Fallback) | Sonnet | medium | PDF-Seiten/Bilder via Vision |
| Transform | Haiku | medium | Übersetzung + konzept-basiertes Chunking |
| Link | Sonnet | high | Konzept-Deduplizierung + typisierte Verlinkung |
| QA (Validatoren-Mix) | Mixed | variable | 6 Validatoren, größtenteils lokal/Haiku |
| Emit | Sonnet | high | Plugin-Generierung, Index- & Memory-Bau |

### 4.2 Phase 1 — Ingest

**Aufgabe:** Quelldateien in Roh-Markdown konvertieren.

**Tools:**
- `pandoc` für DOCX, HTML, RTF
- `pdftotext` (Poppler) für PDFs (primär)
- `marker` als Alternative für Layout-komplexe PDFs
- `WebFetch` (Claude-Code-Tool) oder eigener Fetch-Helper für URLs

**Plausibilitätsprüfung PDF:**
Heuristik zur Erkennung erfolgreicher Text-Extraktion:
```
extracted_chars / page_count > MIN_CHARS_PER_PAGE?
  ja → Text-Extraktion akzeptieren
  nein → Vision-Fallback aktivieren
```
**Default-Schwelle:** `MIN_CHARS_PER_PAGE = 200` (entspricht ca. 30 Wörtern/Seite — unterhalb dieser Marke ist die PDF wahrscheinlich primär grafisch). Konfigurierbar pro Run via CLI-Flag.

**Vision-Fallback:**
- PDF wird seitenweise als Bild gerendert (`pdftoppm`)
- Sonnet erhält Bild und extrahiert Text + Beschreibung von Diagrammen/Grafiken
- Bilder/Grafiken werden grundsätzlich per Vision verarbeitet (nicht nur bei Fallback)

**URL-Handling:**
- URLs werden via `WebFetch` geholt, in Markdown konvertiert (über Reader-Mode-Heuristik)
- Cache pro Run unter `phase_1_ingest/url_cache/`
- Fehlschläge werden geloggt, kein Pipeline-Abbruch
- Auth-erforderliche URLs werden mit Hinweis übersprungen

**Output pro Item:** `phase_1_ingest/<doc_id>.md` plus `<doc_id>.meta.json`:

```json
{
  "source_path": "/inputs/handbuch.pdf",
  "source_type": "pdf",
  "extraction_method": "text" | "vision_fallback" | "hybrid",
  "page_count": 240,
  "extracted_chars": 187000,
  "extracted_images_count": 23,
  "outline": ["1. Intro", "1.1 Grundlagen", ...],
  "language_detected": "de"
}
```

### 4.3 Phase 2 — Transform

**Aufgabe:** Roh-Markdown übersetzen und in konzept-basierte Vault-Seiten zerlegen.

**Drei Schritte pro Quelldokument:**

1. **Konzept-Analyse** (Haiku, low) — erzeugt JSON-Inhaltsverzeichnis der identifizierten Konzepte
2. **Konzept-Extraktion** (Haiku, medium) — pro Konzept eine Vault-Seite mit Frontmatter, übersetztem Inhalt, Quellenangabe
3. **Coverage-Check** (Haiku, low) — Vergleich Original-Outline vs. extrahierte Konzepte, Nachholung fehlender Bereiche

**Chunk-Größen:**
- Ziel: 500–2000 Tokens pro Konzept-Seite
- Zu groß → in Unterkonzepte aufspalten
- Zu klein → mit verwandtem Konzept zusammenführen
- Ausnahmen erlaubt für inhärent große Konzepte (z.B. Referenztabellen)

**Hierarchische Granularität (Verfeinerung):**
Wenn ein Konzept-Cluster eng zusammenhängt, optional verschachtelt ablegen:
```
concepts/authentication/
  _overview.md          ← Übersicht
  oauth2-flow.md
  jwt-tokens.md
  session-management.md
```

Der Transform Agent entscheidet pro Cluster: flach (default) oder verschachtelt (bei eng gekoppeltem Sub-Themenfeld).

**Frontmatter pro Konzept-Seite:**
```yaml
---
title: <Konzeptname>
sources:
  - file: <originaldatei>
    sections: ["§3.1", "§3.2"]
tags: [topic1, topic2]
created: 2026-05-10
---
```

**Übersetzung:**
- Alle Inhalte → Englisch
- Fachbegriffe konsistent (Glossar-Heuristik: häufige Begriffe einmal übersetzen, dann beibehalten)
- Quell-Sprache wird im `meta.json` festgehalten für ggf. spätere Referenz

### 4.4 Phase 3 — Link

**Aufgabe:** Konzepte deduplizieren und typisiert verlinken.

**Inkrementelles Clustering (Verfeinerung — Skala-Problem):**
Bei ~200–400 Vault-Seiten kann der Link Agent nicht alles gleichzeitig im Kontext halten. Daher:

1. **Sammelphase:** alle Konzepte → JSON-Liste mit `name + 1-Satz-Summary + tags` (kompakt)
2. **Cluster-Bildung:** Sonnet analysiert die Liste, identifiziert Cluster verwandter/duplizierter Konzepte
3. **Pro Cluster:** Sonnet lädt nur die Volltexte des Clusters → Merge-Entscheidung + Link-Setting

**Merge-Entscheidungen pro Cluster:**
- **Merge** — Konzepte sind inhaltlich identisch → eine Seite, Quellen aggregiert, Widersprüche explizit dokumentiert
- **Split mit `[[see-also]]`-Verweis** — überlappend, aber nicht identisch
- **Beibehalten** — trotz Namensähnlichkeit verschiedene Konzepte

**Typisierte Links — 5 Typen im Frontmatter:**
- `related` (symmetrisch, max 8): thematisch verwandt
- `prerequisites` (asymmetrisch, max 5): Vorwissen erforderlich
- `examples` (asymmetrisch, max 6): konkrete Umsetzung zu abstraktem Konzept
- `contrasts` (symmetrisch, max 4): alternative/gegensätzliche Konzepte
- `refines` (asymmetrisch, max 3): spezifischere Variante

**Inverse Links** werden in `_index/link_graph.json` materialisiert (z.B. `leads_to` als Inverse von `prerequisites`).

**MOC-Generierung:**
- Vertikale Hierarchie: Topic → Sub-Topic → Konzepte
- Horizontale Verweise: jede MOC verweist auf MOCs gleicher Ebene mit verwandten Themen

**Source-Dokument-Erhalt (Verfeinerung):**
Originale Quellkonvertierungen werden parallel zu Konzept-Seiten unter `vault/sources/` abgelegt. Konzept-Seiten verweisen via `sources[].file` auf die jeweilige Source-Seite — der Nutzer kann den Originalkontext aufrufen.

### 4.5 Phase 4 — QA

**Aufgabe:** Vault-Material vor Plugin-Generierung validieren. Der QA-Agent ist ein Meta-Agent, der spezialisierte Validatoren orchestriert und einen aggregierten Report erzeugt.

**Übersicht der sechs Validatoren:**

| # | Validator | Ausführung | Stichprobe |
|---|-----------|------------|------------|
| 1 | Translation Quality | Sonnet, low | 5%, min 10 |
| 2 | Link Resolution | Python, lokal | 100% |
| 3 | Coverage Check | Haiku, medium | 100% (pro Doc) |
| 4 | Citation Accuracy | Sonnet, medium | 10% |
| 5 | Concept Coherence | Sonnet, high | 15% + verdächtige |
| 6 | Vault Integrity | Python, lokal | 100% |

**Validator 1 — Translation Quality (Sonnet, effort: low):**
- Zufallsstichprobe von 5% der Konzepte (mindestens 10, max 50)
- Pro Stichprobe: Original-Passage vs. Übersetzung vergleichen
- Prüft: Idiomatik, Fachbegriff-Konsistenz, Vollständigkeit
- Bei einzelnen Ausreißern: Konzept zurück durch Transform mit `--retry-translation`

**Validator 2 — Link Resolution (Python, deterministisch):**
- Kein API-Call. Reines Skript.
- Parst alle `[[wikilinks]]` aus Frontmatter und Body
- Prüft: existiert die Zielseite? existieren MOC-Verweise? keine zirkulären `prerequisites`?
- Fix-Versuch via Levenshtein-Toleranz bei Typos, sonst Replay der Link-Phase

**Validator 3 — Coverage Check (Haiku, effort: medium):**
- Pro Quelldokument: Original-Outline (aus Phase 1) vs. erzeugte Konzepte
- Frage an Haiku: "Welche Themen aus dieser Outline sind nicht in der Konzept-Liste vertreten?"
- Bei Lücken: Konzept-Extraktion für die fehlenden Bereiche nachholen
- Toleranzschwelle: <2% verlorene Themen ist okay

**Validator 4 — Citation Accuracy (Sonnet, effort: medium):**
- Stichprobe von 10% der Konzept-Seiten
- Pro Stichprobe: Behauptung im Konzept vs. zitierte Stelle im Original
- Strengste Validator-Schwelle, da Citations sicherheitskritisch sind

**Validator 5 — Concept Coherence (Sonnet, effort: high):**
- Pro Konzept: liest die Seite "kalt" (ohne Kontext)
- Prüft: würde ein Leser nur diese Seite verstehen können?
- Identifiziert ungeklärte Bezüge ("wie oben erwähnt"), unverständliche Abkürzungen, fehlenden Kontext
- Stichprobe 15% plus alle "verdächtigen" Konzepte (sehr kurz, viele unaufgelöste Verweise)

**Validator 6 — Vault Integrity (Python, deterministisch):**
- Frontmatter-YAML valid? Pflicht-Felder vorhanden? Sources-Pfade existent?
- Verzeichnisstruktur entspricht Spec? Dateinamen Obsidian-kompatibel?
- `_index/`-Dateien sind valides JSON?

**Eskalations-Schwellen:**
- Translation: >5% Fehler in Stichprobe → ganze Übersetzungsphase wiederholen
- Citation: >2% Fehler → kritisch, Transform-Phase wiederholen (Citations sind sicherheitskritisch)
- Coherence: einzelne Probleme → gezielter Replay des betroffenen Konzepts
- Coverage: >2% verlorene Themen → Nachholung in Transform

**Auto-Repair:** maximal 2 Iterationen, dann Eskalation an Nutzer.

**Output:** `phase_4_qa/qa_report.json` mit Status pro Validator und Empfehlungen.

**QA-Kosten-Begrenzung:** Volldeckende Validatoren (2, 6) lokal/gratis. Semantische Validatoren nur Stichproben. QA insgesamt soll <10% der Gesamtkosten ausmachen.

### 4.6 Phase 5 — Emit

**Aufgabe:** Generiert das fertige Experten-Skill-Plugin.

**Output-Struktur:**
```
<expert-plugin>/
├── .claude-plugin/
│   └── plugin.json              ← Marketplace-Metadaten
├── README.md                    ← Installation, Nutzung, Vault-Inhalt
├── skills/
│   └── <expert-name>/
│       ├── SKILL.md             ← Trigger-Description, Workflows
│       ├── vault/
│       │   ├── concepts/
│       │   ├── MOCs/
│       │   └── sources/         ← Original-Konvertierungen
│       ├── _index/
│       │   ├── concept_index.json
│       │   ├── moc_map.json
│       │   ├── link_graph.json
│       │   └── alias_map.json
│       └── scripts/
│           ├── vault_locate.py
│           ├── vault_search.py
│           ├── vault_traverse.py
│           ├── vault_brainstorm.py
│           ├── vault_cite.py
│           ├── memory_update.py
│           └── memory_inspect.py
└── LICENSE
```

**SKILL.md-Generierung:**
Der Emit Agent erzeugt eine SKILL.md mit:
- **Triggering-Description** basierend auf den im Vault dominanten Themen (vom Konzept-Index abgeleitet) — pushy formuliert für gute Trigger-Rate
- **Workflows** für Q&A und Brainstorming
- **Citation-Format-Spezifikation**
- **Mode-Detection-Heuristiken**

**Initial-Memory-Erzeugung:**
Der Emit Agent legt initiale Versionen der mutable Memory-Dateien an:
- `query_cache.json` → leer
- `path_frequency.json` → mit synthetischen Co-Accesses (basierend auf Link-Graph)
- `user_preferences.json` → Defaults
- `learned_aliases.json` → leer

Ablageort: `~/.claude/projects/<project-id>/memory/<expert-skill-name>/`

Wobei `<project-id>` von Claude Code aus dem Working-Directory abgeleitet wird (Pfad mit `/` ersetzt durch `-`, vgl. das bestehende Memory-Verzeichnis-Schema). `<expert-skill-name>` entspricht dem `name`-Feld der generierten SKILL.md.

## 5. Experten-Skill (Runtime)

### 5.1 Vier-Schichten-Retrieval

```
Frage → Schicht 1: Entry-Point (Memory-Lookup + MOC-Match)     [Python, gratis]
      → Schicht 2: Targeted Search (Ripgrep + Tag-Match)        [Python, gratis]
      → Schicht 3: Graph-Expansion (typisierte Link-Walks)      [Python, gratis]
      → Schicht 4: Synthese mit Citations                       [API-Call, Modell des Nutzers]
```

Schichten 1–3 laden den fokussierten Kontext, erst Schicht 4 verursacht API-Kosten.

### 5.2 Zwei Modi

**Q&A-Modus** (default):
- Konvergent, fokussiert
- Top-3 relevanteste Konzepte
- Direkte Antwort mit Quellen

**Brainstorming-Modus** (auto-detected oder explizit):
- Divergent, hypothesengetrieben
- Tiefere Graph-Traversierung, breiter Sweep
- Output als **Hypothesen** mit:
  - Proposition
  - Begründung + Quellen
  - Annahmen (explizit)
  - Konfidenz (hoch/mittel/niedrig nach Vault-Stütze)
  - Falsifikationskriterien
- Macht Vault-Lücken (🔍) und Quellenkonflikte (⚠️) explizit
- Welt-Wissen wird als 💡 markiert
- Endet mit forschender Folgefrage

### 5.3 Multilinguale Antworten (Verfeinerung — Runtime-Kosten)

- Vault ist Englisch
- Antwort in Sprache des Nutzers
- Heuristik: Eingangssprache wird detektiert (Skript-basiert, gratis)
- Skill formuliert Antwort direkt in Zielsprache (kein Doppelschritt)
- Fachbegriffe: per `user_preferences.technical_terms` steuerbar (`translate` | `keep_english`)
- Citations bleiben immer in Originalform: `[[concept-name]]` und `Source.pdf §X`

**Runtime-Kosten:** Multilinguale Antworten verursachen ca. 15-25% mehr Output-Tokens als reine Englisch-Antworten. Wird in der Builder-Kostenschätzung als Hinweis mitgegeben.

### 5.4 Memory-Architektur

**Immutable** (im Plugin):
- `concept_index.json`, `moc_map.json`, `link_graph.json`, `alias_map.json`

**Mutable** (in `~/.claude/projects/<project-id>/memory/<expert-skill-name>/`):
- `query_cache.json` (TTL 30 Tage, max ~100 Einträge, LRU)
- `path_frequency.json` (Co-Access-Statistik)
- `user_preferences.json` (Sprache, Tiefe, Fachbegriff-Handling)
- `learned_aliases.json` (Nutzer-Vokabular)
- `session_log.json` (Brainstorming-Sessions inkl. Hypothesen-Lifecycle)

Update via `scripts/memory_update.py` nach jeder Antwort.

### 5.5 Skript-Toolbox

| Skript | Zweck |
|--------|-------|
| `vault_locate.py` | Schicht 1 — Entry Points via Memory + MOC |
| `vault_search.py` | Schicht 2 — Ripgrep + Tag-Match |
| `vault_traverse.py` | Schicht 3 — typisierte Graph-Expansion |
| `vault_brainstorm.py` | Brainstorming — Hypothesen-JSON erzeugen |
| `vault_cite.py` | Citation-Helper — Source-Info zu Vault-Seiten |
| `memory_update.py` | Memory-Update nach Frage |
| `memory_inspect.py` | Memory-Stand inspizieren |

Alle Skripte sind Python ohne externe Dependencies (außer `ripgrep` als System-Binary).

## 6. Failure-Recovery

**State-Persistenz:**
- Pro Run: `~/.docs-to-skill/<run-id>/`
- Zentrale Datei: `pipeline_state.json` mit Phase-Status, Item-Status, Kosten-Tracker
- Jede Phase persistiert ihre Outputs

**Resume-Granularitäten:**
- Phase-Level: "starte mit Transform"
- Item-Level: "weiter mit Konzept 201"
- Sub-Item-Level: "weiter mit QA-Schritt 5 für Konzept X"

**Failure-Klassen:**
| Klasse | Verhalten |
|--------|-----------|
| Transient | Auto-Retry mit Exponential Backoff, max 3× |
| Recoverable | Item als `failed`, Pipeline weiter |
| Critical | Pause, State erhalten, Nutzer-Eingriff |
| Data | Mit Warning-Tag versehen, weiter |

**Replay:**
```bash
docs-to-skill --replay --run-id <id> --phase <name>
```
Wirft die genannte Phase + alle nachfolgenden, läuft ab dort neu.

**Cleanup:**
Nach erfolgreichem Emit fragt der Builder: behalten oder löschen.

## 7. Kostenmanagement

### 7.1 Schätzung vor Start

**Methodik:**
1. Ingest-Kosten: 0 (lokale Tools), Vision-Fallback geschätzt nach Heuristik (% wahrscheinlich problematischer PDFs)
2. Transform-Kosten: `total_input_tokens × translation_factor × Haiku-Preis`
3. Link-Kosten: `concept_count × cluster_factor × Sonnet-Preis`
4. QA-Kosten: `stichproben_anteil × Sonnet/Haiku gemischt`
5. Emit-Kosten: festes Budget + variabler Anteil pro 100 Konzepte
6. Puffer: +20% für Auto-Repair

**Output an Nutzer vor Start:**
```
Geschätzte Kosten:
  Ingest:    $0.00 - $1.20  (abhängig von Vision-Fallback-Häufigkeit)
  Transform: $4.50 - $5.80
  Link:      $2.10
  QA:        $0.80
  Emit:      $0.40
  Puffer:    $1.50
  ───────────────────────
  Gesamt:    $9.30 - $11.80

Hinweis: Runtime-Kosten des erzeugten Skills ca. $0.05-$0.20 pro Frage 
(modell-abhängig, multilinguale Antworten +15-25%).

Fortfahren? [Y/n]
```

### 7.2 Tracking während Build

Jeder Agent-Call wird in `pipeline_state.json.cost_tracker` festgehalten. Nach jeder Phase Update an Nutzer.

### 7.3 Effort-Level-Semantik

In diesem Design steht **Effort-Level** für:
1. **Extended-Thinking-Budget** (sofern für das Modell aktiv): low/medium/high entspricht definierten Token-Budgets
2. **Prompt-Komplexität**: höhere Level enthalten mehr Constraints, Beispiele, Self-Verification-Schritte

Konkrete Mapping-Regeln werden im Implementierungsplan festgelegt.

## 8. Vault-Verzeichnisstruktur

```
vault/
├── concepts/                ← konzept-basierte Vault-Seiten
│   ├── oauth2-flow.md
│   ├── jwt-tokens.md
│   └── authentication/      ← optional verschachtelt
│       ├── _overview.md
│       └── ...
├── MOCs/                    ← Maps of Content (Hierarchie + horizontale Verweise)
│   ├── security.md
│   ├── authentication.md
│   └── ...
└── sources/                 ← Original-Konvertierungen (für Audit/Kontext)
    ├── handbuch.md
    ├── security_guide.md
    └── ...

_index/                      ← außerhalb des sichtbaren Vaults
├── concept_index.json
├── moc_map.json
├── link_graph.json
└── alias_map.json
```

Der `vault/`-Ordner ist ein vollständig valider Obsidian-Vault — der Nutzer kann ihn direkt öffnen.

## 9. Plugin-Output

Das generierte Plugin folgt der Standard-Claude-Code-Plugin-Konvention:
- `.claude-plugin/plugin.json` mit Metadaten
- `skills/<name>/SKILL.md` mit pushy Trigger-Description
- `README.md` für Installation und Nutzung

Plugin ist sofort installierbar via Standard-Plugin-Mechanismen.

## 10. Offene Fragen für Implementierungsplan

Diese Punkte sind in der Architektur-Diskussion erkannt, aber wurden nicht im Detail spezifiziert — der Implementierungsplan muss sie adressieren:

1. Konkrete Token-Budgets pro Effort-Level (low/medium/high)
2. Genaue Heuristiken für Mode-Detection (Q&A vs. Brainstorming)
3. Concrete Prompts für jeden Agent (Ingest, Transform, Link, QA-Validatoren, Emit)
4. Genaues Format des `query_cache`-Matchings (exakt vs. fuzzy)
5. Marketplace-Veröffentlichungsweg für generierte Plugins (separater Schritt durch den Nutzer)
6. Versionierung des Vaults bei Re-Builds (überschreiben? Versions-Suffix?)

## 11. Was bewusst ausgeschlossen ist (YAGNI)

- **Inkrementelle Imports:** Vault wird bei Re-Build komplett neu erzeugt. Inkrementelle Updates sind nicht im Scope von v1.
- **Subagents zur Laufzeit:** Der Experten-Skill nutzt bewusst keine Subagents — nur Skripte und direkten LLM-Call. Subagent-Overhead lohnt nicht für Q&A.
- **REST API / Web-UI:** Der Skill wird ausschließlich über Claude Code genutzt.
- **Embedding-basierte semantische Suche:** Wir setzen auf Konzept-Index + Ripgrep + Graph-Walk. Embedding-Index könnte in v2 ergänzt werden, ist aber nicht nötig für die Skala.
- **Multi-User-Vault-Sharing:** Memory ist pro Nutzer, Plugin ist installiertes Artefakt. Kein zentraler Server.

---

## Anhang A: Begriffs-Glossar

- **Vault** — der Obsidian-konforme Wissensspeicher
- **Konzept** — eine atomare, kohärente Wissenseinheit (eine Vault-Seite)
- **MOC** — Map of Content, hierarchische Übersicht
- **Wikilink** — `[[seitenname]]` im Obsidian-Stil
- **Frontmatter** — YAML-Header einer Markdown-Datei
- **Source-Attribution** — Verweis von einer Konzept-Seite auf die Originalquelle
- **Hypothese** — Brainstorming-Output: testbare Proposition mit expliziten Annahmen und Falsifikationskriterien
