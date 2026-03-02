"""Intentionally invalid plugin to test error handling.

This should trigger:
"register(editor) must return a dict[str, callable]"
"""


def register(editor):
    return ["this", "is", "invalid"]
