"""Behaviour of the pure BM25-style sparse vector builder used by hybrid search."""

import pytest

from app.services.sparse import (
    document_sparse_vector,
    query_sparse_vector,
    to_hybrid_point,
    tokenize,
)

DTU_INDEX = 149479884
DTU_VERSION_INDEX = 4056836807
BETON_INDEX = 3775319405


def test_document_and_query_vectors_of_dtu_20_1_share_the_dtu_and_version_indices() -> None:
    document = document_sparse_vector("Prescriptions du DTU 20.1 pour la maçonnerie")
    query = query_sparse_vector("DTU 20.1")

    assert query is not None
    common = set(document.indices) & set(query.indices)
    assert {DTU_INDEX, DTU_VERSION_INDEX} <= common


def test_query_vector_gives_1_0_to_each_distinct_token_even_when_repeated() -> None:
    query = query_sparse_vector("dtu dtu 20.1 dtu")

    assert query is not None
    assert query.indices == sorted([DTU_INDEX, DTU_VERSION_INDEX])
    assert query.values == [1.0, 1.0]


def test_single_token_document_weighs_1_688_and_a_repeated_token_weighs_1_907() -> None:
    once = document_sparse_vector("béton")
    twice = document_sparse_vector("béton béton")

    assert once.indices == [BETON_INDEX]
    assert once.values == [pytest.approx(1.688, abs=1e-3)]
    assert twice.indices == [BETON_INDEX]
    assert twice.values == [pytest.approx(1.907, abs=1e-3)]
    assert twice.values[0] < 2 * once.values[0]


def test_same_text_gives_the_same_vector_and_dtu_has_the_literal_index() -> None:
    first = document_sparse_vector("DTU 20.1")
    second = document_sparse_vector("DTU 20.1")

    assert first == second
    assert DTU_INDEX in first.indices


def test_reference_codes_stay_whole_when_tokenised() -> None:
    assert tokenize("DTU 20.1") == ["dtu", "20.1"]
    assert tokenize("C15-100") == ["c15-100"]
    assert tokenize("NF P10-201-1") == ["nf", "p10-201-1"]


def test_dtu_20_shares_only_dtu_with_a_document_containing_only_dtu_20_1() -> None:
    document = document_sparse_vector("DTU 20.1")
    query = query_sparse_vector("DTU 20")

    assert query is not None
    assert set(document.indices) & set(query.indices) == {DTU_INDEX}


def test_accents_and_case_are_folded_and_plurals_are_not_stemmed() -> None:
    assert tokenize("Étanchéité") == tokenize("etancheite") == ["etancheite"]
    assert tokenize("maçonneries") == ["maconneries"]
    assert tokenize("maçonnerie") == ["maconnerie"]
    assert tokenize("maçonneries") != tokenize("maçonnerie")


def test_trailing_punctuation_is_removed_and_decimal_comma_is_kept() -> None:
    assert tokenize("béton.") == ["beton"]
    assert tokenize("1,33 m / TN") == ["1,33", "m", "tn"]


@pytest.mark.parametrize("text", ["", "   ", "...", "!? , - /"])
def test_empty_or_punctuation_only_text_gives_empty_document_vector_and_no_query_vector(
    text: str,
) -> None:
    document = document_sparse_vector(text)

    assert document.indices == []
    assert document.values == []
    assert query_sparse_vector(text) is None


def test_document_vector_indices_are_unique_and_sorted_for_a_multi_token_text() -> None:
    vector = document_sparse_vector("dtu 20.1 béton c15-100 nf p10-201-1 béton dtu")

    assert vector.indices == sorted(set(vector.indices))
    assert len(vector.indices) == len(vector.values)
    assert len(vector.indices) == 6


def test_hybrid_point_keeps_dense_sparse_payload_and_id_and_defaults_to_empty_sparse() -> None:
    payload: dict[str, object] = {"text": "béton", "tenant_id": "t-1", "page": 3}

    point = to_hybrid_point("p-1", [0.1, 0.2, 0.3], payload)

    assert point.id == "p-1"
    assert point.payload == {"text": "béton", "tenant_id": "t-1", "page": 3}
    assert isinstance(point.vector, dict)
    assert point.vector["dense"] == [0.1, 0.2, 0.3]
    assert point.vector["sparse"].indices == [BETON_INDEX]

    without_text = to_hybrid_point(7, [0.5], {"tenant_id": "t-1"})

    assert without_text.id == 7
    assert without_text.payload == {"tenant_id": "t-1"}
    assert isinstance(without_text.vector, dict)
    assert without_text.vector["sparse"].indices == []


def test_two_distinct_tokens_sharing_a_hash_index_have_their_weights_summed() -> None:
    colliding = document_sparse_vector("a46307 a65336")
    single = document_sparse_vector("a46307")

    assert colliding.indices == [2734767135]
    assert single.indices == [2734767135]
    assert colliding.values[0] == pytest.approx(2 * single.values[0] * 0.9995, rel=5e-3)


def test_colliding_tokens_weigh_the_hand_computed_sum_of_two_single_occurrences() -> None:
    colliding = document_sparse_vector("a46307 a65336")

    assert colliding.indices == [2734767135]
    assert colliding.values == [pytest.approx(3.366, abs=2e-3)]
