from mistralai.models import UsageInfo

from app.services.chat.stream import _usage_event, _usage_leg


class TestUsageLeg:
    def test_none_usage_is_all_zeros(self) -> None:
        assert _usage_leg(None) == {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }

    def test_full_usage_computes_cost_from_both_token_counts(self) -> None:
        usage = UsageInfo(
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
            total_tokens=1_500_000,
        )
        assert _usage_leg(usage) == {
            "input_tokens": 1_000_000,
            "output_tokens": 500_000,
            "cost_usd": 1.25,
        }

    def test_none_prompt_tokens_on_a_present_usage_counts_as_zero_input(self) -> None:
        usage = UsageInfo(
            prompt_tokens=None,
            completion_tokens=2_000_000,
            total_tokens=2_000_000,
        )
        assert _usage_leg(usage) == {
            "input_tokens": 0,
            "output_tokens": 2_000_000,
            "cost_usd": 3.0,
        }


class TestUsageEvent:
    def test_both_legs_none_zeroes_rewrite_generation_and_total(self) -> None:
        assert _usage_event(None, None) == {
            "rewrite": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            "generation": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
            "total": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        }

    def test_only_generation_set_leaves_rewrite_zeroed_and_total_equal_to_generation(
        self,
    ) -> None:
        generation = UsageInfo(
            prompt_tokens=200_000,
            completion_tokens=100_000,
            total_tokens=300_000,
        )
        event = _usage_event(None, generation)
        assert event["rewrite"] == {
            "input_tokens": 0,
            "output_tokens": 0,
            "cost_usd": 0.0,
        }
        assert event["generation"] == {
            "input_tokens": 200_000,
            "output_tokens": 100_000,
            "cost_usd": 0.25,
        }
        assert event["total"] == {
            "input_tokens": 200_000,
            "output_tokens": 100_000,
            "cost_usd": 0.25,
        }

    def test_both_legs_set_sums_elementwise_into_total(self) -> None:
        rewrite = UsageInfo(
            prompt_tokens=1_000_000,
            completion_tokens=500_000,
            total_tokens=1_500_000,
        )
        generation = UsageInfo(
            prompt_tokens=200_000,
            completion_tokens=100_000,
            total_tokens=300_000,
        )
        event = _usage_event(rewrite, generation)
        assert event["total"] == {
            "input_tokens": 1_200_000,
            "output_tokens": 600_000,
            "cost_usd": 1.5,
        }


