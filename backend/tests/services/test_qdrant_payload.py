"""The single Qdrant chunk-payload constructor — its whole contract.

Two write paths used to build this payload by hand, and they had drifted: one
emitted `doc_type` where the other emitted `type`, and a re-edited chunk lost
`ingested_at`, `heading_prefix` and `char_count`. These cases pin the shape,
key for key and in order, so that both callers can only produce it.

`build_chunk_payload` is synchronous, and `ChunkPayloadFields.from_chunk` is the
one and only place a nullable `Chunk` column is normalised — a `None` reaching
the payload raises at search time on `SearchResult.keywords: list[str]`.
"""

import uuid
from datetime import UTC, datetime

from app.models.chunk import Chunk
from app.services.qdrant_payload import ChunkPayloadFields, build_chunk_payload

TENANT_ID = uuid.UUID("11111111-1111-1111-1111-111111111111")
PROJECT_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")
DOCUMENT_ID = uuid.UUID("33333333-3333-3333-3333-333333333333")


def _fields(**overrides: object) -> ChunkPayloadFields:
    """A fully populated set of fields, as the ingestion path builds them."""
    values: dict[str, object] = {
        "text": "Les cloisons sont doublees en plaque de platre.",
        "page": 4,
        "position": 12,
        "parent_sections": ["2. Second oeuvre", "2.3 Cloisons"],
        "section_title": "2.3.1 Doublage",
        "heading_prefix": "2.3.1",
        "content_type": "prescription",
        "keywords": ["doublage", "NF DTU 25.41"],
        "localisation": ["R+1"],
        "char_count": 46,
        "lot": "",
    }
    values.update(overrides)
    return ChunkPayloadFields(**values)  # type: ignore[arg-type]


def _payload(fields: ChunkPayloadFields | None = None, **overrides: object) -> dict[str, object]:
    kwargs: dict[str, object] = {
        "tenant_id": TENANT_ID,
        "project_id": PROJECT_ID,
        "document_id": DOCUMENT_ID,
        "doc_type": "CCTP",
        "filename": "cctp-lot-02.pdf",
        "phase": "PRO",
        "document_lot": "LOT 01 - Gros oeuvre",
        "ingested_at": None,
    }
    kwargs.update(overrides)
    return build_chunk_payload(fields if fields is not None else _fields(), **kwargs)  # type: ignore[arg-type]


class TestPayloadShape:
    def test_payload_carries_the_key_type_and_never_doc_type(self) -> None:
        payload = _payload(doc_type="CCTP")

        assert payload["type"] == "CCTP"
        assert "doc_type" not in payload

    def test_payload_carries_exactly_the_seventeen_expected_keys_in_order(self) -> None:
        payload = _payload()

        assert list(payload.keys()) == [
            "tenant_id",
            "project_id",
            "document_id",
            "type",
            "lot",
            "phase",
            "filename",
            "page",
            "position",
            "text",
            "heading_prefix",
            "section_title",
            "parent_sections",
            "content_type",
            "keywords",
            "char_count",
            "localisation",
        ]
        assert payload == {
            "tenant_id": "11111111-1111-1111-1111-111111111111",
            "project_id": "22222222-2222-2222-2222-222222222222",
            "document_id": "33333333-3333-3333-3333-333333333333",
            "type": "CCTP",
            "lot": "LOT 01 - Gros oeuvre",
            "phase": "PRO",
            "filename": "cctp-lot-02.pdf",
            "page": 4,
            "position": 12,
            "text": "Les cloisons sont doublees en plaque de platre.",
            "heading_prefix": "2.3.1",
            "section_title": "2.3.1 Doublage",
            "parent_sections": ["2. Second oeuvre", "2.3 Cloisons"],
            "content_type": "prescription",
            "keywords": ["doublage", "NF DTU 25.41"],
            "char_count": 46,
            "localisation": ["R+1"],
        }

    def test_ingested_at_is_written_in_iso_when_given_and_the_key_is_absent_otherwise(
        self,
    ) -> None:
        with_date = _payload(ingested_at=datetime(2026, 9, 6, 14, 30, tzinfo=UTC))
        without_date = _payload(ingested_at=None)

        assert with_date["ingested_at"] == "2026-09-06T14:30:00+00:00"
        assert "ingested_at" not in without_date


