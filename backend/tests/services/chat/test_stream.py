from mistralai.client.models import UsageInfo

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


class TestStreamContextMergesArticleCopies:
    """j2-contexte-dedup-articles: the legacy builder merges article copies like the graph one."""

    import uuid

    import pytest

    from app.schemas.search import SearchResult

    BODY = (
        "Réglementation thermique\n"
        "Le bâtiment doit respecter la RT 2012 pour l'ensemble des locaux chauffés du lot."
    )
    A1 = "1.1.3.9. " + BODY
    A4 = "4.1.3.11. " + BODY
    X = (
        "2.3.1.1. Enduit monocouche\n"
        "Enduit monocouche gratté de teinte claire sur l'ensemble des façades de la maison."
    )
    SHARED_SENTENCE = "Le bâtiment doit respecter la RT 2012"
    DOC_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
    PROJECT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")

    def _chunk(self, text: str, *, page: int, lot: str, score: float) -> SearchResult:
        from app.schemas.search import SearchResult

        return SearchResult(
            text=text,
            page=page,
            position=0,
            filename="CCTP.pdf",
            document_id=self.DOC_ID,
            project_id=self.PROJECT_ID,
            score=score,
            lot=lot,
            phase="PRO",
            type="CCTP",
        )

    def test_v1_stream_context_contains_a_copied_paragraph_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two copies differing by their article number are rendered once, under a merged header."""
        from app.services.chat.stream import _build_context_and_sources

        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        context, _ = _build_context_and_sources(
            [
                self._chunk(self.A1, page=5, lot="01", score=0.9),
                self._chunk(self.A4, page=46, lot="04", score=0.5),
            ],
            score_threshold=0.40,
            context_max=20000,
            max_sources=5,
        )
        assert context.count(self.SHARED_SENTENCE) == 1
        assert "[CCTP.pdf, p.5 ; aussi : CCTP.pdf, p.46]" in context

    def test_baseline_stream_context_is_byte_identical_to_the_unmerged_render(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Baseline never merges: both copies, historical headers and separators."""
        from app.services.chat.stream import _build_context_and_sources

        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "baseline")
        context, _ = _build_context_and_sources(
            [
                self._chunk(self.A1, page=5, lot="01", score=0.9),
                self._chunk(self.A4, page=46, lot="04", score=0.5),
            ],
            score_threshold=0.40,
            context_max=20000,
            max_sources=5,
        )
        assert context == (
            "\n=== 01 ===\n"
            + "\n---\n"
            + "[CCTP.pdf, p.5]\n"
            + self.A1
            + "\n---\n"
            + "\n=== 04 ===\n"
            + "\n---\n"
            + "[CCTP.pdf, p.46]\n"
            + self.A4
        )

    def test_graph_and_stream_build_the_same_v1_context_from_the_same_results(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both builders render the same merged context and sources above both thresholds."""
        from app.services.chat import graph, stream

        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        results = [
            self._chunk(self.A1, page=5, lot="01", score=0.9),
            self._chunk(self.A4, page=46, lot="04", score=0.6),
            self._chunk(self.X, page=50, lot="04", score=0.7),
        ]
        graph_context, graph_sources = graph._build_context_and_sources(
            results, score_threshold=0.40, context_max=20000, max_sources=5
        )
        stream_context, stream_sources = stream._build_context_and_sources(
            results, score_threshold=0.40, context_max=20000, max_sources=5
        )
        assert stream_context == graph_context
        assert stream_sources == graph_sources
        assert graph_context.count(self.SHARED_SENTENCE) == 1


class TestStreamContextBudgetByScore:
    """j2-budget-ordre-score: under a cut, v1 keeps the best-scored passages on both paths."""

    import uuid

    import pytest

    from app.schemas.search import SearchResult

    HEAD = "HEAD-PASSAGE " + "a" * 87
    MIDDLE = "MIDDLE-PASSAGE " + "b" * 85
    END = "END-PASSAGE " + "c" * 88

    def _results(self) -> list["SearchResult"]:
        from app.schemas.search import SearchResult

        return [
            SearchResult(
                text=text,
                page=page,
                position=position,
                filename="cctp.pdf",
                document_id=self.uuid.UUID("11111111-1111-1111-1111-111111111111"),
                project_id=self.uuid.UUID("22222222-2222-2222-2222-222222222222"),
                score=score,
                lot="02",
                phase="PRO",
                type="CCTP",
            )
            for text, score, page, position in [
                (self.HEAD, 0.45, 1, 0),
                (self.MIDDLE, 0.6, 2, 1),
                (self.END, 0.9, 3, 2),
            ]
        ]

    def test_graph_and_stream_build_the_same_v1_context_when_the_budget_cuts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both builders keep the same best-scored passages and sources under a cut."""
        from app.services.chat import graph, stream

        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "v1")
        graph_context, graph_sources = graph._build_context_and_sources(
            self._results(), score_threshold=0.40, context_max=237, max_sources=5
        )
        stream_context, stream_sources = stream._build_context_and_sources(
            self._results(), score_threshold=0.40, context_max=237, max_sources=5
        )
        assert stream_context == graph_context
        assert stream_sources == graph_sources
        assert "END-PASSAGE" in stream_context

    def test_stream_baseline_cut_still_fills_in_document_order(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Baseline keeps filling in document order: the end of the document is cut."""
        from app.services.chat.stream import _build_context_and_sources

        monkeypatch.setattr("app.core.config.settings.retrieval_mode", "baseline")
        context, sources = _build_context_and_sources(
            self._results(), score_threshold=0.40, context_max=237, max_sources=5
        )
        assert context == (
            "[cctp.pdf, p.1]\n" + self.HEAD + "\n---\n" + "[cctp.pdf, p.2]\n" + self.MIDDLE
        )
        assert [(s.filename, s.page) for s in sources] == [("cctp.pdf", 1), ("cctp.pdf", 2)]


class TestStreamNarrowSearchLimit:
    """j2-nombre-passages: the legacy path applies the same v1 search limit as the graph."""

    import pytest

    NARROW_QUESTION = "Quelle est l'épaisseur de la dalle du garage ?"
    RELATED = ["liée 1", "liée 2", "liée 3", "liée 4"]
    FORCED = [f"forcée {i}" for i in range(7)]

    def _patch_search(self, monkeypatch: pytest.MonkeyPatch, module: object) -> None:
        import uuid

        from app.schemas.search import SearchResult
        from app.services import search as search_service

        forced = self.FORCED

        async def _search_merged(
            *, queries: list[str], limit: int, **_: object
        ) -> list["SearchResult"]:
            prefix = "forced" if queries == forced else "main"
            return [
                SearchResult(
                    text=f"{prefix}-{i} passage de test",
                    page=1,
                    position=i,
                    filename="cctp.pdf",
                    document_id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
                    project_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
                    score=0.9,
                    lot="02",
                    phase="PRO",
                    type="CCTP",
                )
                for i in range(limit)
            ]

        async def _expand(
            _tenant: object, _project: object, results: list["SearchResult"]
        ) -> list["SearchResult"]:
            return results

        async def _enrich(
            _tenant: object,
            _project: object,
            _query: object,
            _question: object,
            results: list["SearchResult"],
        ) -> list["SearchResult"]:
            return results

        monkeypatch.setattr(search_service, "search_merged", _search_merged)
        monkeypatch.setattr(module, "expand_heading_chunks", _expand)
        monkeypatch.setattr(module, "enrich_with_dpgf_quantities", _enrich)
        monkeypatch.setattr(module, "get_forced_related", lambda _query: list(forced))

    async def _count(self, monkeypatch: pytest.MonkeyPatch, module: object, search_limit: int) -> int:
        import uuid

        self._patch_search(monkeypatch, module)
        results = await module._run_search(  # type: ignore[attr-defined]
            tenant_id=uuid.UUID("33333333-3333-3333-3333-333333333333"),
            project_id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
            search_query="épaisseur dalle garage",
            question=self.NARROW_QUESTION,
            related_queries=list(self.RELATED),
            scope="specific",
            search_limit=search_limit,
        )
        return len(results)

    async def test_stream_run_search_scales_main_and_forced_limits_at_10(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Six main and seven forced queries at 10: 12 + 14 results on the legacy path."""
        from app.services.chat import stream

        assert await self._count(monkeypatch, stream, 10) == 26

    async def test_stream_and_graph_run_search_return_the_same_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Both copies of `_run_search` return the same number of results at 10 and at 20."""
        from app.services.chat import graph, stream

        counts = [
            (
                await self._count(monkeypatch, graph, limit),
                await self._count(monkeypatch, stream, limit),
            )
            for limit in (10, 20)
        ]
        assert counts == [(26, 26), (65, 65)]

    async def _recorded_limit(
        self, db: "AsyncSession", tenant: "Tenant", monkeypatch: pytest.MonkeyPatch, mode: str
    ) -> list[int]:
        from app.services.chat import stream
        from app.services.chat.prompts import classify_scope
        from tests.services.chat.test_graph import _project_and_user

        assert classify_scope(self.NARROW_QUESTION) == "specific"
        monkeypatch.setattr("app.core.config.settings.retrieval_mode", mode)
        monkeypatch.setattr("app.core.config.settings.v1_search_limit", 10)
        recorded: list[int] = []

        async def _rewrite(
            _question: str, _history: object, usage_sink: object = None
        ) -> tuple[str, list[str], str, str, str]:
            return ("épaisseur dalle garage", [], "specific", "none", "none")

        async def _run_search(*, search_limit: int, **_: object) -> list[object]:
            recorded.append(search_limit)
            raise RuntimeError("search stopped by the test after recording its limit")

        monkeypatch.setattr(stream, "rewrite_query", _rewrite)
        monkeypatch.setattr(stream, "_run_search", _run_search)
        project, user = await _project_and_user(db, tenant)
        lines = [
            line
            async for line in stream.chat_stream(
                db,
                tenant_id=tenant.id,
                project_id=project.id,
                user_id=user.id,
                question=self.NARROW_QUESTION,
            )
        ]
        assert lines[-1] == "data: [DONE]\n\n"
        return recorded

    async def test_stream_v1_narrow_search_uses_the_configured_limit(
        self, db: "AsyncSession", tenant_a: "Tenant", monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under v1 the legacy narrow-scope search receives the configured limit."""
        assert await self._recorded_limit(db, tenant_a, monkeypatch, "v1") == [10]

    async def test_stream_baseline_narrow_search_ignores_the_configured_limit(
        self, db: "AsyncSession", tenant_a: "Tenant", monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under baseline the legacy narrow-scope search keeps 20 whatever is configured."""
        assert await self._recorded_limit(db, tenant_a, monkeypatch, "baseline") == [20]
