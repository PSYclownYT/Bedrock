import sys, re, os, shutil, subprocess
from pathlib import Path
import markdown
import webbrowser
import networkx as nx
import matplotlib.pyplot as plt
from rapidfuzz import fuzz, process
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTreeView, QTextEdit, QVBoxLayout, QWidget,
    QSplitter, QFileSystemModel, QToolBar, QTabWidget, QLineEdit,
    QListWidget, QDockWidget, QListWidgetItem, QMessageBox, QInputDialog, QMenu, QFileDialog
)
from PySide6.QtCore import Qt, QModelIndex, QPoint


class MarkdownEditor(QMainWindow):
    def __init__(self, root_dir):
        super().__init__()
        self.root_dir = Path(root_dir)
        self.current_file = None

        # --- File tree
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
        new_note_action.triggered.connect(self.create_new_note)
        toolbar.addAction(new_note_action)

        preview_action = QAction("Open Preview in Browser", self)
        preview_action.triggered.connect(self.open_preview_in_browser)
        toolbar.addAction(preview_action)

        graph_action = QAction("Graph View", self)
        graph_action.triggered.connect(self.show_graph_view)
        toolbar.addAction(graph_action)

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

        self.setWindowTitle("Obsidian Clone (Advanced)")
        self.resize(1200, 800)

        self.build_tag_index()

    # ============================
    # --- Context Menu
    # ============================
    def show_context_menu(self, pos: QPoint):
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        file_path = Path(self.model.filePath(index))
        menu = QMenu()

        if file_path.is_file():
            rename_action = menu.addAction("Rename Note")
            rename_action.triggered.connect(lambda: self.rename_note_dialog(file_path))

            move_action = menu.addAction("Move to Folder")
            move_action.triggered.connect(lambda: self.move_note_dialog(file_path))

            show_action = menu.addAction("Show in Explorer")
            show_action.triggered.connect(lambda: self.show_in_explorer(file_path))

            delete_action = menu.addAction("Delete Note")
            delete_action.triggered.connect(lambda: self.delete_note_dialog(file_path))
        else:
            new_action = menu.addAction("New Note Here")
            new_action.triggered.connect(lambda: self.create_new_note(file_path))

            new_folder_action = menu.addAction("Create Folder")
            new_folder_action.triggered.connect(lambda: self.create_folder_dialog(file_path))

            show_action = menu.addAction("Show in Explorer")
            show_action.triggered.connect(lambda: self.show_in_explorer(file_path))

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    # ============================
    # --- File Operations
    # ============================
    def create_new_note(self):
        index = self.tree.currentIndex()
        if not index.isValid():
            parent_dir = Path(self.root_dir)
        else:
            path = Path(self.model.filePath(index))
            parent_dir = path if path.is_dir() else path.parent

        # Ask for the new file name
        name, ok = QInputDialog.getText(self, "New Note", "Enter note name:")
        if ok and name:
            if not name.endswith(".md"):
                name += ".md"
            new_path = parent_dir / name
            if not new_path.exists():
                new_path.write_text("# " + name.replace(".md", "") + "\n")
                self.model.setRootPath(self.root_dir)
                self.tree.setRootIndex(self.model.index(self.root_dir))
            else:
                QMessageBox.warning(self, "File Exists", f"{new_path.name} already exists.")

    def create_folder_dialog(self, parent_dir: Path):
        name, ok = QInputDialog.getText(self, "Create Folder", "Enter folder name:")
        if not ok or not name:
            return
        new_folder = parent_dir / name
        try:
            new_folder.mkdir(parents=True, exist_ok=False)
            self.model.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create folder:\n{e}")

    def move_note_dialog(self, file_path: Path):
        dest = QFileDialog.getExistingDirectory(self, "Select Destination Folder", str(self.root_dir))
        if not dest:
            return
        dest_path = Path(dest) / file_path.name
        try:
            shutil.move(str(file_path), str(dest_path))
            self.model.refresh()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to move note:\n{e}")

    def show_in_explorer(self, file_path: Path):
        try:
            if os.name == "nt":
                subprocess.run(["explorer", "/select,", str(file_path)], check=False)
            elif sys.platform == "darwin":
                subprocess.run(["open", "-R", str(file_path)], check=False)
            else:
                subprocess.run(["xdg-open", str(file_path.parent)], check=False)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Cannot open in explorer:\n{e}")

    def rename_note_dialog(self, file_path: Path):
        new_name, ok = QInputDialog.getText(self, "Rename Note", "New name:", text=file_path.stem)
        if ok and new_name:
            new_path = file_path.with_name(new_name + ".md")
            try:
                file_path.rename(new_path)
                self.model.refresh()
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Failed to rename note:\n{e}")

    def delete_note_dialog(self, file_path: Path):
        reply = QMessageBox.question(
            self,
            "Delete Note",
            f"Are you sure you want to delete '{file_path.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                file_path.unlink()
                self.model.refresh()
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to delete note:\n{e}")

    # ============================
    # --- Tabs & Notes
    # ============================
    def open_file_in_tab(self, index: QModelIndex):
        file_path = Path(self.model.filePath(index))
        if file_path.is_dir():
            return
        for i in range(self.tabs.count()):
            if self.tabs.widget(i).property("path") == str(file_path):
                self.tabs.setCurrentIndex(i)
                return
        editor = QTextEdit()
        editor.setPlainText(file_path.read_text(encoding="utf-8"))
        editor.textChanged.connect(lambda: self.save_file(editor))
        editor.setProperty("path", str(file_path))
        self.tabs.addTab(editor, file_path.stem)
        self.tabs.setCurrentWidget(editor)
        self.current_file = file_path
        self.build_tag_index()

    def save_file(self, editor):
        path = Path(editor.property("path"))
        path.write_text(editor.toPlainText(), encoding="utf-8")
        self.build_tag_index()

    def close_tab(self, index):
        self.tabs.removeTab(index)

    # ============================
    # --- Markdown Conversion
    # ============================
    def convert_md_to_html(self, md_text: str) -> str:
        """Convert markdown text to HTML with clickable wikilinks and tags."""
        # Convert [[wikilinks]] → HTML links
        md_text = re.sub(
            r"\[\[([^\]]+)\]\]",
            lambda m: f"[{m.group(1)}]({m.group(1).replace(' ', '%20')}.html)",
            md_text,
        )

        # Convert #tags → HTML links to tag pages
        md_text = re.sub(
            r"(?<!\w)#(\w+)",
            lambda m: f"[#{m.group(1)}](tag_{m.group(1)}.html)",
            md_text,
        )

        return markdown.markdown(md_text, extensions=["fenced_code", "tables"])


    def build_html_tree(self):
        """Convert all markdown files to HTML, with sidebar, search, and graph view."""
        html_dir = self.root_dir / "html_preview"
        html_dir.mkdir(exist_ok=True)

        # --- CSS
        css = """
        <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            display: flex;
            margin: 0;
            height: 100vh;
            color: #d4d4d4;
            background-color: #1e1e2f;
        }
        #sidebar {
            width: 250px;
            background-color: #2c2c3a;
            padding: 15px;
            overflow-y: auto;
            border-right: 1px solid #444;
        }
        #content {
            flex: 1;
            padding: 30px;
            overflow-y: auto;
        }
        input[type="search"] {
            width: 100%;
            padding: 6px;
            border-radius: 4px;
            border: none;
            margin-bottom: 12px;
            background-color: #3b3b4b;
            color: #fff;
        }
        a {
            color: #4fc3f7;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        h1, h2, h3, h4, h5, h6 {
            color: #a9b7c6;
        }
        pre, code {
            background-color: #2d2d3c;
            border-radius: 6px;
            padding: 6px;
            color: #dcdcdc;
        }
        ul { list-style: none; padding-left: 0; }
        li { margin-bottom: 0.4em; }
        #graph {
            width: 100%;
            height: 600px;
            margin-top: 20px;
            border: 1px solid #444;
        }
        </style>
        """

        # --- Build tag and link maps
        tag_map = {}
        link_map = {}
        md_files = list(self.root_dir.glob("**/*.md"))

        for md_file in md_files:
            text = md_file.read_text(encoding="utf-8")
            name = md_file.stem
            links = re.findall(r"\[\[([^\]]+)\]\]", text)
            link_map[name] = links
            for tag in re.findall(r"#(\w+)", text):
                tag_map.setdefault(tag, []).append(md_file)

        # --- Build graph JSON
        import json
        nodes = [{"id": f.stem} for f in md_files]
        edges = []
        for src, links in link_map.items():
            for dst in links:
                edges.append({"source": src, "target": dst})
        graph_json = json.dumps({"nodes": nodes, "links": edges})

        # --- Sidebar (all notes + tags)
        all_notes_links = "\n".join([
            f"<li><a href='{f.relative_to(self.root_dir).with_suffix('.html')}'>{f.stem}</a></li>"
            for f in sorted(md_files)
        ])
        all_tags_links = "\n".join([
            f"<li><a href='tag_{t}.html'>#{t}</a></li>" for t in sorted(tag_map)
        ])

        sidebar_html = f"""
        <div id='sidebar'>
            <input type='search' id='search' placeholder='Search notes...'>
            <h3>Notes</h3>
            <ul id='noteList'>{all_notes_links}</ul>
            <h3>Tags</h3>
            <ul>{all_tags_links}</ul>
            <h3>Graph View</h3>
            <a href='graph.html'>📊 Open Graph</a>
        </div>
        """

        # --- JavaScript for filtering notes
        search_js = """
        <script>
        document.getElementById('search').addEventListener('input', function() {
            let query = this.value.toLowerCase();
            document.querySelectorAll('#noteList li').forEach(li => {
                li.style.display = li.textContent.toLowerCase().includes(query) ? '' : 'none';
            });
        });
        </script>
        """

        # --- Convert notes
        for md_file in md_files:
            html_path = html_dir / md_file.relative_to(self.root_dir).with_suffix(".html")
            html_path.parent.mkdir(parents=True, exist_ok=True)
            text = md_file.read_text(encoding="utf-8")
            html = self.convert_md_to_html(text)
            html_path.write_text(
                f"<html><head>{css}</head><body>{sidebar_html}<div id='content'>{html}</div>{search_js}</body></html>",
                encoding="utf-8"
            )

        # --- Tag pages
        for tag, files in tag_map.items():
            tag_html = [f"<h1>#{tag}</h1>", "<ul>"]
            for f in files:
                rel_html = f.relative_to(self.root_dir).with_suffix(".html")
                tag_html.append(f"<li><a href='{rel_html.as_posix()}'>{f.stem}</a></li>")
            tag_html.append("</ul>")
            (html_dir / f"tag_{tag}.html").write_text(
                f"<html><head>{css}</head><body>{sidebar_html}<div id='content'>" +
                "\n".join(tag_html) + f"</div>{search_js}</body></html>", encoding="utf-8"
            )

        # --- Graph page (D3.js)
        graph_html = f"""
        <html><head>{css}
        <script src="https://d3js.org/d3.v7.min.js"></script>
        </head>
        <body>{sidebar_html}
        <div id='content'>
            <h1>Note Graph</h1>
            <div id='graph'></div>
        </div>
        <script>
        const graphData = {graph_json};
        const width = document.getElementById('graph').clientWidth;
        const height = 600;
        const svg = d3.select("#graph").append("svg")
            .attr("width", width)
            .attr("height", height);
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2));
        const link = svg.append("g")
            .attr("stroke", "#aaa")
            .selectAll("line")
            .data(graphData.links)
            .enter().append("line");
        const node = svg.append("g")
            .selectAll("circle")
            .data(graphData.nodes)
            .enter().append("circle")
            .attr("r", 8)
            .attr("fill", "#4fc3f7")
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("click", (event, d) => {{
                window.location.href = d.id + ".html";
            }});
        const label = svg.append("g")
            .selectAll("text")
            .data(graphData.nodes)
            .enter().append("text")
            .text(d => d.id)
            .attr("fill", "#fff")
            .attr("font-size", 12);
        simulation.on("tick", () => {{
            link.attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            node.attr("cx", d => d.x)
                .attr("cy", d => d.y);
            label.attr("x", d => d.x + 10)
                .attr("y", d => d.y + 4);
        }});
        function dragstarted(event, d) {{
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x; d.fy = d.y;
        }}
        function dragged(event, d) {{
            d.fx = event.x; d.fy = event.y;
        }}
        function dragended(event, d) {{
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null; d.fy = null;
        }}
        </script>{search_js}</body></html>
        """
        (html_dir / "graph.html").write_text(graph_html, encoding="utf-8")

        return html_dir




    def open_preview_in_browser(self):
        if self.tabs.currentWidget() is None:
            return
        current_editor = self.tabs.currentWidget()
        md_file = Path(current_editor.property("path"))
        html_dir = self.build_html_tree()
        html_path = html_dir / md_file.relative_to(self.root_dir).with_suffix(".html")
        webbrowser.open_new_tab(f"file://{html_path.resolve()}")

    # ============================
    # --- Graph, Tags, Search
    # ============================
    def show_graph_view(self):
        G = nx.Graph()
        for md_file in self.root_dir.glob("**/*.md"):
            text = md_file.read_text(encoding="utf-8")
            name = md_file.stem
            G.add_node(name)
            for match in re.findall(r"\[\[([^\]]+)\]\]", text):
                G.add_edge(name, match)
        plt.figure(figsize=(8, 6))
        nx.draw(G, with_labels=True, node_color='lightblue', edge_color='gray')
        plt.title("Note Graph View")
        plt.show()

    def build_tag_index(self):
        self.tags = {}
        for md_file in self.root_dir.glob("**/*.md"):
            text = md_file.read_text(encoding="utf-8")
            for tag in re.findall(r"#(\w+)", text):
                self.tags.setdefault(tag, []).append(md_file)
        self.tag_pane.clear()
        for tag, files in sorted(self.tags.items()):
            self.tag_pane.addItem(f"#{tag} ({len(files)})")

    def filter_by_tag(self, item: QListWidgetItem):
        tag = item.text().split()[0][1:]
        notes = self.tags.get(tag, [])
        msg = "Notes with #" + tag + ":\n" + "\n".join([n.name for n in notes])
        QMessageBox.information(self, f"#{tag}", msg)

    def search_notes(self):
        query = self.search_bar.text().strip()
        if not query:
            return
        all_notes = list(self.root_dir.glob("**/*.md"))
        texts = {n: n.read_text(encoding="utf-8") for n in all_notes}
        results = process.extract(query, texts.keys(), scorer=fuzz.partial_ratio, limit=10)
        msg = ""
        for match, score, path in results:
            msg += f"{path.name} ({score}%)\n"
        QMessageBox.information(self, "Search Results", msg or "No matches found.")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    vault = Path.cwd() / "vault"
    vault.mkdir(exist_ok=True)
    window = MarkdownEditor(vault)
    window.show()
    sys.exit(app.exec())
