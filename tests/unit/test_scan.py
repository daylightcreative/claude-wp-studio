import subprocess

from wpstudio import scan
from conftest import make_site


def entry(path, text):
    data = text.encode()
    return (path, len(data), data)


def test_a_held_secret_is_caught_wherever_it_appears():
    findings = scan.scan_files([entry("clients/acme.md", "notes\nthe password is Hunter2-secret! ok\n")],
                               ["Hunter2-secret!"])
    assert [str(f) for f in findings] == ["clients/acme.md:2: contains a secret the studio holds for a site"]


def test_wp_config_secrets_and_private_keys_are_caught():
    text = "define( 'DB_PASSWORD', 'realpass99' );\n-----BEGIN RSA PRIVATE KEY-----\n"
    reasons = [f.reason for f in scan.scan_files([entry("work/notes.txt", text)], [])]
    assert reasons == ["looks like a WordPress database password or salt", "looks like a private key"]


def test_placeholders_and_redacted_values_are_not_flagged():
    text = "define( 'DB_PASSWORD', '[redacted]' );\nApp password: xxxx xxxx xxxx xxxx xxxx xxxx\n"
    assert scan.scan_files([entry("a.md", text)], []) == []


def test_application_password_shape_is_flagged():
    findings = scan.scan_files([entry("a.md", "use abcd EFGH 1234 ijkl MNOP 5678 for REST\n")], [])
    assert [f.reason for f in findings] == ["looks like a WordPress application password"]


def test_dumps_configs_and_keys_are_blocked_by_name():
    names = ["projects/a/work/wp-config.php", "dump.sql.gz", "x/.env", "keys/server.pem", "id_ed25519"]
    findings = scan.scan_files([entry(n, "") for n in names], [])
    assert [f.path for f in findings] == names


def test_files_over_the_github_limit_are_blocked():
    findings = scan.scan_files([("big.mov", scan.MAX_FILE_BYTES + 1, b"\0")], [])
    assert len(findings) == 1 and "GitHub refuses" in findings[0].reason


def test_known_secrets_come_from_site_files_but_not_hosts_or_users(studio):
    make_site(studio)
    assert scan.known_secrets(studio) == ["Hunter2-secret!"]


def test_scan_staged_reads_the_index(studio):
    make_site(studio)
    (studio / "clients" / "acme.md").write_text("pw Hunter2-secret!\n")
    subprocess.run(["git", "-C", str(studio), "add", "clients/acme.md"], check=True)
    assert [str(f) for f in scan.scan_staged(studio)] == ["clients/acme.md:1: contains a secret the studio holds for a site"]
