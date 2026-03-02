import sys, re, os, shutil, subprocess, webbrowser
from pathlib import Path
import markdown
from rapidfuzz import fuzz, process
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QTextEdit, QTextBrowser, QVBoxLayout, QWidget,
    QSplitter, QFileSystemModel, QToolBar, QTabWidget, QLineEdit, QDialog, QListWidget,
    QDockWidget, QListWidgetItem, QMessageBox, QInputDialog, QMenu, QFileDialog, QLabel
)
from PySide6.QtCore import Qt, QModelIndex, QPoint

import builder  # your external builder script

# =======================================
# --- Command Palette Dialog
# =======================================
class CommandPalette(QDialog):
    def __init__(self, parent, commands: dict):
        super().__init__(parent)
        self.setWindowTitle("Command Palette")
        self.setModal(True)
        self.resize(500, 400)
        self.setStyleSheet("""
            QDialog { background-color: #2c2c3a; color: #d4d4d4; }
            QLineEdit { background-color: #3b3b4b; color: white; border: none; padding: 8px; }
            QListWidget { background-color: #1e1e2f; color: white; border: none; }
            QListWidget::item:selected { background-color: #4fc3f7; color: black; }
        """)

        layout = QVBoxLayout(self)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Type a command...")
        layout.addWidget(self.search_bar)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        self.commands = commands
        self.filtered = list(commands.keys())
        self.refresh_list()

        self.search_bar.textChanged.connect(self.filter_commands)
        self.list_widget.itemDoubleClicked.connect(self.execute_selected)

        self.search_bar.setFocus()

    def refresh_list(self):
        self.list_widget.clear()
        for cmd in self.filtered:
            self.list_widget.addItem(cmd)

    def filter_commands(self, text):
        if not text.strip():
            self.filtered = list(self.commands.keys())
        else:
            self.filtered = [cmd for cmd in self.commands if text.lower() in cmd.lower()]
        self.refresh_list()

    def execute_selected(self, item=None):
        if not item:
            item = self.list_widget.currentItem()
        if item:
            action = self.commands.get(item.text())
            if callable(action):
                action()
        self.accept()


