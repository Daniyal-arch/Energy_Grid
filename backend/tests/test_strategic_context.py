from app.strategic_context import ASPECTS, DATASETS, get_context


def test_full_context_exposes_all_lenses_and_datasets():
    context = get_context()

    assert context["aspects"] == ASPECTS
    assert context["datasets"] == DATASETS
    assert all(dataset["url"].startswith("https://") for dataset in context["datasets"])


def test_context_filters_by_aspect():
    context = get_context("dependencies")

    assert [aspect["id"] for aspect in context["aspects"]] == ["dependencies"]
    expected = set(context["aspects"][0]["dataset_ids"])
    assert {dataset["id"] for dataset in context["datasets"]} == expected


def test_context_searches_catalog_when_aspect_is_not_a_lens():
    context = get_context("gas")

    assert context["aspects"] == []
    assert "bnetza_gas_status" in {dataset["id"] for dataset in context["datasets"]}
    assert get_context("not-a-real-source")["datasets"] == []


def test_context_limit_is_bounded():
    assert len(get_context(limit=2)["datasets"]) == 2
    assert len(get_context(limit=0)["datasets"]) == 1