class TestPayloadBusinessRules:
    def test_chunk_lot_takes_precedence_over_the_document_lot(self) -> None:
        payload = _payload(
            _fields(lot="LOT 03 - Charpente"), document_lot="LOT 01 - Gros oeuvre"
        )

        assert payload["lot"] == "LOT 03 - Charpente"

    def test_document_lot_is_used_when_the_chunk_carries_none(self) -> None:
        payload = _payload(_fields(lot=""), document_lot="LOT 01 - Gros oeuvre")

        assert payload["lot"] == "LOT 01 - Gros oeuvre"

    def test_diagnostic_types_keep_only_norm_keywords_while_an_ordinary_type_keeps_them_all(
        self,
    ) -> None:
        fields = _fields(keywords=["NF P 03-001", "DTU 20.1", "amiante", "flocage"])

        amiante = _payload(fields, doc_type="rapport_amiante")
        sol = _payload(fields, doc_type="etude_sol")
        cctp = _payload(fields, doc_type="CCTP")

        assert amiante["keywords"] == ["NF P 03-001", "DTU 20.1"]
        assert sol["keywords"] == ["NF P 03-001", "DTU 20.1"]
        assert cctp["keywords"] == ["NF P 03-001", "DTU 20.1", "amiante", "flocage"]

    def test_etude_thermique_gets_the_thermal_filter_not_the_diagnostic_one(self) -> None:
        fields = _fields(keywords=["isolation thermique", "Ug = 1.1", "NF EN 12831", "Isover"])

        payload = _payload(fields, doc_type="etude_thermique")

        assert payload["keywords"] == ["isolation thermique", "Ug = 1.1", "NF EN 12831"]

    def test_the_thermal_filter_keeps_the_vocabulary_the_ingestion_one_keeps(self) -> None:
        fields = _fields(keywords=["polystyrène", "C25/30", "EI 60", "Isover"])

        payload = _payload(fields, doc_type="etude_thermique")

        assert payload["keywords"] == ["polystyrène", "C25/30", "EI 60"]

    def test_tenant_id_written_is_the_one_passed_as_a_parameter_as_a_string(self) -> None:
        payload = _payload(tenant_id=uuid.UUID("44444444-4444-4444-4444-444444444444"))

        assert payload["tenant_id"] == "44444444-4444-4444-4444-444444444444"


class TestFromChunk:
    def test_from_chunk_normalises_every_null_column_and_never_yields_none(self) -> None:
        chunk = Chunk(
            document_id=DOCUMENT_ID,
            text="Reprise du chunk apres edition.",
            page=2,
            position=5,
        )

        fields = ChunkPayloadFields.from_chunk(chunk)

        assert fields.text == "Reprise du chunk apres edition."
        assert fields.page == 2
        assert fields.position == 5
        assert fields.lot == ""
        assert fields.heading_prefix == ""
        assert fields.section_title == ""
        assert fields.content_type == ""
        assert fields.parent_sections == []
        assert fields.keywords == []
        assert fields.localisation == []
        assert fields.char_count == 0

    def test_the_diagnostic_filter_needs_the_norm_prefix_to_stand_alone(self) -> None:
        """The space the norm pattern requires, which no other case exercises.

        `^(?:dtu|nf|en)\\s` and a paraphrase without the `\\s` agree on every
        fixture in this file — "enduit monocouche" is what separates them, and
        an unanchored paraphrase keeps it.
        """
        fields = _fields(keywords=["NF P 03-001", "enduit monocouche", "amiante"])

        payload = _payload(fields, doc_type="rapport_amiante")

        assert payload["keywords"] == ["NF P 03-001"]
