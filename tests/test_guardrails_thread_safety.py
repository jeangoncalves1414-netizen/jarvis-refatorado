from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from app.core.guardrails import ToolGuardrails


class TestGuardrailsThreadSafety:
    """Test thread safety of ToolGuardrails."""
    
    def test_concurrent_before_call(self):
        """Test that concurrent before_call calls don't cause race conditions."""
        guardrails = ToolGuardrails(repeat_limit=100, no_progress_limit=100)
        
        def make_call(tool: str, idx: int):
            for _ in range(50):
                decision = guardrails.before_call(tool, {"idx": idx})
                if not decision.allow:
                    return False
            return True
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_call, "test_tool", i) for i in range(10)]
            results = [f.result() for f in futures]
        
        # All should succeed (no false positives)
        assert all(results)
    
    def test_concurrent_after_call(self):
        """Test that concurrent after_call calls don't cause race conditions."""
        guardrails = ToolGuardrails(repeat_limit=100, no_progress_limit=100)
        
        def make_call(tool: str, idx: int):
            for _ in range(50):
                guardrails.before_call(tool, {"idx": idx})
                guardrails.after_call(tool, {"idx": idx}, f"result_{idx}")
            return True
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_call, "test_tool", i) for i in range(10)]
            results = [f.result() for f in futures]
        
        # All should succeed
        assert all(results)
    
    def test_repeat_limit_with_concurrent_calls(self):
        """Test that repeat limit is enforced correctly under concurrent load."""
        guardrails = ToolGuardrails(repeat_limit=5, no_progress_limit=100)
        
        def make_call(tool: str, idx: int):
            for _ in range(10):
                decision = guardrails.before_call(tool, {"idx": idx})
                if not decision.allow:
                    return False
            return True
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_call, "test_tool", i) for i in range(3)]
            results = [f.result() for f in futures]
        
        # At least some should be blocked due to repeat limit
        # (with 3 threads * 10 calls each = 30 calls, limit is 5 per key)
        # This test verifies the limit is actually enforced, not that all fail
        assert not all(results)
    
    def test_reset_during_concurrent_calls(self):
        """Test that reset works correctly while calls are happening."""
        guardrails = ToolGuardrails(repeat_limit=100, no_progress_limit=100)
        
        def make_calls(tool: str, idx: int):
            for _ in range(20):
                guardrails.before_call(tool, {"idx": idx})
                if idx == 0 and guardrails._calls.get(guardrails._key(tool, {"idx": 0}), 0) == 10:
                    guardrails.reset()
            return True
        
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_calls, "test_tool", i) for i in range(5)]
            results = [f.result() for f in futures]
        
        # All should succeed
        assert all(results)
