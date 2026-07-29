"""
Tests for PermissionManager — including coverage of new tools.
"""

from runner.permissions.manager import PermissionManager


def make_manager(
    allowed=None,
    denied=None,
    shell_enabled=True,
    allowed_cmds=None,
    denied_cmds=None,
    allowed_domains=None,
):
    config = {
        "permissions": {
            "filesystem": {
                "allowed_paths": allowed or [],
                "denied_paths": denied or [],
                "max_file_size_mb": 10,
            },
            "shell": {
                "enabled": shell_enabled,
                "allowed_commands": allowed_cmds or [],
                "denied_commands": denied_cmds or [],
            },
            "network": {
                "enabled": True,
                "allowed_domains": allowed_domains or [],
            },
        }
    }
    return PermissionManager(config)


class TestFilesystemPermissions:
    def test_allowed_path(self, tmp_path):
        pm = make_manager(allowed=[str(tmp_path)])
        assert pm.check_tool_permission("filesystem", {"path": str(tmp_path / "file.txt")})

    def test_denied_path(self, tmp_path):
        pm = make_manager(allowed=[str(tmp_path)], denied=[str(tmp_path / "secret")])
        secret = tmp_path / "secret" / "data.txt"
        assert not pm.check_tool_permission("filesystem", {"path": str(secret)})

    def test_denied_overrides_allowed(self, tmp_path):
        pm = make_manager(allowed=[str(tmp_path)], denied=[str(tmp_path)])
        assert not pm.check_tool_permission("filesystem", {"path": str(tmp_path / "f.txt")})

    def test_no_allowed_list_permits_all(self, tmp_path):
        pm = make_manager(allowed=[])  # empty = unrestricted
        assert pm.check_tool_permission("filesystem", {"path": str(tmp_path / "anything.txt")})

    def test_path_outside_allowed(self, tmp_path):
        allowed = tmp_path / "docs"
        allowed.mkdir()
        pm = make_manager(allowed=[str(allowed)])
        outside = tmp_path / "other" / "file.txt"
        assert not pm.check_tool_permission("filesystem", {"path": str(outside)})

    def test_document_reader_uses_filesystem_check(self, tmp_path):
        pm = make_manager(allowed=[str(tmp_path)])
        assert pm.check_tool_permission("document_reader", {"path": str(tmp_path / "doc.pdf")})

    def test_explorer_defaults_to_allowed(self, tmp_path):
        # explorer tool name not explicitly in the routing → defaults to True
        pm = make_manager(allowed=[])
        assert pm.check_tool_permission("explorer", {"path": str(tmp_path)})

    def test_tilde_expansion(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        pm = make_manager(allowed=["~/docs"])
        docs = tmp_path / "docs" / "report.txt"
        assert pm.check_tool_permission("filesystem", {"path": str(docs)})


class TestShellPermissions:
    def test_shell_disabled(self):
        pm = make_manager(shell_enabled=False)
        assert not pm.check_tool_permission("shell", {"command": "ls"})

    def test_shell_no_allowed_list_permits_all(self):
        pm = make_manager(shell_enabled=True, allowed_cmds=[])
        assert pm.check_tool_permission("shell", {"command": "ls -la"})

    def test_shell_allowed_commands(self):
        pm = make_manager(allowed_cmds=["ls", "cat", "grep"])
        assert pm.check_tool_permission("shell", {"command": "ls -la"})
        assert pm.check_tool_permission("shell", {"command": "cat file.txt"})

    def test_shell_blocked_command(self):
        pm = make_manager(allowed_cmds=["ls", "cat"])
        assert not pm.check_tool_permission("shell", {"command": "rm -rf /"})

    def test_shell_denied_commands(self):
        pm = make_manager(denied_cmds=["rm"])
        assert not pm.check_tool_permission("shell", {"command": "rm file.txt"})

    def test_denied_overrides_allowed_in_shell(self):
        pm = make_manager(allowed_cmds=["rm"], denied_cmds=["rm"])
        assert not pm.check_tool_permission("shell", {"command": "rm file.txt"})

    def test_shell_no_command_arg_permits(self):
        pm = make_manager()
        assert pm.check_tool_permission("shell", {})


class TestNetworkPermissions:
    def test_no_domain_list_permits_all(self):
        pm = make_manager()
        assert pm.check_tool_permission("browser", {"url": "https://example.com"})

    def test_allowed_domain(self):
        pm = make_manager(allowed_domains=["api.akaion.com"])
        assert pm.check_tool_permission("browser", {"url": "https://api.akaion.com/v1/data"})

    def test_blocked_domain(self):
        pm = make_manager(allowed_domains=["api.akaion.com"])
        assert not pm.check_tool_permission("browser", {"url": "https://evil.com"})

    def test_wildcard_subdomain(self):
        pm = make_manager(allowed_domains=["*.akaion.com"])
        assert pm.check_tool_permission("browser", {"url": "https://ai.akaion.com"})
        assert pm.check_tool_permission("browser", {"url": "https://calendar.akaion.com"})

    def test_wildcard_does_not_match_parent(self):
        pm = make_manager(allowed_domains=["*.akaion.com"])
        # "akaion.com" itself should not match "*.akaion.com"
        assert not pm.check_tool_permission("browser", {"url": "https://evil-akaion.com"})


class TestFileSizeValidation:
    def test_file_within_limit(self, tmp_path):
        f = tmp_path / "small.txt"
        f.write_bytes(b"x" * 1000)
        pm = make_manager()
        assert pm.validate_file_size(f)

    def test_file_exceeds_limit(self, tmp_path):
        f = tmp_path / "huge.bin"
        # 10 MB + 1 byte (limit is 10 MB)
        f.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
        pm = make_manager()
        assert not pm.validate_file_size(f)

    def test_nonexistent_file_passes(self, tmp_path):
        pm = make_manager()
        assert pm.validate_file_size(tmp_path / "missing.txt")
