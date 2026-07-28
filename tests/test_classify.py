from pgchat.safety.classify import classify_sql, classify_tool


def test_select_is_read():
    assert classify_sql("SELECT * FROM users").risk == "read"


def test_delete_without_where_is_destructive():
    c = classify_sql("DELETE FROM users")
    assert c.risk == "destructive"
    assert not c.blocked


def test_delete_with_where_is_write():
    assert classify_sql("DELETE FROM users WHERE id = 1").risk == "write"


def test_drop_database_blocked():
    c = classify_sql("DROP DATABASE production")
    assert c.blocked
    assert c.risk == "destructive"


def test_kill_query_is_admin():
    assert classify_tool("kill_query").risk == "admin"


def test_check_health_is_read():
    assert classify_tool("check_health").risk == "read"
