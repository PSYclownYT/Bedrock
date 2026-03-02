from __future__ import annotations

"""Plugin loader for Bedrock command-palette extensions.

This module discovers `*.py` plugin files, imports each module, and executes a
required `register(editor)` function. That registration function may return a
mapping of command names to callables; the app merges those commands into the
command palette.
"""

from dataclasses import dataclass, field
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable

#: Command mapping expected from plugins.
#: - key: label shown in the command palette
#: - value: no-arg callback executed when selected
CommandMap = dict[str, Callable[[], None]]


@dataclass
class PluginLoadResult:
    """Result payload for plugin discovery and validation.

    Attributes:
        commands: Aggregated valid commands from all successfully loaded plugins.
        errors: Human-readable load/validation errors for failed plugins.
    """

    commands: CommandMap = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _load_module(plugin_file: Path) -> ModuleType:
    """Import a plugin file as an isolated module object.

    Args:
        plugin_file: Python file to import.

    Returns:
        Imported module object.

    Raises:
        RuntimeError: If import spec cannot be created.
        Any import exception raised while executing the plugin module.
    """

    module_name = f"bedrock_user_plugin_{plugin_file.stem}_{abs(hash(plugin_file))}"
    spec = importlib.util.spec_from_file_location(module_name, plugin_file)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to build import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_plugin_commands(plugin_name: str, commands: object) -> CommandMap:
    """Validate a plugin's command mapping contract.

    Plugins may return `None` (equivalent to no commands), or a dictionary where
    each key is a string command label and each value is callable.

    Args:
        plugin_name: Plugin stem name used in diagnostic messages.
        commands: Value returned by `register(editor)`.

    Returns:
        Normalized and validated command mapping.

    Raises:
        TypeError: If command mapping shape/types are invalid.
    """

    if commands is None:
        return {}
    if not isinstance(commands, dict):
        raise TypeError("register(editor) must return a dict[str, callable]")

    validated: CommandMap = {}
    for command_name, callback in commands.items():
        if not isinstance(command_name, str):
            raise TypeError("Plugin command names must be strings")
        if not callable(callback):
            raise TypeError(f"Command '{command_name}' in plugin '{plugin_name}' is not callable")
        validated[command_name] = callback
    return validated


def load_user_plugins(plugin_dir: Path, editor: object) -> PluginLoadResult:
    """Discover and load user plugins from a directory.

    Contract for each plugin file:
    - expose a callable `register(editor)` symbol
    - return `dict[str, callable]` or `None`

    Behavior:
    - every plugin load failure is captured in `errors`
    - valid plugins continue loading even if some fail
    - duplicate command labels across plugins are rejected

    Args:
        plugin_dir: Directory that contains `*.py` plugin files.
        editor: Application editor instance passed to `register(editor)`.

    Returns:
        `PluginLoadResult` containing aggregated commands and errors.
    """

    result = PluginLoadResult()
    if not plugin_dir.exists():
        return result

    for plugin_file in sorted(plugin_dir.glob("*.py")):
        try:
            module = _load_module(plugin_file)
            register = getattr(module, "register", None)
            if register is None or not callable(register):
                raise AttributeError("Missing callable register(editor) function")

            plugin_commands = _validate_plugin_commands(plugin_file.stem, register(editor))
            for command_name, callback in plugin_commands.items():
                if command_name in result.commands:
                    raise ValueError(f"Duplicate command name '{command_name}'")
                result.commands[command_name] = callback
        except Exception as exc:  # noqa: BLE001 - surface all plugin errors to user
            result.errors.append(f"{plugin_file.name}: {exc}")

    return result
