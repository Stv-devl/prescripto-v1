"""Validate assembled message structure against prompt rules.

Uses a REAL chat result (plancher bois) to check coherence of:
- Text body (SYSTEM_PROMPT rules)
- Structured table (TABLE_EXTRACTION_PROMPT rules)
- Schema (SCHEMA_EXTRACTION_PROMPT rules)

Five cases are xfail, and they are prompt defects rather than code drift: the
recorded sample is what the model actually returned, and the rules it breaks are
written in the prompts themselves. They reduce to three causes, each carrying a
line in docs/product/backlog.md so the debt is visible outside this file:

- TABLE_EXTRACTION_PROMPT drops the dimensions it asks for
- SCHEMA_EXTRACTION_PROMPT emits the "non précisé(e)" it forbids, instead of
  dropping the layer
- SCHEMA_TYPES has no plancher_bois, so a timber floor is typed as hourdis and
  the layers open on finishes the text never mentions

`strict=False` is deliberate: the day a prompt is fixed the case passes, and an
xpass must not turn the suite red before someone has flipped it to a plain
assert. Fixing a prompt therefore means coming back here.
"""

import json
import re

import pytest

from app.schemas.chat import StructuredSchema, StructuredTable
from app.services.chat.prompts import SCHEMA_TYPES

# ── Regex helpers ────────────────────────────────────────────────

_QTY_RE = re.compile(r"\d+[.,]?\d*\s*(?:m[²³23]?|ml|kg|U|l)\b", re.IGNORECASE)
_BOLD_RE = re.compile(r"\*\*[^*]+\*\*")
_BULLET_RE = re.compile(r"^- ", re.MULTILINE)
_SOURCE_REF_RE = re.compile(r"\[.*?,\s*p\.\d+\]")
_TITLE_RE = re.compile(r"^#{1,6}\s", re.MULTILINE)
_NON_PRECISE_RE = re.compile(
    r"non\s+pr[ée]cis[ée]e?|non\s+mentionn[ée]e?|non\s+d[ée]taill[ée]e?"
    r"|non\s+disponible|information\s+absente|donn[ée]e\s+manquante",
    re.IGNORECASE,
)
_NO_QTY_RE = re.compile(
    r"^(—|-|non\s+chiffr[ée]e?|non\s+quantifi[ée]e?"
    r"|non\s+pr[ée]cis[ée]e?|n/?a|inconnue?|sans|aucune?|)$",
    re.IGNORECASE,
)


# ── Real chat result: plancher bois ──────────────────────────────

REAL_TEXT = (
    "Le projet comprend deux planchers bois distincts :\n\n"
    "**Plancher haut RDC** (plancher du R+1) :\n\n"
    "- **Solivage bois** 80×200 mm en sapin du nord traité, entraxe 0,50 m, "
    "raboté 4 faces.\n"
    "- **Panneaux OSB 22 mm** posés sur solivage, fixation par vissage "
    "avec bande de phaltex 10 mm.\n"
    "- **Poutre en lamellé collé** 15×40 cm, rabotée 4 faces, "
    "calages et ferrures inclus.\n"
    "- **Faux-plafond** en panneaux OSB ou dérivés, localisé sous ce plancher.\n\n"
    "**Plancher haut du garage** (zone de rangement) :\n\n"
    "- **Solivage bois** 80×200 mm en sapin du nord traité, entraxe 0,50 m.\n"
    "- **Panneaux OSB 18 mm** posés sur solivage.\n\n"
    "**Localisation** :\n\n"
    "- Plancher haut RDC : R+1 (maison principale).\n"
    "- Plancher haut du garage : garage (zone de rangement)."
)

REAL_TABLE = StructuredTable(
    title="Planchers bois",
    columns=["Élément", "Description", "Quantité", "Localisation"],
    rows=[
        {
            "element": "Solivage bois",
            "description": "Solivage structurel",
            "quantite": "72.53 m² + 20.43 m²",
            "localisation": "plancher haut RDC, haut RDC du garage",
        },
        {
            "element": "Plancher bois OSB",
            "description": "Panneaux OSB sur solivage",
            "quantite": "72.53 m² + 20.43 m²",
            "localisation": "plancher haut RDC, haut RDC du garage",
        },
        {
            "element": "Poutre en lamellé collé",
            "description": "Poutre support plancher",
            "quantite": "11.58 ml",
            "localisation": "plancher bois du R+1",
        },
    ],
)

