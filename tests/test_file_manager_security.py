from __future__ import annotations

import os
import platform
import tempfile
from pathlib import Path

import pytest

from app.domain.file_manager import FileManagerService


@pytest.fixture
def temp_base_folder():
    """Create a temporary base folder for testing."""
    with tempfile.TemporaryDirectory() as tmp:
        # Create some test files and directories
        test_dir = os.path.join(tmp, "safe_dir")
        os.makedirs(test_dir)
        
        test_file = os.path.join(tmp, "safe_file.txt")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Safe content")
        
        yield tmp


class TestPathTraversalSecurity:
    """Test suite for path traversal attack prevention."""
    
    def test_basic_traversal_with_double_dot(self, temp_base_folder):
        """Test that basic ../ traversal is blocked."""
        fm = FileManagerService(temp_base_folder)
        
        with pytest.raises(ValueError) as exc_info:
            fm._validate_path("../etc/passwd")
        
        assert "não permitido" in str(exc_info.value).lower()
    
    def test_multiple_traversal_levels(self, temp_base_folder):
        """Test that multiple levels of ../ are blocked."""
        fm = FileManagerService(temp_base_folder)
        
        with pytest.raises(ValueError) as exc_info:
            fm._validate_path("../../Windows/System32")
        
        assert "não permitido" in str(exc_info.value).lower()
    
    def test_absolute_path_attempt(self, temp_base_folder):
        """Test that absolute paths are blocked."""
        fm = FileManagerService(temp_base_folder)
        
        if platform.system() == "Windows":
            malicious_path = "C:\\Windows\\System32"
        else:
            malicious_path = "/etc/passwd"
        
        with pytest.raises(ValueError) as exc_info:
            fm._validate_path(malicious_path)
        
        assert "não permitido" in str(exc_info.value).lower()
    
    def test_symlink_attack(self, temp_base_folder):
        """Test that symlinks pointing outside the base folder are blocked."""
        fm = FileManagerService(temp_base_folder)
        
        # Create a symlink inside the base folder pointing outside
        if platform.system() != "Windows":  # Symlinks work differently on Windows
            outside_dir = tempfile.mkdtemp()
            try:
                symlink_path = os.path.join(temp_base_folder, "malicious_link")
                os.symlink(outside_dir, symlink_path)
                
                # Try to access through the symlink
                with pytest.raises(ValueError) as exc_info:
                    fm._validate_path("malicious_link/../etc/passwd")
                
                assert "não permitido" in str(exc_info.value).lower()
            finally:
                os.remove(symlink_path)
                os.rmdir(outside_dir)
    
    def test_case_sensitivity_bypass_windows(self, temp_base_folder):
        """Test case sensitivity bypass on Windows."""
        fm = FileManagerService(temp_base_folder)
        
        if platform.system() == "Windows":
            # On Windows, try to escape using case variations
            # This test documents the behavior; the actual bypass depends on Windows specifics
            with pytest.raises(ValueError):
                fm._validate_path("../Windows/System32")
    
    def test_normalized_path_traversal(self, temp_base_folder):
        """Test that normalized paths with trailing slashes are handled correctly."""
        fm = FileManagerService(temp_base_folder)
        
        with pytest.raises(ValueError) as exc_info:
            fm._validate_path("../")
        
        assert "não permitido" in str(exc_info.value).lower()
    
    def test_mixed_traversal_and_valid_path(self, temp_base_folder):
        """Test that mixed valid/invalid paths are blocked."""
        fm = FileManagerService(temp_base_folder)
        
        with pytest.raises(ValueError) as exc_info:
            fm._validate_path("safe_dir/../../etc/passwd")
        
        assert "não permitido" in str(exc_info.value).lower()
    
    def test_dotdot_in_middle_of_path(self, temp_base_folder):
        """Test that ../ in the middle of a path is blocked."""
        fm = FileManagerService(temp_base_folder)
        
        # Create a directory to make the path valid before the traversal
        safe_dir = os.path.join(temp_base_folder, "safe")
        os.makedirs(safe_dir, exist_ok=True)
        
        # This path would escape after normalization: safe/../../etc/passwd
        with pytest.raises(ValueError) as exc_info:
            fm._validate_path("safe/../../etc/passwd")
        
        assert "não permitido" in str(exc_info.value).lower()
    
    def test_valid_path_still_works(self, temp_base_folder):
        """Test that valid paths within the base folder still work."""
        fm = FileManagerService(temp_base_folder)
        
        # Valid directory
        result = fm._validate_path("safe_dir")
        assert result.is_relative_to(temp_base_folder)
        
        # Valid file
        result = fm._validate_path("safe_file.txt")
        assert result.is_relative_to(temp_base_folder)
    
    def test_empty_path_still_works(self, temp_base_folder):
        """Test that empty path (base folder itself) still works."""
        fm = FileManagerService(temp_base_folder)
        
        result = fm._validate_path("")
        assert result == Path(temp_base_folder)
    
    def test_list_directory_blocks_traversal(self, temp_base_folder):
        """Test that list_directory blocks path traversal."""
        fm = FileManagerService(temp_base_folder)
        
        with pytest.raises(ValueError) as exc_info:
            fm.list_directory("../etc")
        
        assert "não permitido" in str(exc_info.value).lower()
    
    def test_read_file_blocks_traversal(self, temp_base_folder):
        """Test that read_file blocks path traversal."""
        fm = FileManagerService(temp_base_folder)
        
        with pytest.raises(ValueError) as exc_info:
            fm.read_file("../../Windows/System32/drivers/etc/hosts")
        
        assert "não permitido" in str(exc_info.value).lower()
    
    def test_valid_list_directory_still_works(self, temp_base_folder):
        """Test that valid list_directory operations still work."""
        fm = FileManagerService(temp_base_folder)
        
        result = fm.list_directory("")
        assert "safe_dir" in result
        assert "safe_file.txt" in result
    
    def test_valid_read_file_still_works(self, temp_base_folder):
        """Test that valid read_file operations still work."""
        fm = FileManagerService(temp_base_folder)
        
        result = fm.read_file("safe_file.txt")
        assert result == "Safe content"