class TestSystemPromptByMode:
    """The assembled system message follows `settings.retrieval_mode`, read at call time."""

    import pytest

    BROAD_QUESTION = "Quels sont les lots du projet ?"
    WALL_QUESTION = "Quelle est la composition du mur extérieur ?"
    FOUNDATION_QUESTION = "Comment sont réalisées les fondations ?"

    @staticmethod
    def _system_content(question: str, scope: str) -> str:
        from app.services.chat.stream import _build_mistral_messages

        messages = _build_mistral_messages(
            context_block="",
            question=question,
            recent_messages=[],
            scope=scope,
            structured="none",
            schema_flag="none",
            sources=[],
        )
        return messages[0]["content"]

    @staticmethod
    def _graph_system_content(question: str, scope: str) -> str:
        from app.services.chat.graph import _build_mistral_messages

        messages = _build_mistral_messages(
            context_block="",
            question=question,
            recent_messages=[],
            scope=scope,
            structured="none",
            schema_flag="none",
            sources=[],
        )
        return messages[0]["content"]

    def test_baseline_system_message_keeps_the_pre_brick_fingerprint(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In baseline mode the three reference questions hash to the historical sha256."""
        import hashlib

        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "baseline")
        cases = [
            (
                "broad",
                self.BROAD_QUESTION,
                "749529cff64a1190a7863fcb6479d57c88b83e4a857e5be19420701a2b24ddb3",
            ),
            (
                "specific",
                self.WALL_QUESTION,
                "d8ccc061ad696b59d8fe43438dc7cb8eedf01bbcbfeff3723839d7d093a8b525",
            ),
            (
                "specific",
                self.FOUNDATION_QUESTION,
                "5d1e603c98ecd1758822d7383cb02e51cfedf2f4f4585fdc290881d645c8122e",
            ),
        ]
        digests = [
            hashlib.sha256(self._system_content(question, scope).encode("utf-8")).hexdigest()
            for scope, question, _ in cases
        ]
        assert digests == [expected for _, _, expected in cases]

    def test_v1_wall_question_carries_the_norms_rule_and_drops_applicable_norms(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In v1 mode the wall question gets the sourced-norms rule, not the old request."""
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        content = self._system_content(self.WALL_QUESTION, "specific")
        assert "écrites dans le contexte ET rattachées à l'ouvrage de la question" in content
        assert "DTU/NF EN applicables" not in content

    def test_v1_wall_question_carries_new_line_6_and_no_norm_example(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In v1 mode the wall instruction has the new line 6 and no example norm."""
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        content = self._system_content(self.WALL_QUESTION, "specific")
        assert "uniquement avec les normes écrites dans le contexte pour cette paroi" in content
        for example in ("tous les DTU", "20.1", "26.1", "25.41"):
            assert example not in content

    def test_v1_system_message_matches_the_langgraph_path_on_reference_questions(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In v1 mode the stream path and the LangGraph path assemble identical system messages."""
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        cases = [
            ("broad", self.BROAD_QUESTION),
            ("specific", self.WALL_QUESTION),
            ("specific", self.FOUNDATION_QUESTION),
        ]
        stream_contents = [self._system_content(question, scope) for scope, question in cases]
        graph_contents = [self._graph_system_content(question, scope) for scope, question in cases]
        assert stream_contents == graph_contents

    def test_mode_is_read_at_call_time(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Two successive calls, baseline then v1, return different system messages."""
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "baseline")
        baseline_content = self._system_content(self.WALL_QUESTION, "specific")
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        v1_content = self._system_content(self.WALL_QUESTION, "specific")
        assert baseline_content != v1_content


class TestNormesBlockOptionalAssembled:
    """In v1 the assembled system message never presents the Normes block as mandatory."""

    import pytest

    BROAD_QUESTION = "Quels sont les lots du projet ?"
    WALL_QUESTION = "Quelle est la composition du mur extérieur ?"
    FOUNDATION_QUESTION = "Comment sont réalisées les fondations ?"
    OLD_ORDER_LINE = "**Localisation** puis **Normes** — rien après"
    V1_ORDER_LINE = (
        "   ORDRE STRICT en fin de réponse : **Localisation**, puis **Normes** "
        "UNIQUEMENT s'il y a au moins une norme à citer (règle d) — rien après. "
        "Une réponse sans bloc Normes est correcte.\n"
    )
    OLD_PARENTHESIS = "(avant Normes)"
    V1_PARENTHESIS = "(avant le bloc Normes s'il y en a un)"

    @staticmethod
    def _system_content(question: str, scope: str) -> str:
        from app.services.chat.stream import _build_mistral_messages

        messages = _build_mistral_messages(
            context_block="",
            question=question,
            recent_messages=[],
            scope=scope,
            structured="none",
            schema_flag="none",
            sources=[],
        )
        return messages[0]["content"]

    def test_v1_foundation_question_drops_the_old_order_line_and_parenthesis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In v1 mode neither unconditional mention of the Normes block is served."""
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        content = self._system_content(self.FOUNDATION_QUESTION, "specific")
        assert self.OLD_ORDER_LINE not in content
        assert self.OLD_PARENTHESIS not in content

    def test_v1_foundation_question_carries_the_conditional_order_line_and_parenthesis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In v1 mode the order line and the localisation parenthesis are conditional."""
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        content = self._system_content(self.FOUNDATION_QUESTION, "specific")
        assert self.V1_ORDER_LINE in content
        assert self.V1_PARENTHESIS in content

    def test_v1_wall_question_drops_the_old_order_line_and_parenthesis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In v1 mode a question matching an ouvrage pattern is served the same way."""
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        content = self._system_content(self.WALL_QUESTION, "specific")
        assert self.OLD_ORDER_LINE not in content
        assert self.OLD_PARENTHESIS not in content

    def test_baseline_foundation_question_keeps_the_old_order_line_and_parenthesis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In baseline mode both historical mentions are still served."""
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "baseline")
        content = self._system_content(self.FOUNDATION_QUESTION, "specific")
        assert self.OLD_ORDER_LINE in content
        assert self.OLD_PARENTHESIS in content

    def test_v1_broad_question_carries_the_order_line_and_no_localisation_parenthesis(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """In v1 mode a broad question keeps its exemption and gets no localisation text."""
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        content = self._system_content(self.BROAD_QUESTION, "broad")
        assert self.V1_ORDER_LINE in content
        assert "PAS de bloc Localisation ni Normes pour les questions générales" in content
        assert self.OLD_PARENTHESIS not in content
        assert self.V1_PARENTHESIS not in content