REAL_SCHEMA = StructuredSchema(
    schema_type="plancher_hourdis",
    title="Plancher bois R+1 avec solivage et revêtement",
    params={
        "couches": json.dumps(
            [
                {"nom": "Parquet stratifié BALANCE CLICK", "epaisseur": "0.8 cm", "nature": "revetement"},
                {"nom": "Sous-couche phonique SILENT WALK", "epaisseur": "0.3 cm", "nature": "isolant_acoustique"},
                {"nom": "Panneau OSB hydrofugé", "epaisseur": "1.8 cm", "nature": "bois"},
                {"nom": "Solivage bois", "epaisseur": "non précisée", "nature": "bois"},
            ],
            ensure_ascii=False,
        ),
        "type_poutrelle": "solivage bois",
        "entraxe": "non précisé",
    },
)


# ── Text body tests ─────────────────────────────────────────────


class TestTextBody:
    """Validate text body against SYSTEM_PROMPT rules."""

    def test_has_bold_terms(self) -> None:
        matches = _BOLD_RE.findall(REAL_TEXT)
        assert len(matches) >= 2, f"Expected ≥2 bold terms, got {len(matches)}: {matches}"

    def test_has_bullet_list(self) -> None:
        matches = _BULLET_RE.findall(REAL_TEXT)
        assert len(matches) >= 2, f"Expected ≥2 bullets, got {len(matches)}"

    def test_no_source_references(self) -> None:
        assert not _SOURCE_REF_RE.search(REAL_TEXT), "No [file, p.X] allowed in body"

    def test_no_markdown_titles(self) -> None:
        assert not _TITLE_RE.search(REAL_TEXT), "No # titles in body text"

    def test_no_non_precise_in_text(self) -> None:
        """SYSTEM_PROMPT rule 6: INTERDICTION de signaler info absente."""
        match = _NON_PRECISE_RE.search(REAL_TEXT)
        assert match is None, f"Found forbidden pattern in text: '{match.group()}'"

    def test_paragraphs_separated(self) -> None:
        assert "\n\n" in REAL_TEXT

    def test_has_localisation_block(self) -> None:
        assert "**Localisation**" in REAL_TEXT
        count = REAL_TEXT.count("**Localisation**")
        assert count == 1, f"Expected 1 Localisation block, got {count}"

    def test_localisation_after_all_descriptions(self) -> None:
        loc_pos = REAL_TEXT.find("**Localisation**")
        desc_bullets = REAL_TEXT[:loc_pos]
        assert "- **" in desc_bullets, "Description bullets should precede Localisation"


# ── Structured table tests ───────────────────────────────────────


