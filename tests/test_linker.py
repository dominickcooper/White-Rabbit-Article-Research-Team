from white_rabbit.publishing.substack_source_linker import Source, insert_links


def test_existing_linker_inserts_first_use_only():
    md = "Flock Safety appears here. Later Flock Safety appears again."
    linked, success, missing = insert_links(md, [Source("1", "Flock Safety", "https://example.com/flock")])
    assert linked.count("https://example.com/flock") == 1
    assert len(success) == 1
    assert missing == []