# =======================================
# --- Main Window
# =======================================
class MarkdownEditor(QMainWindow):
    def __init__(self, root_dir: Path):
        super().__init__()
        self.root_dir = root_dir
        self.current_file = None

        # --- File Tree
        self.model = QFileSystemModel()
        self.model.setRootPath(str(self.root_dir))
        self.model.setNameFilters(["*.md"])
        self.model.setNameFilterDisables(False)

        self.tree = QTreeView()
        self.tree.setModel(self.model)
        self.tree.setRootIndex(self.model.index(str(self.root_dir)))
        self.tree.doubleClicked.connect(self.open_file_in_tab)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.show_context_menu)

        # --- Tabs
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)

        # --- Layout
        splitter = QSplitter()
        splitter.addWidget(self.tree)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 1)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(splitter)
        self.setCentralWidget(container)

        # --- Toolbar
        toolbar = QToolBar("Main Toolbar")
        self.addToolBar(toolbar)

        new_note_action = QAction("New Note", self)
        new_note_action.triggered.connect(lambda: self.create_new_note(None))
        toolbar.addAction(new_note_action)

        new_group_action = QAction("New Group", self)
        new_group_action.triggered.connect(lambda: self.create_new_folder(None))
        toolbar.addAction(new_group_action)

        preview_action = QAction("Open Preview in Browser", self)
        preview_action.triggered.connect(self.open_preview_in_browser)
        toolbar.addAction(preview_action)

        command_action = QAction("Command Palette", self)
        command_action.setShortcut(QKeySequence("Ctrl+P"))
        command_action.triggered.connect(self.open_command_palette)
        toolbar.addAction(command_action)
        self.addAction(command_action)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search notes...")
        self.search_bar.returnPressed.connect(self.search_notes)
        toolbar.addWidget(self.search_bar)

        # --- Tags Dock
        self.tag_pane = QListWidget()
        self.tag_pane.itemClicked.connect(self.filter_by_tag)
        dock = QDockWidget("Tags", self)
        dock.setWidget(self.tag_pane)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

        self.setWindowTitle("Bedrock Notes (with Command Palette)")
        self.resize(1300, 850)

        self.build_tag_index()
        self.init_commands()

    # ==================================================
    # --- Command Palette
    # ==================================================
    def init_commands(self):
        """Define available commands."""
        self.commands = {
            "Create New Note": lambda: self.create_new_note(None),
            "Open Preview in Browser": self.open_preview_in_browser,
            "Search Notes": self.search_notes,
            "Show Tags": lambda: QMessageBox.information(self, "Tags", ", ".join(self.tags.keys())),
            "Rebuild HTML Vault": lambda: builder.build_vault(self.root_dir),
            "Open Graph View in Browser": lambda: webbrowser.open(f"file:///{self.root_dir/'html_preview'/'graph.html'}"),
            "Quit Application": self.close
        }

    def open_command_palette(self):
        dialog = CommandPalette(self, self.commands)
        dialog.exec()

    # ==================================================
    # --- Context Menu & File Operations
    # ==================================================
    def show_context_menu(self, pos: QPoint):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        file_path = Path(self.model.filePath(index))
        menu = QMenu()
        if file_path.is_file():
            menu.addAction("Rename").triggered.connect(lambda: self.rename_note_dialog(file_path))
            menu.addAction("Delete").triggered.connect(lambda: self.delete_note_dialog(file_path))
            menu.addAction("Move").triggered.connect(lambda: self.move_note_dialog(file_path))
        else:
            menu.addAction("New Note Here").triggered.connect(lambda: self.create_new_note(file_path))
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def create_new_note(self, parent_dir=None):
        if parent_dir is None or isinstance(parent_dir, bool):
            index = self.tree.currentIndex()
            parent_dir = self.root_dir if not index.isValid() else Path(self.model.filePath(index)).parent
        name, ok = QInputDialog.getText(self, "New Note", "Enter note name:")
        if ok and name:
            if not name.endswith(".md"):
                name += ".md"
            new_path = parent_dir / name
            new_path.write_text(f"# {name.replace('.md', '')}\n", encoding="utf-8")
            self.model.setRootPath(str(self.root_dir))

    def create_new_folder(self, parent_dir=None):
        if parent_dir is None or isinstance(parent_dir, bool):
            index = self.tree.currentIndex()
            parent_dir = self.root_dir if not index.isValid() else Path(self.model.filePath(index)).parent
        name, ok = QInputDialog.getText(self, "New Note", "Enter note name:")
        if ok and name:
            os.mkdir(str(parent_dir) + "\\" + name)
            self.model.setRootPath(str(self.root_dir))

    def rename_note_dialog(self, file_path: Path):
        new_name, ok = QInputDialog.getText(self, "Rename", "New name:", text=file_path.stem)
        if ok and new_name:
            file_path.rename(file_path.with_name(new_name + ".md"))

    def delete_note_dialog(self, file_path: Path):
        if QMessageBox.question(self, "Delete?", f"Delete {file_path.name}?") == QMessageBox.Yes:
            file_path.unlink(missing_ok=True)

    def move_note_dialog(self, file_path: Path):
        dest = QFileDialog.getExistingDirectory(self, "Select Destination", str(self.root_dir))
        if dest:
            shutil.move(str(file_path), str(Path(dest) / file_path.name))

    # ==================================================
    # --- Editor Tabs & Live Preview
    # ==================================================
    def open_file_in_tab(self, index: QModelIndex):
        file_path = Path(self.model.filePath(index))
        if file_path.is_dir():
            return
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).property("path") == str(file_path):
                self.tabs.setCurrentIndex(i)
                return
        editor_splitter = QSplitter(Qt.Horizontal)
        editor = QTextEdit()
        preview = QTextBrowser()
        preview.setOpenExternalLinks(True)
        preview.setStyleSheet("background-color:#1e1e2f;color:#d4d4d4;padding:12px;")
        editor.setPlainText(file_path.read_text(encoding="utf-8"))
        editor.textChanged.connect(lambda: self.update_preview(editor, preview))
        editor.textChanged.connect(lambda: self.save_file(editor))
        editor.setProperty("path", str(file_path))
        editor_splitter.addWidget(editor)
        editor_splitter.addWidget(preview)
        self.tabs.addTab(editor_splitter, file_path.stem)
        self.tabs.setCurrentWidget(editor_splitter)
        self.update_preview(editor, preview)
        self.current_file = file_path

    def update_preview(self, editor, preview):
        html = markdown.markdown(editor.toPlainText(), extensions=["fenced_code", "tables"])
        preview.setHtml(f"<html><body style='font-family:Segoe UI'>{html}</body></html>")

    def save_file(self, editor):
        Path(editor.property("path")).write_text(editor.toPlainText(), encoding="utf-8")
        self.build_tag_index()

    def close_tab(self, index):
        self.tabs.removeTab(index)

    # ==================================================
    # --- Tags & Builder
    # ==================================================
    def open_preview_in_browser(self):
        builder.build_vault(self.root_dir)
        graph = self.root_dir / "html_preview" / "graph.html"
        webbrowser.open_new_tab(f"file:///{graph}")

    def build_tag_index(self):
        self.tags = {}
        for md_file in self.root_dir.glob("**/*.md"):
            for tag in re.findall(r"\{\{(.*?)\}\}", md_file.read_text(encoding="utf-8")):
                self.tags.setdefault(tag, []).append(md_file)
        self.tag_pane.clear()
        for tag, files in sorted(self.tags.items()):
            self.tag_pane.addItem(f"{{{{{tag}}}}} ({len(files)})")

    def filter_by_tag(self, item: QListWidgetItem):
        tag = re.findall(r"\{\{(.*?)\}\}", item.text())[0]
        notes = self.tags.get(tag, [])
        QMessageBox.information(self, f"{{{{{tag}}}}}", "\n".join(n.name for n in notes))

    def search_notes(self):
        query = self.search_bar.text().strip()
        if not query:
            return
        notes = list(self.root_dir.glob("**/*.md"))
        text_map = {n: n.read_text(encoding="utf-8") for n in notes}
        results = process.extract(query, text_map.keys(), scorer=fuzz.partial_ratio, limit=10)
        msg = "\n".join(f"{p.name} ({s}%)" for p, s, _ in results)
        QMessageBox.information(self, "Search Results", msg or "No matches found.")


# =======================================
# --- Entry Point
# =======================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    bedrock_vault = Path(os.path.expanduser("~/Documents/Bedrock"))
    if not bedrock_vault.exists():
        QMessageBox.critical(None, "Error", f"Vault not found at:\n{bedrock_vault}")
        sys.exit(1)

    folder = QFileDialog.getExistingDirectory(None, "Select Folder in Bedrock Vault", str(bedrock_vault))
    if not folder:
        sys.exit(0)

    window = MarkdownEditor(Path(folder))
    window.show()
    sys.exit(app.exec())
