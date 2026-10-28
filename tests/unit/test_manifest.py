import json
import re

from conftest import PLUGIN, REPO


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_version_is_one_value_everywhere():
    import wpstudio
    version = load(PLUGIN / ".claude-plugin" / "plugin.json")["version"]
    assert wpstudio.__version__ == version
    top = re.search(r"^## (\d+\.\d+\.\d+)", (REPO / "CHANGELOG.md").read_text(encoding="utf-8"), re.M).group(1)
    assert top == version


def test_marketplace_lists_the_plugin_folder():
    market = load(REPO / ".claude-plugin" / "marketplace.json")
    entry = next(p for p in market["plugins"] if p["name"] == "wp-studio")
    assert (REPO / entry["source"] / ".claude-plugin" / "plugin.json").is_file()
    settings = load(PLUGIN / "templates" / "workspace" / "settings.json")
    assert settings["enabledPlugins"] == {"wp-studio@%s" % market["name"]: True}
    assert market["name"] in settings["extraKnownMarketplaces"]


def test_browser_server_is_pinned_and_the_installer_reads_the_pin():
    args = load(PLUGIN / ".mcp.json")["mcpServers"]["playwright"]["args"]
    package = next(a for a in args if a.startswith("@playwright/mcp@"))
    assert re.match(r"^@playwright/mcp@\d+\.\d+\.\d+$", package)
    installer = (REPO / "install.sh").read_text(encoding="utf-8")
    assert "mcp-version" in installer and "@playwright/mcp@$MCP_VERSION" in installer


def test_hooks_use_exec_form_with_a_sessionend_budget():
    hooks = load(PLUGIN / "hooks" / "hooks.json")["hooks"]
    assert set(hooks) == {"SessionStart", "PreToolUse", "SessionEnd"}
    for groups in hooks.values():
        for group in groups:
            for hook in group["hooks"]:
                assert hook["command"] == "python3" and hook["args"][0] == "${CLAUDE_PLUGIN_ROOT}/bin/studio"
    assert hooks["SessionEnd"][0]["hooks"][0]["timeout"] >= 10
    assert hooks["PreToolUse"][0]["matcher"] == "Bash"


def test_workspace_denies_file_tools_on_secrets():
    deny = set(load(PLUGIN / "templates" / "workspace" / "settings.json")["permissions"]["deny"])
    assert {"Read(./CREDENTIALS.txt)", "Read(**/.secrets/**)", "Edit(**/.secrets/**)"} <= deny


def test_launcher_uses_auto_mode_not_bypass():
    launcher = (PLUGIN / "templates" / "workspace" / "studio.sh").read_text(encoding="utf-8")
    assert "--permission-mode auto" in launcher
    assert "dangerously" not in launcher
