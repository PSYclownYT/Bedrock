from __future__ import annotations

from dataclasses import dataclass, field
import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Callable

CommandMap = dict[str, Callable[[], None]]


@dataclass
class PluginLoadResult:
    commands: CommandMap = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


def _load_module(plugin_file: Path) -> ModuleType:
    module_name = f"bedrock_user_plugin_{plugin_file.stem}_{abs(hash(plugin_file))}"
    spec = importlib.util.spec_from_file_location(module_name, plugin_file)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to build import spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate_plugin_commands(plugin_name: str, commands: object) -> CommandMap:
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
