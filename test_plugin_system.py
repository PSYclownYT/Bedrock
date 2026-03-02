import tempfile
from pathlib import Path
import unittest

from plugin_system import load_user_plugins


class DummyEditor:
    def __init__(self):
        self.events = []


class PluginLoaderTests(unittest.TestCase):
    def test_loads_valid_plugin_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            (plugin_dir / "hello.py").write_text(
                """
def register(editor):
    return {
        \"Say Hello\": lambda: editor.events.append(\"hello\")
    }
""".strip(),
                encoding="utf-8",
            )

            editor = DummyEditor()
            result = load_user_plugins(plugin_dir, editor)

            self.assertEqual(result.errors, [])
            self.assertIn("Say Hello", result.commands)
            result.commands["Say Hello"]()
            self.assertEqual(editor.events, ["hello"])

    def test_collects_errors_for_invalid_plugins(self):
        with tempfile.TemporaryDirectory() as tmp:
            plugin_dir = Path(tmp)
            (plugin_dir / "broken.py").write_text(
                """
def register(editor):
    return [\"not a dict\"]
""".strip(),
                encoding="utf-8",
            )

            result = load_user_plugins(plugin_dir, DummyEditor())
            self.assertEqual(result.commands, {})
            self.assertEqual(len(result.errors), 1)
            self.assertIn("register(editor) must return a dict", result.errors[0])


if __name__ == "__main__":
    unittest.main()
