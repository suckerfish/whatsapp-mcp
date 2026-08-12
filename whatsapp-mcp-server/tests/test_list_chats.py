"""Regression tests for list_chats / get_chat.

The previous SQL referenced messages.* in the SELECT but only added the
LEFT JOIN messages clause when include_last_message=True, so calling
list_chats(include_last_message=False) errored out with
"no such column: messages.content" and silently returned [].
"""

import sqlite3

import pytest

import whatsapp


def _make_messages_db(path):
    """Create a minimal messages.db that matches the real bridge schema."""
    conn = sqlite3.connect(path)
    cursor = conn.cursor()
    cursor.executescript(
        """
        CREATE TABLE chats (
            jid TEXT PRIMARY KEY,
            name TEXT,
            last_message_time TIMESTAMP
        );
        CREATE TABLE messages (
            id TEXT,
            chat_jid TEXT,
            sender TEXT,
            content TEXT,
            timestamp TIMESTAMP,
            is_from_me BOOLEAN,
            media_type TEXT,
            filename TEXT,
            url TEXT,
            media_key BLOB,
            file_sha256 BLOB,
            file_enc_sha256 BLOB,
            file_length INTEGER,
            quoted_message_id TEXT,
            PRIMARY KEY (id, chat_jid),
            FOREIGN KEY (chat_jid) REFERENCES chats(jid)
        );
        """
    )
    cursor.execute(
        "INSERT INTO chats (jid, name, last_message_time) VALUES (?, ?, ?)",
        ("1234567890@s.whatsapp.net", "Alice", "2024-01-15 10:30:00+00:00"),
    )
    cursor.execute(
        """INSERT INTO messages
           (id, chat_jid, sender, content, timestamp, is_from_me)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            "msg1",
            "1234567890@s.whatsapp.net",
            "1234567890",
            "hello world",
            "2024-01-15 10:30:00+00:00",
            0,
        ),
    )
    conn.commit()
    conn.close()


@pytest.fixture
def messages_db(tmp_path, monkeypatch):
    db_path = tmp_path / "messages.db"
    _make_messages_db(str(db_path))
    monkeypatch.setattr(whatsapp, "MESSAGES_DB_PATH", str(db_path))
    return db_path


def test_list_chats_with_last_message(messages_db):
    """Default behavior: include the joined last_message fields."""
    chats = whatsapp.list_chats(limit=10)
    assert len(chats) == 1
    assert chats[0]["jid"] == "1234567890@s.whatsapp.net"
    assert chats[0]["name"] == "Alice"
    assert chats[0]["last_message"] == "hello world"
    assert chats[0]["last_sender"] == "1234567890"


def test_list_chats_without_last_message(messages_db):
    """Regression: include_last_message=False must not error and must
    still return the chat row without the last message's content."""
    chats = whatsapp.list_chats(limit=10, include_last_message=False)
    assert len(chats) == 1
    assert chats[0]["jid"] == "1234567890@s.whatsapp.net"
    assert chats[0]["name"] == "Alice"
    assert chats[0]["last_message"] is None
    assert chats[0]["last_sender"] is None
    # is_from_me is always joined — the unread flag is derived from it.
    assert chats[0]["last_is_from_me"] == 0


def test_list_chats_query_filter_with_include_last_message_false(messages_db):
    """Filter by query while not including the last message — both code paths
    should compose cleanly."""
    chats = whatsapp.list_chats(query="Alice", include_last_message=False)
    assert len(chats) == 1
    assert chats[0]["name"] == "Alice"

    chats = whatsapp.list_chats(query="Bob", include_last_message=False)
    assert chats == []


def test_get_chat_with_last_message(messages_db):
    chat = whatsapp.get_chat("1234567890@s.whatsapp.net")
    assert chat is not None
    assert chat["name"] == "Alice"
    assert chat["last_message"] == "hello world"


def test_get_chat_without_last_message(messages_db):
    """Regression: same bug existed in get_chat."""
    chat = whatsapp.get_chat("1234567890@s.whatsapp.net", include_last_message=False)
    assert chat is not None
    assert chat["name"] == "Alice"
    assert chat["last_message"] is None
    assert chat["last_sender"] is None
    assert chat["last_is_from_me"] == 0


def test_get_chat_missing_jid_returns_none(messages_db):
    assert whatsapp.get_chat("nonexistent@s.whatsapp.net") is None
    assert whatsapp.get_chat("nonexistent@s.whatsapp.net", include_last_message=False) is None


def test_get_contact_chats_returns_each_chat_once_with_last_message(messages_db):
    conn = sqlite3.connect(messages_db)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chats (jid, name, last_message_time) VALUES (?, ?, ?)",
        ("group-1@g.us", "Group", "2024-01-15 10:40:00+00:00"),
    )
    cursor.executemany(
        """INSERT INTO messages
           (id, chat_jid, sender, content, timestamp, is_from_me)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            (
                "group-msg-1",
                "group-1@g.us",
                "1234567890@s.whatsapp.net",
                "contact's earlier group message",
                "2024-01-15 10:35:00+00:00",
                0,
            ),
            (
                "group-msg-2",
                "group-1@g.us",
                "1234567890@s.whatsapp.net",
                "contact's later group message",
                "2024-01-15 10:36:00+00:00",
                0,
            ),
            (
                "group-last",
                "group-1@g.us",
                "9999999999@s.whatsapp.net",
                "actual chat last message",
                "2024-01-15 10:40:00+00:00",
                0,
            ),
        ],
    )
    conn.commit()
    conn.close()

    chats = whatsapp.get_contact_chats("1234567890@s.whatsapp.net")
    group_chats = [chat for chat in chats if chat["jid"] == "group-1@g.us"]

    assert len(group_chats) == 1
    assert group_chats[0]["last_message"] == "actual chat last message"
    assert group_chats[0]["last_sender"] == "9999999999@s.whatsapp.net"


def _make_whatsmeow_db(path):
    """Minimal whatsapp.db with the contact store the resolver reads."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE whatsmeow_contacts (
            our_jid TEXT,
            their_jid TEXT,
            first_name TEXT,
            full_name TEXT,
            push_name TEXT,
            business_name TEXT
        );
        """
    )
    conn.executemany(
        """INSERT INTO whatsmeow_contacts
           (our_jid, their_jid, first_name, full_name, push_name, business_name)
           VALUES (?, ?, ?, ?, ?, ?)""",
        [
            ("me@s.whatsapp.net", "14085551234@s.whatsapp.net", "", "Jane Doe", "Janey", ""),
            ("me@s.whatsapp.net", "14085559999@s.whatsapp.net", "", "", "Pushy", ""),
        ],
    )
    conn.commit()
    conn.close()


@pytest.fixture
def contacts_db(tmp_path, monkeypatch):
    db_path = tmp_path / "whatsapp.db"
    _make_whatsmeow_db(str(db_path))
    monkeypatch.setattr(whatsapp, "WHATSMEOW_DB_PATH", str(db_path))
    return db_path


def _add_chat(db, jid, name, ts="2024-01-16 09:00:00+00:00"):
    conn = sqlite3.connect(db)
    conn.execute("INSERT INTO chats (jid, name, last_message_time) VALUES (?, ?, ?)", (jid, name, ts))
    conn.commit()
    conn.close()


def test_numeric_chat_name_resolves_to_contact(messages_db, contacts_db):
    """The bug: chats.name caches the bare number and never backfills from
    the contact store, so the chat displays as digits."""
    _add_chat(messages_db, "14085551234@s.whatsapp.net", "14085551234")

    chats = whatsapp.list_chats(query="14085551234")
    assert len(chats) == 1
    assert chats[0]["name"] == "Jane Doe"


def test_resolution_falls_back_to_push_name(messages_db, contacts_db):
    _add_chat(messages_db, "14085559999@s.whatsapp.net", "14085559999")

    chat = whatsapp.get_chat("14085559999@s.whatsapp.net")
    assert chat["name"] == "Pushy"


def test_real_cached_name_is_not_overwritten(messages_db, contacts_db):
    """A non-numeric cached name wins even when a contact record exists."""
    _add_chat(messages_db, "14085551234@s.whatsapp.net", "Custom Label")

    chat = whatsapp.get_chat("14085551234@s.whatsapp.net")
    assert chat["name"] == "Custom Label"


def test_unknown_number_keeps_its_digits(messages_db, contacts_db):
    """No contact record — the number is still the best available name."""
    _add_chat(messages_db, "19998887777@s.whatsapp.net", "19998887777")

    chat = whatsapp.get_chat("19998887777@s.whatsapp.net")
    assert chat["name"] == "19998887777"


def test_group_chats_skip_contact_lookup(messages_db, contacts_db):
    _add_chat(messages_db, "12345@g.us", "12345")

    chat = whatsapp.get_chat("12345@g.us")
    assert chat["name"] == "12345"


def test_missing_contacts_db_is_not_fatal(messages_db, tmp_path, monkeypatch):
    """Resolver must degrade gracefully when whatsapp.db is absent."""
    monkeypatch.setattr(whatsapp, "WHATSMEOW_DB_PATH", str(tmp_path / "nope.db"))
    _add_chat(messages_db, "14085551234@s.whatsapp.net", "14085551234")

    chat = whatsapp.get_chat("14085551234@s.whatsapp.net")
    assert chat["name"] == "14085551234"


def test_list_messages_resolves_chat_name(messages_db, contacts_db):
    """chat_name on Message rows comes from the same stale chats.name cache
    and must resolve too — list_messages showed the bare number while
    sender_name was already correct."""
    _add_chat(messages_db, "14085551234@s.whatsapp.net", "14085551234")
    conn = sqlite3.connect(messages_db)
    conn.execute(
        """INSERT INTO messages (id, chat_jid, sender, content, timestamp, is_from_me)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            "m-resolve",
            "14085551234@s.whatsapp.net",
            "14085551234",
            "hi there",
            "2024-01-16 09:00:00+00:00",
            0,
        ),
    )
    conn.commit()
    conn.close()

    out = whatsapp.list_messages(chat_jid="14085551234@s.whatsapp.net", include_context=False)
    assert len(out) == 1
    assert out[0]["chat_name"] == "Jane Doe"
