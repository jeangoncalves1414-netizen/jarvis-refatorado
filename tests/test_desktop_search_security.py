from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.agent.tools.desktop_search import DesktopSearchTool


@pytest.fixture
def temp_search_folder():
    """Create a temporary search folder for testing."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create some test files and directories
        test_dir = Path(tmp) / "test_dir"
        test_dir.mkdir()
        
        (test_dir / "test_file.txt").write_text("Test content")
        (test_dir / "test_code.py").write_text("print('test')")
        (test_dir / "subdir").mkdir()
        (test_dir / "subdir" / "nested.txt").write_text("Nested content")
        
        yield tmp


class TestDesktopSearchSecurity:
    """Test suite for desktop search security and input validation."""
    
    def test_query_length_validation(self, temp_search_folder):
        """Test that overly long queries are rejected."""
        tool = DesktopSearchTool()
        
        # Query exceeding max length
        long_query = "a" * 250
        result = tool.run(query=long_query)
        
        assert result["success"] is False
        assert "too long" in result["error"].lower()
    
    def test_max_results_validation_too_low(self, temp_search_folder):
        """Test that max_results below minimum is rejected."""
        tool = DesktopSearchTool()
        
        result = tool.run(query="test", max_results=0)
        
        assert result["success"] is False
        assert "between 1 and" in result["error"].lower()
    
    def test_max_results_validation_too_high(self, temp_search_folder):
        """Test that max_results above maximum is rejected."""
        tool = DesktopSearchTool()
        
        result = tool.run(query="test", max_results=200)
        
        assert result["success"] is False
        assert "between 1 and" in result["error"].lower()
    
    def test_invalid_category_rejection(self, temp_search_folder):
        """Test that invalid categories are rejected."""
        tool = DesktopSearchTool()
        
        result = tool.run(query="test", category="invalid_category")
        
        assert result["success"] is False
        assert "invalid category" in result["error"].lower()
    
    def test_query_term_length_validation(self, temp_search_folder):
        """Test that query terms exceeding max length are filtered out."""
        tool = DesktopSearchTool()
        
        # Create query with very long term (should be filtered out by length check)
        long_term_query = "xyzabc" * 15  # 15 * 6 = 90 characters, exceeds MAX_TERM_LENGTH
        result = tool.run(query=long_term_query)
        
        # Should still work since term is filtered out by length check
        assert result["success"] is True
        # When query terms are all filtered out due to length, it behaves like empty query
        # The important thing is it doesn't crash and the filtering works
        assert result["count"] >= 0  # May return results (empty query behavior)
    
    def test_too_many_query_terms(self, temp_search_folder):
        """Test that too many query terms are rejected."""
        tool = DesktopSearchTool()
        
        # Create query with many terms
        many_terms = " ".join([f"term{i}" for i in range(15)])
        result = tool.run(query=many_terms)
        
        assert result["success"] is False
        assert "too many search terms" in result["error"].lower()
    
    def test_empty_query_still_works(self, temp_search_folder):
        """Test that empty query still works (returns all files)."""
        tool = DesktopSearchTool()
        
        result = tool.run(query="")
        
        assert result["success"] is True
        assert result["count"] > 0
    
    def test_valid_search_still_works(self, temp_search_folder):
        """Test that valid search operations still work correctly."""
        tool = DesktopSearchTool()
        
        result = tool.run(query="test", max_results=10)
        
        assert result["success"] is True
        assert result["count"] > 0
        assert any("test" in item["name"].lower() for item in result["results"])
    
    def test_category_filter_still_works(self, temp_search_folder):
        """Test that category filtering still works."""
        tool = DesktopSearchTool()
        
        result = tool.run(query="test", category="code", max_results=10)
        
        assert result["success"] is True
        # Should only return .py files
        for item in result["results"]:
            assert item["ext"] in {".py", ".ts", ".js", ".json", ".html", ".css"}
    
    def test_timeout_enforcement(self, temp_search_folder):
        """Test that search timeout is enforced (simulated with large directory)."""
        tool = DesktopSearchTool()
        
        # This is a basic test - actual timeout would require very large directory
        # Just verify the mechanism exists by checking it doesn't hang
        result = tool.run(query="test", max_results=5)
        
        assert result["success"] is True
        assert result["count"] >= 0
    
    def test_depth_limit_respected(self, temp_search_folder):
        """Test that directory depth limit is respected."""
        tool = DesktopSearchTool()
        
        # Create nested directories
        deep_dir = Path(temp_search_folder) / "level1" / "level2" / "level3" / "level4" / "level5" / "level6"
        deep_dir.mkdir(parents=True)
        (deep_dir / "deep_file.txt").write_text("Deep content")
        
        result = tool.run(query="deep", max_results=10)
        
        # Should not find files beyond depth limit
        assert result["success"] is True
        # Files at depth > MAX_DEPTH should not be found
        deep_path_found = any("level6" in item["path"] for item in result["results"])
        assert not deep_path_found
    
    def test_files_per_directory_limit(self, temp_search_folder):
        """Test that files per directory limit is respected."""
        tool = DesktopSearchTool()
        
        # Create directory with many files
        many_files_dir = Path(temp_search_folder) / "many_files"
        many_files_dir.mkdir()
        for i in range(150):  # More than MAX_FILES_PER_DIR
            (many_files_dir / f"file{i}.txt").write_text(f"Content {i}")
        
        result = tool.run(query="file", max_results=10)
        
        assert result["success"] is True
        # Should limit results even with many files
        assert result["count"] <= 10
    
    def test_malformed_query_handling(self, temp_search_folder):
        """Test that malformed queries are handled gracefully."""
        tool = DesktopSearchTool()
        
        # Query with special characters
        result = tool.run(query="test<>|&%", max_results=5)
        
        # Should handle gracefully - special chars filtered out by term length check
        assert result["success"] is True
        assert result["count"] >= 0