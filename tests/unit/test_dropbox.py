import pytest

from wpstudio import dropbox


def filled(lines):
    return dropbox.TEMPLATE.read_text(encoding="utf-8").split("Site address:")[0] + "\n".join(lines) + "\n"


def test_blank_template_counts_as_empty(tmp_path):
    box = tmp_path / "CREDENTIALS.txt"
    dropbox.wipe(box)
    assert dropbox.has_content(box) is False


def test_labeled_lines_map_to_connection_keys():
    parsed = dropbox.parse(filled([
        "Site address: Acme.com/", "SSH host: 203.0.113.5", "SSH port: 2222", "SSH username: acme",
        "SSH password:  p@ss: w0rd with spaces ", "WordPress folder on the server: /www/acme/public",
        "Hosting company: Kinsta",
    ]))
    assert parsed.values == {
        "SITE_URL": "https://acme.com", "SSH_HOST": "203.0.113.5", "SSH_PORT": "2222", "SSH_USER": "acme",
        "SSH_PASSWORD": "p@ss: w0rd with spaces", "WP_PATH": "/www/acme/public", "HOST": "kinsta",
    }


def test_host_connect_line_fills_user_host_and_port():
    parsed = dropbox.parse(filled(["ssh acme@203.0.113.5 -p 41234"]))
    assert parsed.values == {"SSH_USER": "acme", "SSH_HOST": "203.0.113.5", "SSH_PORT": "41234"}


def test_unlabeled_lines_are_counted_not_kept():
    parsed = dropbox.parse(filled(["just some words", "Password: abcdef123"]))
    assert parsed.unrecognized_lines == 1
    assert parsed.values == {"SSH_PASSWORD": "abcdef123"}


def test_unknown_labels_are_kept_as_extras():
    parsed = dropbox.parse(filled(["Cloudflare API token: abc123xyz"]))
    assert parsed.values == {"EXTRA_CLOUDFLARE_API_TOKEN": "abc123xyz"}


def test_pasted_private_key_is_refused_and_not_kept():
    parsed = dropbox.parse(filled(["-----BEGIN OPENSSH PRIVATE KEY-----", "b3BlbnNzaC1rZXktdjEAAAAA",
                                   "-----END OPENSSH PRIVATE KEY-----"]))
    assert parsed.values == {}
    assert len(parsed.refused) == 1


def test_bad_port_is_an_error():
    with pytest.raises(dropbox.DropboxError):
        dropbox.parse(filled(["SSH port: twenty-two"]))


def test_missing_marker_is_an_error():
    with pytest.raises(dropbox.DropboxError):
        dropbox.parse("SSH password: x\n")
