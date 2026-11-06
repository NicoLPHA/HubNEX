"""The mailbox search term comes from Claude, so it may carry what an email put in its head:
it must never be able to start a second IMAP command."""

from hubnex.integrations.mail import MailClient, _search_text
from hubnex.config import MailSettings


def test_search_term_loses_everything_that_could_break_out_of_the_command():
    assert _search_text("offerta") == "offerta"
    assert _search_text('a"b') == "a b"
    assert _search_text("back\\slash") == "back slash"
    assert "\r" not in _search_text("x\r\nA2 DELETE INBOX") and "\n" not in _search_text("x\r\nA2 DELETE INBOX")
    assert _search_text(None) == ""
    assert _search_text("perché") == "perché"  # accents stay: they go as a UTF-8 literal


def test_search_sends_one_command_only(monkeypatch):
    sent = []

    class FakeConn:
        def select(self, *a, **k):
            return "OK", [b"1"]

        def uid(self, *args):
            sent.append(args)
            return "OK", [b""]

        def logout(self):
            pass

    client = MailClient(MailSettings(user="a@b.c", password="x", imap_host="h", smtp_host="s"))
    monkeypatch.setattr(client, "_imap", lambda: FakeConn())
    client.search('x"\r\nA2 DELETE INBOX')
    command = sent[0][2]
    assert "\r" not in command and "\n" not in command
    assert command.count('"') % 2 == 0, "quotes must stay balanced"
