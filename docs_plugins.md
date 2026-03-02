# Plugin System Reference

This document describes the plugin-related functions and variables introduced in Bedrock.

## `main.py`

### `MarkdownEditor` plugin variables

- `self.plugin_errors: list[str]`
  - Stores non-fatal plugin load/validation error messages collected at startup.
  - Populated by `load_custom_plugins()`.
  - Displayed once by `show_plugin_errors()`.

- `self.plugin_commands: dict[str, callable]`
  - Stores successfully loaded plugin commands.
  - Keys are command labels shown in the command palette.
  - Values are no-argument callbacks executed from the palette.
  - Populated by `load_custom_plugins()` and merged into `self.commands` in `init_commands()`.

### `MarkdownEditor` plugin functions

- `load_custom_plugins(self) -> None`
  - Resolves plugin directory:
    - `BEDROCK_PLUGIN_DIR` env var (if set), else
    - `<vault>/.bedrock/plugins`
  - Calls `load_user_plugins(plugin_root, self)` from `plugin_system.py`.
  - Assigns returned `commands` and `errors` into editor state.

- `show_plugin_errors(self) -> None`
  - If `self.plugin_errors` is not empty, displays one warning dialog with all errors.
  - Does not terminate the application.

- `init_commands(self) -> None`
  - Initializes built-in command palette entries.
  - Merges plugin command mappings via `self.commands.update(self.plugin_commands)`.

### Status bar note

- A `QStatusBar` is explicitly installed with `self.setStatusBar(QStatusBar(self))` during editor initialization.
- This guarantees status-bar output from plugin callbacks is visible.

---

## `plugin_system.py`

### Type aliases and data structures

- `CommandMap = dict[str, Callable[[], None]]`
  - Canonical type for plugin command mappings.

- `PluginLoadResult`
  - Dataclass used as the return type for plugin loading.
  - Fields:
    - `commands: CommandMap` — aggregated valid commands.
    - `errors: list[str]` — per-plugin errors with filename context.

### Functions

- `_load_module(plugin_file: Path) -> ModuleType`
  - Imports one plugin file using `importlib.util.spec_from_file_location(...)`.
  - Raises if import spec cannot be created or module execution fails.

- `_validate_plugin_commands(plugin_name: str, commands: object) -> CommandMap`
  - Validates `register(editor)` return value.
  - Accepts `None` or `dict[str, callable]`.
  - Raises `TypeError` for invalid shape/types.

- `load_user_plugins(plugin_dir: Path, editor: object) -> PluginLoadResult`
  - Scans `plugin_dir` for `*.py` plugins.
  - Requires each plugin to expose callable `register(editor)`.
  - Aggregates valid commands.
  - Rejects duplicate command labels across plugins.
  - Captures all plugin errors (non-fatal) in `PluginLoadResult.errors`.

---

## `example_plugins/` reference

### `01_hello.py`
Valid plugin demonstrating command registration and editor interaction.

- `register(editor)`
  - Returns two commands:
    - `Plugin: Hello`
    - `Plugin: Show Vault Path`
  - Each command writes to status bar and also shows a `QMessageBox` for obvious visual confirmation.

### `02_invalid_return.py`
Invalid plugin for testing validator behavior.

- `register(editor)` returns list (invalid).
- Expected error: `register(editor) must return a dict[str, callable]`.

### `03_duplicate_name.py`
Invalid plugin for duplicate command testing.

- `register(editor)` defines `Plugin: Hello` which conflicts with `01_hello.py`.
- Expected duplicate-command error in plugin warnings.

### `04_missing_register.py`
Invalid plugin for missing symbol testing.

- No `register(editor)` function exported.
- Expected error: missing callable register function.
