import shlex

import pytest

from wpstudio import guard
from conftest import make_backup


@pytest.mark.parametrize("args", [
    "plugin list", "plugin list --status=active --field=name", "theme status twentytwentyfive",
    "core version", "core verify-checksums", "option get home", "option list --search=blog*",
    "post list --post_type=page --fields=ID,post_title", "post get 12 --field=post_content",
    "post meta list 12", "user list --role=administrator", "db size", "db tables",
    "db query 'SELECT ID FROM wp_posts LIMIT 1'", "db export -", "search-replace a b --dry-run",
    "cli has-command 'kinsta cache'", "--info", "cache flush", "kinsta cache purge --all",
    "litespeed-purge all", "config list", "cron event list", "menu item list main",
])
def test_reading_commands_need_no_backup(args):
    assert guard.wp_is_read_only(shlex.split(args)) is True


@pytest.mark.parametrize("args", [
    "plugin delete hello", "plugin update --all", "plugin install foo --activate", "theme activate x",
    "option update blogname X", "option delete foo", "post update 12 -", "post delete 12 --force",
    "post meta update 12 key value", "user create bob b@example.com", "user delete 3",
    "db reset --yes", "db import dump.sql", "db query 'DELETE FROM wp_posts'",
    "db query 'SELECT 1; DROP TABLE wp_posts'", "db export backup.sql", "search-replace old new",
    "eval 'update_option(1,2);'", "eval-file script.php", "config set WP_DEBUG true --raw",
    "core update", "rewrite structure /%postname%/", "some-unknown-command run",
    # Review round 1: global flags, aliases and pass-through flags that run code or SQL.
    "option get home --exec=update_option('blogname','x');", "plugin list --require=/tmp/x.php",
    "@prod plugin delete akismet", "@all option update blogname x", "option get home --ssh=other-host",
    "db query 'SELECT 1' --init-command='DELETE FROM wp_posts'", "db check --repair", "cli update --yes",
    "db query \"SELECT * FROM wp_users INTO OUTFILE '/tmp/u'\"", "db export - --result-file=x.sql",
    "cron test", "transient delete --all", "plugin list -v",
])
def test_changing_commands_need_a_backup(args):
    assert guard.wp_is_read_only(shlex.split(args)) is False


@pytest.mark.parametrize("command", [
    "ls -la wp-content", "cat wp-config.php | tail -5", "grep -rl base64_decode wp-content/uploads",
    "find wp-content/uploads -name '*.php' -newer wp-config.php", "md5sum index.php",
    "wp plugin list && wp theme list", "cd wp-content && ls", "php -v", "tar -tf file.tar",
    "du -sh wp-content/uploads 2>/dev/null", "head -20 wp-config.php", "crontab -l",
])
def test_read_only_shell(command):
    assert guard.shell_is_read_only(command) is True


@pytest.mark.parametrize("command", [
    # Review round 1: things a real shell runs that the old parser missed.
    "ls\nrm -rf wp-content/uploads", "ls >/dev/null\nwp option update blogname x", "echo hi >| index.php",
    "command rm -rf wp-content/uploads", "sed -i.bak s/a/b/ index.php", "sed -Ei s/a/b/ x",
    "sed -n 's/x/y/w out' f", "sort --output=wp-config.php a", "sort -owp-config.php a", "uniq a.txt wp-config.php",
    "tree -o index.php", "tar -tf x.tar --checkpoint=1 --checkpoint-action=exec='rm -rf wp-content'",
    "mysql -e 'select 1; delete from wp_posts'", "WP_CLI_PHP_ARGS='-d auto_prepend_file=/tmp/x' wp option get home",
    "{ rm x; }", "( rm x )", "ls # \nrm x", "ls ${IFS}x", "/bin/rm x", "file -C -m x",
    "rm -rf wp-content/cache", "mv a b", "echo x > index.php", "cat a >> b", "find . -name x -delete",
    "find . -exec rm {} +", "sed -i s/a/b/ wp-config.php", "wp option update a b", "chmod 777 x",
    "ls $(rm -rf /)", "ls `id`", "php -r 'unlink(\"x\");'", "php script.php", "tar -xf x.tar",
    "gzip big.log", "crontab -r", "mysql -e 'DROP TABLE x'", "cat <<EOF > x", "sort -o out in",
    "curl https://example.com/x.sh", "python3 -c 'print(1)'",
])
def test_writing_or_unknown_shell(command):
    assert guard.shell_is_read_only(command) is False


def test_no_backup_folder_means_not_fresh(tmp_path):
    assert guard.latest_backup(tmp_path) is None
    assert guard.backup_is_fresh(tmp_path) is False


def test_recent_verified_backup_is_fresh(tmp_path):
    make_backup(tmp_path, age=60)
    assert guard.backup_is_fresh(tmp_path / "backups" / "live") is True


def test_backup_older_than_the_limit_is_not_fresh(tmp_path):
    make_backup(tmp_path, age=guard.BACKUP_MAX_AGE + 5)
    assert guard.backup_is_fresh(tmp_path / "backups" / "live") is False


def test_unverified_dump_does_not_count(tmp_path):
    folder = tmp_path / "backups" / "live"
    folder.mkdir(parents=True)
    (folder / "db-1.sql.gz").write_bytes(b"x")
    assert guard.latest_backup(folder) is None


def test_dump_changed_after_verification_does_not_count(tmp_path):
    make_backup(tmp_path, age=10, bytes_override=63)
    assert guard.latest_backup(tmp_path / "backups" / "live") is None
