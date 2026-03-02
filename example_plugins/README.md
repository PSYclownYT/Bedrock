# Bedrock Plugin Examples

These plugins are meant to be copied into your active plugin folder to test **all plugin loader behaviors**:

- successful command registration
- plugin load failure reporting
- duplicate command detection
- command callbacks that interact with the editor instance

## How to use

1. Create your plugin folder (if needed):
   - default: `<your-vault>/.bedrock/plugins`
   - or set `BEDROCK_PLUGIN_DIR` to any folder you want.
2. Copy one or more `*.py` files from this folder into that plugin folder.
3. Start Bedrock and open the command palette (`Ctrl+P`).

## Suggested test flow

### 1) Happy path
Copy only:
- `01_hello.py`

Expected:
- command palette includes `Plugin: Hello`
- command palette includes `Plugin: Show Vault Path`

### 2) Error path (bad return type)
Add:
- `02_invalid_return.py`

Expected:
- warning dialog appears listing `02_invalid_return.py`
- valid commands from `01_hello.py` still load

### 3) Duplicate command name
Add:
- `03_duplicate_name.py`

Expected:
- warning dialog includes duplicate-command error
- first plugin command remains available

### 4) Missing register(editor)
Add:
- `04_missing_register.py`

Expected:
- warning dialog includes missing register function error

## Notes

- These files are examples only; they are **not** auto-loaded from this `example_plugins` folder.
- You can start from `01_hello.py` and modify it for your own commands.
