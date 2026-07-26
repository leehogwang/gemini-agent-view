#!/usr/bin/env python3
"""Standalone check for resolve_new_session_workspace (Ctrl+N workspace targeting).

Plain assert-based script, no test framework. Run: python3 tests/test_agy_av_workspace.py
"""
import importlib.util
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE_PATH = os.path.join(REPO_ROOT, "bin", "agy-av.py")

spec = importlib.util.spec_from_file_location("agy_av", MODULE_PATH)
agy_av = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agy_av)

resolve_new_session_workspace = agy_av.resolve_new_session_workspace


def test_session_row_focused_returns_session_workspace():
    tree_items = [
        {"type": "header", "workspace": "/home/u/foo", "short_ws": "~/foo"},
        {"type": "session", "workspace": "/home/u/foo", "session": {"id": "abc"}},
    ]
    result = resolve_new_session_workspace(tree_items, 1, "/fallback")
    assert result == "/home/u/foo", f"expected /home/u/foo, got {result}"
    print("PASS: session row focused -> returns that session's workspace")


def test_header_row_focused_returns_header_workspace():
    tree_items = [
        {"type": "header", "workspace": "/home/u/bar", "short_ws": "~/bar"},
        {"type": "session", "workspace": "/home/u/bar", "session": {"id": "def"}},
    ]
    result = resolve_new_session_workspace(tree_items, 0, "/fallback")
    assert result == "/home/u/bar", f"expected /home/u/bar, got {result}"
    print("PASS: folder header row focused -> returns that header's workspace")


def test_empty_tree_items_returns_fallback():
    result = resolve_new_session_workspace([], 0, "/fallback")
    assert result == "/fallback", f"expected /fallback, got {result}"
    print("PASS: empty tree_items -> returns the fallback")


def test_out_of_range_idx_returns_fallback():
    tree_items = [{"type": "header", "workspace": "/home/u/baz", "short_ws": "~/baz"}]
    result = resolve_new_session_workspace(tree_items, 5, "/fallback")
    assert result == "/fallback", f"expected /fallback, got {result}"
    print("PASS: out-of-range current_tree_idx -> returns the fallback")


if __name__ == "__main__":
    test_session_row_focused_returns_session_workspace()
    test_header_row_focused_returns_header_workspace()
    test_empty_tree_items_returns_fallback()
    test_out_of_range_idx_returns_fallback()
    print("\nALL TESTS PASSED")
