from __future__ import annotations

import os
import tempfile
import json
from pathlib import Path

import pytest

from app.storage.runtime_settings import (
    get_api_keys,
    set_api_keys,
    sync_api_keys_to_env,
    sync_settings_to_obj,
)


class TestMergeKeysBehavior:
    """Test that merge behavior preserves existing values when incoming is empty."""
    
    def test_get_api_keys_priorizes_saved_over_env(self):
        """Test that saved keys in runtime_settings.json take priority over env."""
        # Create a temporary runtime_settings.json
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "runtime_settings.json"
            settings_file.write_text(json.dumps({
                "api_keys": {
                    "groq": "saved_groq_key",
                    "gemini": "saved_gemini_key",
                }
            }))
            
            # Mock the DATA_DIR and RUNTIME_SETTINGS_FILE
            import app.storage.runtime_settings as rs
            original_data_dir = rs.DATA_DIR
            original_file = rs.RUNTIME_SETTINGS_FILE
            
            rs.DATA_DIR = tmp
            rs.RUNTIME_SETTINGS_FILE = str(settings_file)
            
            try:
                # Set env vars
                os.environ["GROQ_API_KEY"] = "env_groq_key"
                os.environ["GEMINI_API_KEY"] = "env_gemini_key"
                
                keys = get_api_keys()
                
                # Saved keys should take priority
                assert keys["groq"] == "saved_groq_key"
                assert keys["gemini"] == "saved_gemini_key"
            finally:
                rs.DATA_DIR = original_data_dir
                rs.RUNTIME_SETTINGS_FILE = original_file
                # Clean up env
                os.environ.pop("GROQ_API_KEY", None)
                os.environ.pop("GEMINI_API_KEY", None)
    
    def test_set_api_keys_updates_env_and_file(self):
        """Test that set_api_keys updates both environment and file."""
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "runtime_settings.json"
            
            import app.storage.runtime_settings as rs
            original_data_dir = rs.DATA_DIR
            original_file = rs.RUNTIME_SETTINGS_FILE
            
            rs.DATA_DIR = tmp
            rs.RUNTIME_SETTINGS_FILE = str(settings_file)
            
            try:
                # Set keys
                result = set_api_keys({
                    "groq": "new_groq_key",
                    "gemini": "new_gemini_key",
                })
                
                # Check env was updated
                assert os.environ.get("GROQ_API_KEY") == "new_groq_key"
                assert os.environ.get("GEMINI_API_KEY") == "new_gemini_key"
                
                # Check file was updated
                data = json.loads(settings_file.read_text())
                assert data["api_keys"]["groq"]["credential_refs"]
                assert data["api_keys"]["gemini"]["credential_refs"]
                assert "new_groq_key" not in settings_file.read_text()
                
                # Check return value
                assert result["groq"] == "new_groq_key"
                assert result["gemini"] == "new_gemini_key"
            finally:
                rs.DATA_DIR = original_data_dir
                rs.RUNTIME_SETTINGS_FILE = original_file
                os.environ.pop("GROQ_API_KEY", None)
                os.environ.pop("GEMINI_API_KEY", None)
    
    def test_set_api_keys_with_multiple_keys(self):
        """Test that set_api_keys handles comma-separated multiple keys."""
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "runtime_settings.json"
            
            import app.storage.runtime_settings as rs
            original_data_dir = rs.DATA_DIR
            original_file = rs.RUNTIME_SETTINGS_FILE
            
            rs.DATA_DIR = tmp
            rs.RUNTIME_SETTINGS_FILE = str(settings_file)
            
            try:
                # Set multiple keys
                result = set_api_keys({
                    "groq": "key1,key2,key3",
                })
                
                # Check both env vars are set with the same value
                assert os.environ.get("GROQ_API_KEY") == "key1,key2,key3"
                assert os.environ.get("GROQ_API_KEYS") == "key1,key2,key3"
                
                # O arquivo guarda uma referência para cada chave.
                data = json.loads(settings_file.read_text())
                assert len(data["api_keys"]["groq"]["credential_refs"]) == 3
                assert rs._read()["api_keys"]["groq"] == "key1,key2,key3"
            finally:
                rs.DATA_DIR = original_data_dir
                rs.RUNTIME_SETTINGS_FILE = original_file
                os.environ.pop("GROQ_API_KEY", None)
                os.environ.pop("GROQ_API_KEYS", None)
    
    def test_sync_settings_to_obj_updates_all_fields(self):
        """Test that sync_settings_to_obj updates Settings object correctly."""
        from app.config import Settings
        
        with tempfile.TemporaryDirectory() as tmp:
            settings_file = Path(tmp) / "runtime_settings.json"
            settings_file.write_text(json.dumps({
                "api_keys": {
                    "groq": "test_groq",
                    "gemini": "test_gemini",
                },
                "llm_provider": "groq",
                "tts_provider": "fish",
                "oxyy_models": {
                    "chat": "gpt-4o-mini",
                    "tts": "tts-1-hd",
                }
            }))
            
            import app.storage.runtime_settings as rs
            original_data_dir = rs.DATA_DIR
            original_file = rs.RUNTIME_SETTINGS_FILE
            
            rs.DATA_DIR = tmp
            rs.RUNTIME_SETTINGS_FILE = str(settings_file)
            
            try:
                settings = Settings()
                sync_settings_to_obj(settings)
                
                # Check API keys
                assert settings.groq_api_key == "test_groq"
                assert settings.gemini_api_key == "test_gemini"
                assert len(settings.groq_api_keys) == 1
                assert settings.groq_api_keys[0] == "test_groq"
                
                # Check providers
                assert settings.llm_provider == "groq"
                assert settings.tts_provider == "fish"
                
                # Check Oxyy models
                assert settings.oxyy_chat_model == "gpt-4o-mini"
                assert settings.oxyy_tts_model == "tts-1-hd"
            finally:
                rs.DATA_DIR = original_data_dir
                rs.RUNTIME_SETTINGS_FILE = original_file
