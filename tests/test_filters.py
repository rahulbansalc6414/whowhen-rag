from whowhen import Condition, Filters, Sort

F = Filters(conditions=[
    Condition("modified_on", ">=", "2026-11-09"),
    Condition("modified_on", "<", "2026-11-16"),
    Condition("owner", "in", ["a@x.com", "b@x.com"]),
], sort=Sort("modified_on", descending=True))


def test_to_sql():
    where, params = F.to_sql()
    assert where == '"modified_on" >= %s AND "modified_on" < %s AND "owner" IN (%s, %s)'
    assert params == ["2026-11-09", "2026-11-16", "a@x.com", "b@x.com"]
    assert F.order_by_sql() == 'ORDER BY "modified_on" DESC'


def test_to_sql_sqlite_and_dotted_and_quotes():
    f = Filters(conditions=[Condition('meta.weird"col', "=", 1)])
    assert f.to_sql("?") == ('"meta"."weird""col" = ?', [1])


def test_empty():
    f = Filters()
    assert f.to_sql() == ("", []) and f.order_by_sql() == ""
    assert f.to_chroma() is None and f.to_qdrant() is None


def test_to_chroma():
    assert F.to_chroma() == {"$and": [
        {"modified_on": {"$gte": "2026-11-09"}},
        {"modified_on": {"$lt": "2026-11-16"}},
        {"owner": {"$in": ["a@x.com", "b@x.com"]}},
    ]}
    assert Filters(conditions=[Condition("owner", "=", "a")]).to_chroma() == {"owner": {"$eq": "a"}}


def test_to_qdrant_merges_ranges():
    assert F.to_qdrant() == {"must": [
        {"key": "modified_on", "range": {"gte": "2026-11-09", "lt": "2026-11-16"}},
        {"key": "owner", "match": {"any": ["a@x.com", "b@x.com"]}},
    ]}


def test_to_dict_roundtrips_to_json():
    import json
    json.dumps(F.to_dict())
