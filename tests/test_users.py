from fixtures import standard_graph, graph, users, groups, session, permissions  # noqa


def test_basic_metadata(standard_graph, session, users, groups, permissions):  # noqa
    """ Test basic metadata functionality. """

    graph = standard_graph  # noqa

    assert len(users["zorkian@a.co"].my_metadata()) == 0, "No metadata yet"

    # Test setting "foo" to 1 works, and we get "1" back (metadata is defined as strings)
    users["zorkian@a.co"].set_metadata("foo", 1)
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 1, "One metadata item"
    assert [d.data_value for d in md if d.data_key == "foo"] == ["1"], "foo is 1"

    users["zorkian@a.co"].set_metadata("bar", "test string")
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 2, "Two metadata items"
    assert [d.data_value for d in md if d.data_key == "bar"] == ["test string"], \
        "bar is test string"

    users["zorkian@a.co"].set_metadata("foo", "test2")
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 2, "Two metadata items"
    assert [d.data_value for d in md if d.data_key == "foo"] == ["test2"], "foo is test2"

    users["zorkian@a.co"].set_metadata("foo", None)
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 1, "One metadata item"
    assert [d.data_value for d in md if d.data_key == "foo"] == [], "foo is not found"

    users["zorkian@a.co"].set_metadata("baz", None)
    md = users["zorkian@a.co"].my_metadata()
    assert len(md) == 1, "One metadata item"


# TODO(herb): test graph when user is disabled ; this test isn't trivial if we
# want to be able to include FE code to do the disable (we need a user with
# admin perms but adding those to fixtures isn't straightforward and adding it
# one-off is a bit hacky ; need to rethink how those perms exist in test,
# specifically what test_sync_db_default_group() assumes