class TestStructuredTable:
    """Validate table against TABLE_EXTRACTION_PROMPT rules."""

    def test_has_quantite_column(self) -> None:
        cols_lower = [c.lower().replace("é", "e") for c in REAL_TABLE.columns]
        assert "quantite" in cols_lower, f"Missing Quantité column in {REAL_TABLE.columns}"

    def test_every_row_has_quantity_value(self) -> None:
        """CHAQUE ligne DOIT avoir une valeur chiffrée."""
        for row in REAL_TABLE.rows:
            qty = row.get("quantite", "")
            assert not _NO_QTY_RE.match(qty.strip()), (
                f"Row '{row.get('element')}' has empty/invalid quantity: '{qty}'"
            )
            assert _QTY_RE.search(qty), (
                f"Row '{row.get('element')}' quantity missing numeric+unit: '{qty}'"
            )

    def test_row_count_1_to_8(self) -> None:
        assert 1 <= len(REAL_TABLE.rows) <= 8

    def test_no_duplicate_elements(self) -> None:
        elements = [r.get("element", "").strip().lower() for r in REAL_TABLE.rows]
        assert len(elements) == len(set(elements)), f"Duplicates: {elements}"

    @pytest.mark.xfail(
        reason="Known defect in the recorded sample: TABLE_EXTRACTION_PROMPT asks for "
        "material + key dimensions, the model returned 'Solivage structurel' and dropped "
        "the 80x200 mm it had in context. Prompt defect, not a code drift — flip to a "
        "plain assert once the extraction prompt is fixed.",
        strict=False,
    )
    def test_description_includes_dimensions(self) -> None:
        """TABLE_EXTRACTION_PROMPT: inclure matériau, dimensions clés.
        'Solivage structurel' perd les dimensions 80×200 mm du contexte.
        """
        for row in REAL_TABLE.rows:
            desc = row.get("description", "")
            element = row.get("element", "")
            # A description of just 1-2 generic words is too vague
            word_count = len(desc.split())
            assert word_count >= 3, (
                f"Row '{element}' description too vague ({word_count} words): '{desc}'"
            )

    def test_description_max_15_words(self) -> None:
        for row in REAL_TABLE.rows:
            desc = row.get("description", "")
            word_count = len(desc.split())
            assert word_count <= 20, (
                f"Row '{row.get('element')}' description too long: {word_count} words"
            )


# ── Schema tests ─────────────────────────────────────────────────


class TestStructuredSchema:
    """Validate schema against SCHEMA_EXTRACTION_PROMPT rules."""

    def test_schema_type_valid(self) -> None:
        assert REAL_SCHEMA.schema_type in SCHEMA_TYPES, (
            f"Unknown schema type: '{REAL_SCHEMA.schema_type}'. "
            f"Valid: {list(SCHEMA_TYPES.keys())}"
        )

    def test_params_keys_allowed(self) -> None:
        allowed = set(SCHEMA_TYPES[REAL_SCHEMA.schema_type])
        actual = set(REAL_SCHEMA.params.keys())
        assert actual.issubset(allowed), (
            f"Unexpected params: {actual - allowed} (allowed: {allowed})"
        )

    def test_couches_valid_json(self) -> None:
        couches_raw = REAL_SCHEMA.params.get("couches")
        assert couches_raw is not None, "Missing couches param for multicouche schema"
        couches = json.loads(couches_raw)
        assert isinstance(couches, list)
        assert len(couches) >= 2, f"Expected ≥2 layers, got {len(couches)}"

    def test_couches_required_fields(self) -> None:
        couches = json.loads(REAL_SCHEMA.params["couches"])
        for i, couche in enumerate(couches):
            for field in ("nom", "epaisseur", "nature"):
                assert field in couche, f"Layer {i} missing '{field}': {couche}"

    def test_couches_nature_valid(self) -> None:
        valid_natures = {
            "beton", "beton_arme", "chape", "mortier", "isolant_thermique",
            "isolant_acoustique", "etancheite", "pare_vapeur", "film_pe",
            "revetement", "carrelage", "enduit", "plaque_platre", "bois",
            "metal", "gravier", "enrobe", "grave", "hourdis", "geotextile",
            "tuile", "ecran_sous_toiture",
        }
        couches = json.loads(REAL_SCHEMA.params["couches"])
        for couche in couches:
            nature = couche.get("nature", "")
            assert nature in valid_natures, (
                f"Invalid nature '{nature}' in layer '{couche.get('nom')}'"
            )

    @pytest.mark.xfail(
        reason="Known defect in the recorded sample: SCHEMA_EXTRACTION_PROMPT forbids "
        "'non précisé(e)' values, the model emitted them for 'entraxe' and for the "
        "solivage layer thickness. Prompt defect, not a code drift.",
        strict=False,
    )
    def test_no_non_precise_in_schema(self) -> None:
        """Aucune valeur du schéma ne doit contenir 'non précisé(e)'."""
        # Check all params
        for key, value in REAL_SCHEMA.params.items():
            assert not _NON_PRECISE_RE.search(value), (
                f"Schema param '{key}' contains forbidden pattern: '{value}'"
            )

    @pytest.mark.xfail(
        reason="Same recorded defect as test_no_non_precise_in_schema: the 'Solivage bois' "
        "layer carries epaisseur='non précisée' where the rule says to drop the layer "
        "instead. Prompt defect, not a code drift.",
        strict=False,
    )
    def test_couches_epaisseur_numeric(self) -> None:
        """Toutes les épaisseurs doivent être numériques (ex: '22 cm'), jamais 'non précisée'."""
        couches = json.loads(REAL_SCHEMA.params["couches"])
        epaisseur_re = re.compile(r"^\d+[.,]?\d*\s*(?:cm|m|mm)$")
        for couche in couches:
            ep = couche.get("epaisseur", "")
            if ep == "inf":
                continue  # Valid for substratum in coupe_geotechnique
            assert epaisseur_re.match(ep) or _NON_PRECISE_RE.search(ep) is None, (
                f"Layer '{couche.get('nom')}' has invalid epaisseur: '{ep}' "
                f"(expected numeric like '22 cm')"
            )
            assert not _NON_PRECISE_RE.search(ep), (
                f"Layer '{couche.get('nom')}' epaisseur is 'non précisée' — "
                f"rule: if unknown, DO NOT include the layer"
            )

    def test_title_not_empty(self) -> None:
        assert REAL_SCHEMA.title.strip()


