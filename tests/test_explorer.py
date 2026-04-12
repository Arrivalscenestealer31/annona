"""
Tests for ExplorerTool.

Covers: map, find, search, analyze operations —
        including depth limits, hidden files, file type filters,
        pattern matching, and edge cases.
"""
import pytest
from pathlib import Path

from runner.tools.explorer import ExplorerTool, _fmt_size


# ── Fixture helpers ───────────────────────────────────────────────────────────

def make_tool(config=None):
    return ExplorerTool(config or {})


# ── MAP operation ─────────────────────────────────────────────────────────────

class TestMap:
    def test_map_flat_directory(self, sample_dir):
        result = make_tool().execute("map", str(sample_dir))
        assert result["success"] is True
        tree = result["tree"]
        assert "reports" in tree
        assert "docs" in tree
        assert "scripts" in tree

    def test_map_shows_file_sizes(self, sample_dir):
        result = make_tool().execute("map", str(sample_dir))
        # sizes should appear as e.g. "123B" or "1KB"
        tree = result["tree"]
        assert any(unit in tree for unit in ["B", "KB", "MB"])

    def test_map_excludes_hidden_by_default(self, sample_dir):
        result = make_tool().execute("map", str(sample_dir))
        assert ".hidden_file" not in result["tree"]

    def test_map_includes_hidden_when_requested(self, sample_dir):
        result = make_tool().execute("map", str(sample_dir), include_hidden=True)
        assert ".hidden_file" in result["tree"]

    def test_map_depth_limit(self, sample_dir):
        result = make_tool().execute("map", str(sample_dir), depth=0)
        tree = result["tree"]
        # depth=0 means we list top-level only, not descend into subdirs
        assert "max depth reached" in tree

    def test_map_stats(self, sample_dir):
        result = make_tool().execute("map", str(sample_dir))
        stats = result["stats"]
        assert stats["dirs"] >= 3  # reports, docs, scripts
        assert stats["files"] > 0

    def test_map_stats_by_format(self, sample_dir):
        result = make_tool().execute("map", str(sample_dir))
        by_fmt = result["stats"]["by_format"]
        # We have .txt, .csv, .md, .json, .sh, .py files
        assert sum(by_fmt.values()) >= 7

    def test_map_file_type_filter(self, sample_dir):
        result = make_tool().execute(
            "map", str(sample_dir), file_types=[".csv"]
        )
        tree = result["tree"]
        assert "financial_summary.csv" in tree
        assert "q1_report.txt" not in tree

    def test_map_nonexistent_path(self):
        result = make_tool().execute("map", "/nonexistent/path/xyz")
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_map_max_results_cap(self, tmp_path):
        # Create 10 files
        for i in range(10):
            (tmp_path / f"file_{i:02d}.txt").write_text(f"content {i}")
        result = make_tool().execute("map", str(tmp_path), max_results=5)
        assert result["success"] is True
        assert "more items" in result["tree"]

    def test_map_single_file_directory(self, tmp_path):
        (tmp_path / "only.txt").write_text("alone")
        result = make_tool().execute("map", str(tmp_path))
        assert result["success"] is True
        assert "only.txt" in result["tree"]
        assert result["stats"]["files"] == 1

    def test_map_empty_directory(self, tmp_path):
        empty = tmp_path / "empty_dir"
        empty.mkdir()
        result = make_tool().execute("map", str(empty))
        assert result["success"] is True
        assert result["stats"]["files"] == 0


# ── FIND operation ────────────────────────────────────────────────────────────

