import stat

from wpstudio import envfile


def test_round_trip_keeps_awkward_values_exactly(tmp_path):
    path = tmp_path / ".secrets" / "live.env"
    values = {"SSH_PASSWORD": "it's $HOME `x` \"q\" \\ # not a comment", "WP_PATH": "/www/a b/public",
              "EXTRA_NOTE": ""}
    envfile.write(path, values, header="test")
    assert envfile.read(path) == values


def test_file_and_folder_are_private(tmp_path):
    path = tmp_path / ".secrets" / "live.env"
    envfile.write(path, {"SSH_HOST": "h"})
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_reads_v1_shell_quoted_files(tmp_path):
    path = tmp_path / "connection.env"
    path.write_text("# v1\nSSH_HOST='203.0.113.7'\nSSH_PASSWORD='it'\\''s'\nexport WP_PATH=\"/www/x\"\nSSH_PORT=22 # custom\n")
    assert envfile.read(path) == {"SSH_HOST": "203.0.113.7", "SSH_PASSWORD": "it's", "WP_PATH": "/www/x", "SSH_PORT": "22"}


def test_line_breaks_in_values_are_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        envfile.write(tmp_path / "x.env", {"SSH_PASSWORD": "a\nb"})
