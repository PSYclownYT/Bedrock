"""Intentionally duplicates a command name from 01_hello.py.

This should trigger duplicate command detection.
"""


def register(editor):
    return {
        "Plugin: Hello": lambda: editor.statusBar().showMessage("Duplicate command", 3000),
    }