class TestFind:
    def test_find_by_extension(self, sample_dir):
        result = make_tool().execute("find", str(sample_dir), file_types=[".csv"])
        assert result["success"] is True
        assert result["count"] == 1
        assert result["files"][0]["name"] == "financial_summary.csv"

    def test_find_multiple_extensions(self, sample_dir):
        result = make_tool().execute(
            "find", str(sample_dir), file_types=[".txt", ".md"]
        )
        assert result["success"] is True
        names = [f["name"] for f in result["files"]]
        assert "q1_report.txt" in names
        assert "q2_report.txt" in names
        assert "readme.md" in names
        assert "financial_summary.csv" not in names

    def test_find_by_glob_pattern(self, sample_dir):
        result = make_tool().execute("find", str(sample_dir), pattern="q*.txt")
        assert result["success"] is True
        assert result["count"] == 2
        names = {f["name"] for f in result["files"]}
        assert names == {"q1_report.txt", "q2_report.txt"}

    def test_find_by_substring(self, sample_dir):
        result = make_tool().execute("find", str(sample_dir), pattern="report")
        assert result["success"] is True
        names = [f["name"] for f in result["files"]]
        assert all("report" in n for n in names)

    def test_find_no_matches(self, sample_dir):
        result = make_tool().execute("find", str(sample_dir), pattern="*.xyz")
        assert result["success"] is True
        assert result["count"] == 0

    def test_find_returns_metadata(self, sample_dir):
        result = make_tool().execute("find", str(sample_dir), pattern="config.json")
        assert result["success"] is True
        assert result["count"] == 1
        f = result["files"][0]
        assert "path" in f
        assert "size_mb" in f
        assert "modified" in f
        assert "format" in f

    def test_find_respects_depth(self, tmp_path):
        # Create nested structure
        (tmp_path / "top.txt").write_text("top")
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_text("deep")

        shallow = make_tool().execute("find", str(tmp_path), depth=1)
        deep_result = make_tool().execute("find", str(tmp_path), depth=5)

        shallow_names = {f["name"] for f in shallow["files"]}
        deep_names = {f["name"] for f in deep_result["files"]}

        assert "top.txt" in shallow_names
        assert "deep.txt" not in shallow_names
        assert "deep.txt" in deep_names

    def test_find_max_results(self, tmp_path):
        for i in range(20):
            (tmp_path / f"file_{i}.txt").write_text(f"content {i}")
        result = make_tool().execute("find", str(tmp_path), max_results=5)
        assert result["count"] == 5

    def test_find_includes_path(self, sample_dir):
        result = make_tool().execute("find", str(sample_dir), pattern="deploy.sh")
        assert result["count"] == 1
        assert "scripts" in result["files"][0]["path"]


# ── SEARCH operation ──────────────────────────────────────────────────────────

class TestSearch:
    def test_search_finds_keyword(self, sample_dir):
        result = make_tool().execute("search", str(sample_dir), pattern="Revenue")
        assert result["success"] is True
        assert result["files_with_matches"] > 0

    def test_search_case_insensitive(self, sample_dir):
        result_lower = make_tool().execute("search", str(sample_dir), pattern="revenue")
        result_upper = make_tool().execute("search", str(sample_dir), pattern="REVENUE")
        # Both should find same files
        assert result_lower["files_with_matches"] == result_upper["files_with_matches"]

    def test_search_returns_line_numbers(self, sample_dir):
        result = make_tool().execute("search", str(sample_dir), pattern="Revenue")
        for file_result in result["results"]:
            for match in file_result["matches"]:
                assert "line" in match
                assert match["line"] >= 1
                assert "text" in match

    def test_search_filtered_by_extension(self, sample_dir):
        result = make_tool().execute(
            "search", str(sample_dir),
            pattern="Revenue",
            file_types=[".csv"]
        )
        for file_result in result["results"]:
            assert file_result["path"].endswith(".csv")

    def test_search_no_pattern_returns_error(self, sample_dir):
        result = make_tool().execute("search", str(sample_dir))
        assert result["success"] is False
        assert "pattern" in result["error"].lower()

    def test_search_no_matches(self, sample_dir):
        result = make_tool().execute("search", str(sample_dir), pattern="ZZZNOMATCH999")
        assert result["success"] is True
        assert result["files_with_matches"] == 0

    def test_search_max_matches_per_file(self, tmp_path):
        f = tmp_path / "repeated.txt"
        f.write_text("\n".join([f"line {i}: keyword here" for i in range(50)]))
        result = make_tool().execute("search", str(tmp_path), pattern="keyword")
        assert result["success"] is True
        # Max 20 matches per file
        for file_result in result["results"]:
            assert len(file_result["matches"]) <= 20

    def test_search_across_multiple_files(self, sample_dir):
        # "Revenue" appears in q1, q2 reports AND csv
        result = make_tool().execute("search", str(sample_dir), pattern="Revenue")
        files_found = {r["name"] for r in result["results"]}
        assert len(files_found) >= 2

    def test_search_respects_max_results(self, tmp_path):
        for i in range(10):
            (tmp_path / f"file_{i}.txt").write_text("target word here")
        result = make_tool().execute(
            "search", str(tmp_path), pattern="target", max_results=3
        )
        assert result["files_with_matches"] <= 3


