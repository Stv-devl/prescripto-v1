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


class TestNormesBlockByMode:
    """The Normes rule of the system prompt and the ouvrage instruction, per mode."""

    MUR = "Quelle est la composition du mur extérieur ?"
    NO_MATCH = "Quels sont les lots du projet ?"
    NORM_EXAMPLES = ("tous les DTU", "20.1", "26.1", "25.41")

    def test_baseline_system_prompt_has_the_historical_sha256(self) -> None:
        import hashlib

        from app.services.chat.prompts import system_prompt_for

        digest = hashlib.sha256(system_prompt_for("baseline").encode("utf-8")).hexdigest()
        assert digest == "72164b88e250e32acdb5bd6fd47869f20d5292bddb1b67836c74937b76c90d52"

    def test_v1_system_prompt_carries_the_context_and_ouvrage_rule(self) -> None:
        from app.services.chat.prompts import system_prompt_for

        assert (
            "écrites dans le contexte ET rattachées à l'ouvrage de la question"
            in system_prompt_for("v1")
        )

    def test_v1_system_prompt_forbids_a_norm_absent_from_the_context(self) -> None:
        from app.services.chat.prompts import system_prompt_for

        assert "INTERDIT de citer une norme absente du contexte" in system_prompt_for("v1")

    def test_v1_system_prompt_drops_the_block_when_there_is_no_norm(self) -> None:
        from app.services.chat.prompts import system_prompt_for

        assert "PAS de bloc Normes" in system_prompt_for("v1")

    def test_v1_system_prompt_no_longer_asks_for_applicable_norms(self) -> None:
        from app.services.chat.prompts import system_prompt_for

        assert "DTU/NF EN applicables" not in system_prompt_for("v1")

    def test_v1_system_prompt_differs_from_baseline_only_on_sentence_d_and_the_order_line(
        self,
    ) -> None:
        from app.services.chat.prompts import system_prompt_for

        baseline = system_prompt_for("baseline")
        v1 = system_prompt_for("v1")
        assert "   d) " in baseline
        assert "   ORDRE STRICT" in baseline
        assert v1.split("   d) ")[0] == baseline.split("   d) ")[0]
        assert v1[v1.index("   ORDRE STRICT"):] == (
            "   ORDRE STRICT en fin de réponse : **Localisation**, puis **Normes** "
            "UNIQUEMENT s'il y a au moins une norme à citer (règle d) — rien après. "
            "Une réponse sans bloc Normes est correcte.\n"
        ) + baseline[baseline.index("   Si plusieurs variantes"):]

    def test_v1_system_prompt_still_forbids_signalling_an_absent_info(self) -> None:
        from app.services.chat.prompts import system_prompt_for

        assert "INTERDIT de signaler qu'une info est absente" in system_prompt_for("v1")

    def test_v1_ouvrage_instruction_has_no_norm_example(self) -> None:
        from app.services.chat.prompts import get_ouvrage_instruction

        text = get_ouvrage_instruction(self.MUR, "v1")
        assert text != ""
        for example in self.NORM_EXAMPLES:
            assert example not in text

    def test_v1_ouvrage_instruction_carries_the_new_line_6(self) -> None:
        from app.services.chat.prompts import get_ouvrage_instruction

        text = get_ouvrage_instruction(self.MUR, "v1")
        assert "uniquement avec les normes écrites dans le contexte pour cette paroi" in text

    def test_v1_ouvrage_instruction_keeps_wall_composition_and_localisation(self) -> None:
        from app.services.chat.prompts import get_ouvrage_instruction

        text = get_ouvrage_instruction(self.MUR, "v1")
        assert "COMPOSITION DES PAROIS EXTÉRIEURES" in text
        assert "UN SEUL bloc Localisation à la fin" in text

    def test_baseline_ouvrage_instruction_keeps_its_historical_norm_line(self) -> None:
        from app.services.chat.prompts import get_ouvrage_instruction

        text = get_ouvrage_instruction(self.MUR, "baseline")
        assert "(tous les DTU : 20.1, 26.1, 25.41, etc.)" in text

    def test_ouvrage_instruction_defaults_to_baseline(self) -> None:
        from app.services.chat.prompts import get_ouvrage_instruction

        text = get_ouvrage_instruction(self.MUR)
        assert "(tous les DTU : 20.1, 26.1, 25.41, etc.)" in text
        assert "uniquement avec les normes écrites dans le contexte pour cette paroi" not in text

    def test_question_matching_no_ouvrage_gives_empty_instruction_in_both_modes(self) -> None:
        from app.services.chat.prompts import get_ouvrage_instruction

        assert get_ouvrage_instruction(self.NO_MATCH, "baseline") == ""
        assert get_ouvrage_instruction(self.NO_MATCH, "v1") == ""


