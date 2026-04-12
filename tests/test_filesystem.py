"""
Tests for FilesystemTool — including the new 'search' operation.
"""
import pytest
from pathlib import Path

from runner.tools.filesystem import FilesystemTool


def make_tool(config=None):
    return FilesystemTool(config or {})


class TestRead:
    def test_read_text_file(self, tmp_path):
        f = tmp_path / "hello.txt"
        f.write_text("Hello\nWorld\n")
        result = make_tool().execute("read", str(f))
        assert result == "Hello\nWorld\n"

    def test_read_nonexistent(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            make_tool().execute("read", str(tmp_path / "missing.txt"))

    def test_read_directory_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Not a file"):
            make_tool().execute("read", str(tmp_path))

    def test_read_unicode(self, tmp_path):
        f = tmp_path / "utf8.txt"
        f.write_text("café résumé 日本語", encoding="utf-8")
        result = make_tool().execute("read", str(f))
        assert "café" in result


class TestWrite:
    def test_write_creates_file(self, tmp_path):
        path = str(tmp_path / "out.txt")
        result = make_tool().execute("write", path, content="new content")
        assert result["success"] is True
        assert Path(path).read_text() == "new content"

    def test_write_creates_parent_dirs(self, tmp_path):
        path = str(tmp_path / "a" / "b" / "c" / "file.txt")
        make_tool().execute("write", path, content="deep")
        assert Path(path).exists()

    def test_write_overwrites_existing(self, tmp_path):
        f = tmp_path / "existing.txt"
        f.write_text("old")
        make_tool().execute("write", str(f), content="new")
        assert f.read_text() == "new"

    def test_write_no_content_raises(self, tmp_path):
        with pytest.raises(ValueError, match="Content required"):
            make_tool().execute("write", str(tmp_path / "x.txt"))

    def test_write_returns_size(self, tmp_path):
        result = make_tool().execute("write", str(tmp_path / "s.txt"), content="abcde")
        assert result["size"] == 5


class TestList:
    def test_list_directory(self, sample_dir):
        result = make_tool().execute("list", str(sample_dir))
        names = {item["name"] for item in result}
        assert "reports" in names
        assert "docs" in names
        assert "scripts" in names

    def test_list_has_type_field(self, sample_dir):
        result = make_tool().execute("list", str(sample_dir))
        types = {item["type"] for item in result}
        assert "directory" in types

    def test_list_file_has_size(self, tmp_path):
        (tmp_path / "sized.txt").write_text("hello")
        result = make_tool().execute("list", str(tmp_path))
        file_items = [i for i in result if i["type"] == "file"]
        assert all(i["size"] is not None for i in file_items)

    def test_list_dir_size_is_none(self, tmp_path):
        (tmp_path / "sub").mkdir()
        result = make_tool().execute("list", str(tmp_path))
        dirs = [i for i in result if i["type"] == "directory"]
        assert all(i["size"] is None for i in dirs)

    def test_list_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            make_tool().execute("list", str(tmp_path / "ghost"))

    def test_list_file_raises(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("")
        with pytest.raises(ValueError, match="Not a directory"):
            make_tool().execute("list", str(f))


class TestExists:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "yes.txt"
        f.write_text("")
        assert make_tool().execute("exists", str(f)) is True

    def test_missing_path(self, tmp_path):
        assert make_tool().execute("exists", str(tmp_path / "no.txt")) is False

    def test_existing_directory(self, tmp_path):
        assert make_tool().execute("exists", str(tmp_path)) is True


class TestDelete:
    def test_delete_file(self, tmp_path):
        f = tmp_path / "del.txt"
        f.write_text("bye")
        result = make_tool().execute("delete", str(f))
        assert result["success"] is True
        assert not f.exists()

    def test_delete_directory_recursive(self, tmp_path):
        d = tmp_path / "tree"
        d.mkdir()
        (d / "child.txt").write_text("x")
        result = make_tool().execute("delete", str(d))
        assert result["success"] is True
        assert not d.exists()

    def test_delete_nonexistent_raises(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            make_tool().execute("delete", str(tmp_path / "missing.txt"))


class TestSearch:
    def test_search_by_extension(self, sample_dir):
        results = make_tool().execute("search", str(sample_dir), pattern="*.csv")
        assert len(results) == 1
        assert results[0]["name"] == "financial_summary.csv"

    def test_search_by_glob_prefix(self, sample_dir):
        results = make_tool().execute("search", str(sample_dir), pattern="q*.txt")
        names = {r["name"] for r in results}
        assert names == {"q1_report.txt", "q2_report.txt"}

    def test_search_wildcard_all(self, sample_dir):
        results = make_tool().execute("search", str(sample_dir), pattern="*")
        assert len(results) >= 7  # all non-hidden files

    def test_search_nonrecursive(self, sample_dir):
        results = make_tool().execute(
            "search", str(sample_dir), pattern="*.txt", recursive=False
        )
        # .txt files are inside subdirs, not at root level
        assert len(results) == 0

    def test_search_recursive_default(self, sample_dir):
        results = make_tool().execute("search", str(sample_dir), pattern="*.txt")
        assert len(results) >= 3  # q1, q2, notes

    def test_search_returns_metadata(self, sample_dir):
        results = make_tool().execute("search", str(sample_dir), pattern="*.py")
        assert len(results) >= 1
        r = results[0]
        assert "name" in r
        assert "path" in r
        assert "size_mb" in r
        assert "modified" in r

    def test_search_no_match(self, sample_dir):
        results = make_tool().execute("search", str(sample_dir), pattern="*.xyz")
        assert results == []

    def test_search_on_file_raises(self, tmp_path):
        f = tmp_path / "f.txt"
        f.write_text("")
        with pytest.raises(ValueError, match="Not a directory"):
            make_tool().execute("search", str(f))