# ── ANALYZE operation ─────────────────────────────────────────────────────────

class TestAnalyze:
    def test_analyze_returns_all_sections(self, sample_dir):
        result = make_tool().execute("analyze", str(sample_dir))
        assert result["success"] is True
        assert "summary" in result
        assert "tree" in result
        assert "stats" in result
        assert "files" in result
        assert "by_category" in result

    def test_analyze_summary_contains_file_count(self, sample_dir):
        result = make_tool().execute("analyze", str(sample_dir))
        assert "Total files:" in result["summary"]
        # We have at least 7 files
        assert result["stats"]["total_files"] >= 7

    def test_analyze_classifies_by_format(self, sample_dir):
        result = make_tool().execute("analyze", str(sample_dir))
        by_cat = result["stats"]["by_category"]
        assert "text" in by_cat       # .txt files
        assert "csv" in by_cat        # .csv
        assert "code" in by_cat       # .py, .sh, .json, .md

    def test_analyze_files_have_metadata(self, sample_dir):
        result = make_tool().execute("analyze", str(sample_dir))
        for f in result["files"]:
            assert "path" in f
            assert "name" in f
            assert "format" in f
            assert "size_mb" in f
            assert "modified" in f

    def test_analyze_generates_previews(self, sample_dir):
        result = make_tool().execute("analyze", str(sample_dir))
        # Should have previews for text/code/csv files
        assert len(result["previews"]) > 0
        for preview in result["previews"]:
            assert "path" in preview
            assert "format" in preview
            assert "preview" in preview
            assert len(preview["preview"]) > 0

    def test_analyze_by_category_grouping(self, sample_dir):
        result = make_tool().execute("analyze", str(sample_dir))
        by_cat = result["by_category"]
        # All files in category list should have consistent format field
        for cat, files in by_cat.items():
            for f in files:
                assert f["format"] == cat

    def test_analyze_summary_format(self, sample_dir):
        result = make_tool().execute("analyze", str(sample_dir))
        lines = result["summary"].split("\n")
        # First line should be the directory path
        assert str(sample_dir) in lines[0]

    def test_analyze_single_file_dir(self, tmp_path):
        (tmp_path / "lonely.py").write_text("print('hello')")
        result = make_tool().execute("analyze", str(tmp_path))
        assert result["success"] is True
        assert result["stats"]["total_files"] == 1

    def test_analyze_empty_dir(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        result = make_tool().execute("analyze", str(empty))
        assert result["success"] is True
        assert result["stats"]["total_files"] == 0
        assert result["previews"] == []


# ── Unknown operation ─────────────────────────────────────────────────────────

class TestErrors:
    def test_unknown_operation(self, sample_dir):
        result = make_tool().execute("explode", str(sample_dir))
        assert result["success"] is False
        assert "Unknown operation" in result["error"]

    def test_nonexistent_path_all_ops(self, tmp_path):
        bad = str(tmp_path / "does_not_exist")
        for op in ["map", "find", "search", "analyze"]:
            result = make_tool().execute(op, bad)
            assert result["success"] is False


# ── Helper function ───────────────────────────────────────────────────────────

class TestFmtSize:
    def test_bytes(self):
        assert _fmt_size(500) == "500B"

    def test_kilobytes(self):
        assert _fmt_size(2048) == "2KB"

    def test_megabytes(self):
        assert "MB" in _fmt_size(5 * 1024 * 1024)