class TestNormesBlockOptionalInV1:
    """In v1 no prompt text presents the final Normes block as mandatory."""

    OLD_ORDER_LINE = "**Localisation** puis **Normes** — rien après"
    V1_ORDER_LINE = (
        "   ORDRE STRICT en fin de réponse : **Localisation**, puis **Normes** "
        "UNIQUEMENT s'il y a au moins une norme à citer (règle d) — rien après. "
        "Une réponse sans bloc Normes est correcte.\n"
    )
    OLD_PARENTHESIS = "(avant Normes)"
    V1_PARENTHESIS = "(avant le bloc Normes s'il y en a un)"

    def test_v1_system_prompt_no_longer_contains_the_old_order_line(self) -> None:
        from app.services.chat.prompts import system_prompt_for

        assert self.OLD_ORDER_LINE not in system_prompt_for("v1")

    def test_v1_system_prompt_carries_the_full_v1_order_line(self) -> None:
        from app.services.chat.prompts import system_prompt_for

        assert self.V1_ORDER_LINE in system_prompt_for("v1")

    def test_v1_localisation_instruction_no_longer_contains_the_old_parenthesis(self) -> None:
        from app.services.chat.prompts import localisation_instruction_for

        assert self.OLD_PARENTHESIS not in localisation_instruction_for("v1")

    def test_v1_localisation_instruction_carries_the_conditional_parenthesis(self) -> None:
        from app.services.chat.prompts import localisation_instruction_for

        assert self.V1_PARENTHESIS in localisation_instruction_for("v1")

    def test_baseline_localisation_instruction_has_the_historical_sha256(self) -> None:
        import hashlib

        from app.services.chat.prompts import localisation_instruction_for

        digest = hashlib.sha256(localisation_instruction_for("baseline").encode("utf-8")).hexdigest()
        assert digest == "dbbf8abbd1f2a6180e3f712f34c7cc7498f4cc1a771ea9367caa899d83ef5300"

    def test_v1_rule_d_is_served_unchanged_up_to_the_order_line(self) -> None:
        import hashlib

        from app.services.chat.prompts import system_prompt_for

        v1 = system_prompt_for("v1")
        rule_d = v1[v1.index("   d) "):v1.index("   ORDRE STRICT")]
        assert len(rule_d) == 448
        assert (
            hashlib.sha256(rule_d.encode("utf-8")).hexdigest()
            == "8081409d5ae90fea0d72f8a234376bc2056986224c2028c1f703542b3d9b4ef4"
        )

    def test_v1_localisation_instruction_differs_from_baseline_only_by_the_parenthesis(
        self,
    ) -> None:
        from app.services.chat.prompts import localisation_instruction_for

        baseline = localisation_instruction_for("baseline")
        v1 = localisation_instruction_for("v1")
        assert baseline.count(self.OLD_PARENTHESIS) == 1
        assert v1.count(self.V1_PARENTHESIS) == 1
        assert v1.split(self.V1_PARENTHESIS) == baseline.split(self.OLD_PARENTHESIS)

    def test_baseline_system_prompt_still_contains_the_old_order_line(self) -> None:
        from app.services.chat.prompts import system_prompt_for

        assert self.OLD_ORDER_LINE in system_prompt_for("baseline")

    def test_v1_localisation_instruction_keeps_dropping_the_block_without_precise_location(
        self,
    ) -> None:
        from app.services.chat.prompts import localisation_instruction_for

        assert (
            "Si aucune localisation PRÉCISE n'est dans le contexte, ne mets pas ce bloc"
            in localisation_instruction_for("v1")
        )
