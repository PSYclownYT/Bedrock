"""Valid example plugin.

Demonstrates:
- registering multiple commands
- using the passed `editor` object
- interacting with Qt UI helpers already imported in main.py
"""


def register(editor):
    def hello_command():
        # Uses the existing Qt import available in main.py via editor context.
        editor.statusBar().showMessage("Hello from plugin!", 3000)

    def show_vault_path():
        editor.statusBar().showMessage(f"Vault: {editor.root_dir}", 5000)

    return {
        "Plugin: Hello": hello_command,
        "Plugin: Show Vault Path": show_vault_path,
    }
