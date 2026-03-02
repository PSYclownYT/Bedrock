"""Valid example plugin.

Demonstrates:
- registering multiple commands
- using the passed `editor` object
- showing both a status-bar message and a visible confirmation dialog
"""

from PySide6.QtWidgets import QMessageBox


def register(editor):
    """Return command callbacks for the Bedrock command palette.

    Args:
        editor: `MarkdownEditor` instance provided by Bedrock.

    Returns:
        dict[str, callable]: command labels mapped to no-arg callbacks.
    """

    def hello_command():
        editor.statusBar().showMessage("Hello from plugin!", 3000)
        QMessageBox.information(editor, "Plugin: Hello", "Hello from plugin!")

    def show_vault_path():
        message = f"Vault: {editor.root_dir}"
        editor.statusBar().showMessage(message, 5000)
        QMessageBox.information(editor, "Plugin: Show Vault Path", message)

    return {
        "Plugin: Hello": hello_command,
        "Plugin: Show Vault Path": show_vault_path,
    }
