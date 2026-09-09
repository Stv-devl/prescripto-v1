"""Contract tests for the chat prompts, and for the forced-related patterns.

These lock the rules the prompt is actually expected to carry today. The
previous version of this file asserted a spec (docs/test-message-structure.md,
"15 response patterns") that the prompt no longer implements: the response
template was slimmed down, the regulatory / Eurocode and "résumé" rules moved to
the summary service, and out-of-scope handling moved from a prompt section to the
OFF_TOPIC sentinel returned by the rewrite step. Those assertions were rewritten
against the current prompt rather than left red.

A prompt rule that changes on purpose should change here in the same commit —
that is the whole point of these tests.

`TestGetForcedRelated` was in `test_chat_rewrite.py` until the TDD mirror was
repaired. `get_forced_related` is defined here, in `prompts.py`, not in
`query_rewrite.py`: left in the other file its cases would have frozen under the
wrong module, and the freeze's patch guard would then have allowed an insertion
that neutralises them.
"""

from app.services.chat.prompts import (
    OFF_TOPIC,
    REWRITE_PROMPT,
    SYSTEM_PROMPT,
    get_forced_related,
)


class TestGroundingRules:
    """What keeps an answer tied to the retrieved documents."""

    def test_context_only(self) -> None:
        assert "UNIQUEMENT sur les documents fournis" in SYSTEM_PROMPT

    def test_no_source_citations_in_the_body(self) -> None:
        assert "Ne cite JAMAIS de source" in SYSTEM_PROMPT

    def test_never_fabricate(self) -> None:
        assert "Ne fabrique JAMAIS d'information" in SYSTEM_PROMPT

    def test_missing_data_is_not_announced(self) -> None:
        """The model omits what it does not have instead of narrating its absence."""
        assert "INTERDIT de signaler qu'une info est absente" in SYSTEM_PROMPT


class TestLotsRules:
    def test_only_explicit_lots(self) -> None:
        assert "LOT n°" in SYSTEM_PROMPT

    def test_no_lot_inference(self) -> None:
        assert "Ne déduis pas de lots" in SYSTEM_PROMPT

    def test_labels_copied_verbatim(self) -> None:
        assert "EXACTEMENT" in SYSTEM_PROMPT


class TestTechnicalData:
    def test_complete_dimensions(self) -> None:
        assert "dimensions COMPLÈTES" in SYSTEM_PROMPT

    def test_raw_dimensions_without_glosses(self) -> None:
        assert "Dimensions BRUTES" in SYSTEM_PROMPT

    def test_haut_convention(self) -> None:
        """'haut RDC' = the R+1 slab — a domain convention worth pinning."""
        assert "CONVENTION 'HAUT'" in SYSTEM_PROMPT


class TestFormatting:
    def test_markdown_bold(self) -> None:
        assert "**gras**" in SYSTEM_PROMPT

    def test_concision(self) -> None:
        assert "CONCIS" in SYSTEM_PROMPT

    def test_no_titles_tables_or_code_blocks(self) -> None:
        assert "titres (#)" in SYSTEM_PROMPT
        assert "tableaux" in SYSTEM_PROMPT
        assert "blocs de code" in SYSTEM_PROMPT

    def test_paragraphs_separated_by_a_blank_line(self) -> None:
        assert "ligne vide" in SYSTEM_PROMPT


class TestOuvrageStructure:
    """One block per ouvrage: intro, bullet list, Localisation, Normes."""

    def test_single_block_per_ouvrage(self) -> None:
        assert "STRUCTURE OBLIGATOIRE" in SYSTEM_PROMPT
        assert "UN SEUL BLOC par ouvrage" in SYSTEM_PROMPT

    def test_localisation_appears_exactly_once(self) -> None:
        assert "**Localisation" in SYSTEM_PROMPT
        assert "UNE SEULE FOIS" in SYSTEM_PROMPT

    def test_final_order_is_localisation_then_normes(self) -> None:
        assert "**Localisation** puis **Normes**" in SYSTEM_PROMPT

    def test_final_validation_step(self) -> None:
        assert "VALIDATION FINALE" in SYSTEM_PROMPT


class TestRewritePrompt:
    """The rewrite step owns off-topic detection and the intent flags."""

    def test_off_topic_sentinel_matches_the_one_the_parser_looks_for(self) -> None:
        assert OFF_TOPIC in REWRITE_PROMPT

    def test_project_level_questions_are_never_off_topic(self) -> None:
        assert "ne les marque JAMAIS comme HORS_SUJET" in REWRITE_PROMPT

    def test_query_length_is_bounded(self) -> None:
        assert "5 à 20 mots MAX" in REWRITE_PROMPT

    def test_structured_flag_values(self) -> None:
        assert '"table"' in REWRITE_PROMPT
        assert '"none"' in REWRITE_PROMPT


class TestGetForcedRelated:
    """FORCED_RELATED currently holds two patterns: soubassement/infrastructure
    and murs/façades. Fondations, dallage and charpente were removed — their
    tests went with them."""

    def test_soubassement_triggers_infrastructure_queries(self) -> None:
        result = get_forced_related("soubassement en agglos")
        assert any("longrine" in q for q in result)
        assert any("drainage" in q or "étanchéité" in q for q in result)

    def test_vide_sanitaire_triggers_same_family(self) -> None:
        result = get_forced_related("vide sanitaire sur longrines")
        assert any("hourdis" in q for q in result)

    def test_mur_triggers_facade_queries(self) -> None:
        result = get_forced_related("mur de façade en parpaing")
        assert any("enduit extérieur" in q for q in result)
        assert any("maçonnerie" in q for q in result)

    def test_mur_enterre_is_infrastructure_not_facade(self) -> None:
        """The negative lookahead keeps a buried wall out of the façade family."""
        result = get_forced_related("mur enterré")
        assert any("paroi" in q or "longrine" in q for q in result)
        assert not any("enduit extérieur façade" in q for q in result)

    def test_isolation_triggers_related(self) -> None:
        result = get_forced_related("isolation thermique murs")
        assert any("enduit" in q or "plaque" in q for q in result)

    def test_no_match_returns_empty(self) -> None:
        result = get_forced_related("quels sont les lots du projet")
        assert result == []