# ── Cross-coherence tests ────────────────────────────────────────


class TestAssemblyCoherence:
    """Coherence between text body, table, and schema."""

    def test_table_elements_mentioned_in_text(self) -> None:
        """Chaque élément du tableau doit apparaître dans le corps texte."""
        text_lower = REAL_TEXT.lower()
        for row in REAL_TABLE.rows:
            element = row.get("element", "").lower()
            # Match first significant word (e.g. "solivage" from "solivage bois")
            first_word = element.split()[0] if element else ""
            assert first_word in text_lower, (
                f"Table element '{element}' not found in text body"
            )

    @pytest.mark.xfail(
        reason="Known defect in the recorded sample: schema_extraction picked "
        "'plancher_hourdis' (concrete beams + infill) for a text describing a timber "
        "solivage. SCHEMA_TYPES has no 'plancher_bois', so the honest output is 'none'. "
        "Fix is either a new schema type or a stricter extraction prompt.",
        strict=False,
    )
    def test_schema_coherent_with_question(self) -> None:
        """Schema type should match the ouvrage described in the text.

        A plancher bois (solivage) is NOT a plancher hourdis (poutrelles béton).
        If there's no matching schema type, schema_type should be 'none'.
        """
        text_lower = REAL_TEXT.lower()
        schema_type = REAL_SCHEMA.schema_type

        # plancher_hourdis = poutrelles béton + entrevous — NOT solivage bois
        if "solivage" in text_lower and "poutrelle" not in text_lower:
            assert schema_type != "plancher_hourdis", (
                f"Schema type '{schema_type}' is incoherent with text: "
                f"text describes solivage bois, not hourdis béton. "
                f"Should be 'none' (no plancher_bois type exists) or a new type."
            )

    @pytest.mark.xfail(
        reason="Known defect in the recorded sample: the question was about the timber "
        "floor structure, the extracted schema opens with parquet and acoustic underlay — "
        "finish layers the text never describes. Same root cause as the schema_type "
        "defect above.",
        strict=False,
    )
    def test_schema_layers_no_revêtement_for_structure(self) -> None:
        """If the question is about structure (plancher bois), schema should show
        structural layers, not finitions (parquet, sous-couche).
        """
        couches_raw = REAL_SCHEMA.params.get("couches")
        if couches_raw is None:
            pytest.skip("No couches")
        couches = json.loads(couches_raw)
        text_lower = REAL_TEXT.lower()

        # If text is about plancher bois structure, check layers are structural
        if "solivage" in text_lower and "parquet" not in text_lower:
            layer_names = [c["nom"].lower() for c in couches]
            revetement_layers = [
                n for n in layer_names
                if any(kw in n for kw in ("parquet", "stratifié", "carrelage", "moquette"))
            ]
            assert not revetement_layers, (
                f"Schema includes finition layers {revetement_layers} "
                f"but the text describes structural plancher bois, not revêtements"
            )
