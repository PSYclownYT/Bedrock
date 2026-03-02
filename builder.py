import re
import json
import random
from pathlib import Path
import markdown
import re

def extract_note_color(text):
    match = re.search(r"@color:\s*(#[0-9a-fA-F]{6})", text)
    if match:
        return match.group(1)
    return "#4fc3f7"  # default color

def build_vault(root_dir: Path):
    """Build static HTML preview of all markdown notes with tags, links, and D3 force-directed graph."""
    html_dir = root_dir / "html_preview"
    html_dir.mkdir(exist_ok=True)

    TAG_REGEX = re.compile(r"\{\{(.*?)\}\}")
    LINK_REGEX = re.compile(r"\[\[([^\]]+)\]\]")

    DEFAULT_CSS = """
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
        width: 260px;
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
    a:hover { text-decoration: underline; }
    h1, h2, h3, h4, h5, h6 { color: #a9b7c6; }
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
        height: 700px;
        margin-top: 20px;
        border: 1px solid #444;
        border-radius: 12px;
        background: #252539;
    }
    .node {
        cursor: pointer;
    }
    .node:hover {
        stroke: #fff;
        stroke-width: 2px;
    }
    </style>
    """

    md_files = list(root_dir.glob("**/*.md"))
    tag_map = {}
    link_map = {}

    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        color = extract_note_color(text)
        name = md_file.stem
        tags = TAG_REGEX.findall(text)
        links = LINK_REGEX.findall(text)
        link_map[name] = links
        for tag in tags:
            tag_map.setdefault(tag, []).append(md_file)

    all_notes_links = "\n".join(
        f"<li><a href='{f.relative_to(root_dir).with_suffix('.html')}'>{f.stem}</a></li>"
        for f in sorted(md_files)
    )
    all_tags_links = "\n".join(
        f"<li><a href='tag_{t}.html'># {t}</a></li>" for t in sorted(tag_map)
    )

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

    search_js = """
    <script>
    document.getElementById('search').addEventListener('input', function() {
        let q = this.value.toLowerCase();
        document.querySelectorAll('#noteList li').forEach(li => {
            li.style.display = li.textContent.toLowerCase().includes(q) ? '' : 'none';
        });
    });
    </script>
    """

    def convert_md_to_html(text):
        text = re.sub(LINK_REGEX, lambda m: f"<a href='{m.group(1)}.html'>{m.group(1)}</a>", text)
        text = re.sub(TAG_REGEX, lambda m: f"<a href='tag_{m.group(1)}.html'>@{m.group(1)}</a>", text)
        return markdown.markdown(text, extensions=["fenced_code", "tables"])

    for md_file in md_files:
        html_path = html_dir / md_file.relative_to(root_dir).with_suffix(".html")
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html = convert_md_to_html(md_file.read_text(encoding="utf-8"))
        html_path.write_text(
            f"<html><head>{DEFAULT_CSS}</head><body>{sidebar_html}<div id='content'>{html}</div>{search_js}</body></html>",
            encoding="utf-8"
        )

    for tag, files in tag_map.items():
        seen = set()
        tag_html = [f"<h1>#{tag}</h1>", "<ul>"]
        for f in files:
            if f.stem not in seen:
                rel_html = f.relative_to(root_dir).with_suffix(".html")
                tag_html.append(f"<li><a href='{rel_html.as_posix()}'>{f.stem}</a></li>")
                seen.add(f.stem)
        tag_html.append("</ul>")
        (html_dir / f"tag_{tag}.html").write_text(
            f"<html><head>{DEFAULT_CSS}</head><body>{sidebar_html}<div id='content'>" +
            "\n".join(tag_html) + f"</div>{search_js}</body></html>", encoding="utf-8"
        )

    # Create nodes with random initial positions spread throughout the canvas
    nodes = []
    for f in md_files:
        nodes.append({
            "id": f.stem,
            "color": color
        })
    
    # Filter edges to only include targets that exist in our nodes
    valid_nodes = {f.stem for f in md_files}
    edges = []
    for src, links in link_map.items():
        for dst in links:
            if dst in valid_nodes:
                edges.append({"source": src, "target": dst})

    graph_html = f"""
    <html><head>{DEFAULT_CSS}
    <script src="https://d3js.org/d3.v7.min.js"></script>
    </head>
    <body>{sidebar_html}
    <div id='content'>
        <h1>Note Graph</h1>
        <div id='graph'></div>
    </div>

    <script>
    const graphData = {{
        nodes: {json.dumps(nodes)},
        links: {json.dumps(edges)}
    }};

    const width = document.getElementById('graph').clientWidth;
    const height = 700;

    const svg = d3.select("#graph").append("svg")
        .attr("width", width)
        .attr("height", height)
        .style("background", "#252539");

    const container = svg.append("g");

    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on("zoom", (event) => container.attr("transform", event.transform));
    svg.call(zoom);

    // Initialize simulation
    const simulation = d3.forceSimulation()
        .force("link", d3.forceLink().id(d => d.id).distance(120))
        .force("charge", d3.forceManyBody().strength(-250))
        .force("center", d3.forceCenter(width / 2, height / 2))
        .force("collision", d3.forceCollide().radius(35));

    // Create links
    const link = container.append("g")
        .selectAll("line")
        .data(graphData.links)
        .join("line")
        .attr("stroke", "#666")
        .attr("stroke-width", 1.5)
        .attr("stroke-opacity", 0.6);

    // Create nodes
    const node = container.append("g")
        .selectAll("circle")
        .data(graphData.nodes)
        .join("circle")
        .attr("r", 12)
        .attr("fill", d => d.color || "#4fc3f7")
        .attr("class", "node")
        .call(d3.drag()
            .on("start", dragstarted)
            .on("drag", dragged)
            .on("end", dragended))
        .on("click", (event, d) => {{
            window.location.href = d.id + ".html";
        }});

    // Create labels
    const label = container.append("g")
        .selectAll("text")
        .data(graphData.nodes)
        .join("text")
        .text(d => d.id)
        .attr("font-size", 10)
        .attr("fill", "#fff")
        .attr("dx", 15)
        .attr("dy", 4)
        .style("pointer-events", "none");

    // Set up simulation with data
    simulation.nodes(graphData.nodes);
    simulation.force("link").links(graphData.links);

    // Update positions on tick
    simulation.on("tick", () => {{
        link
            .attr("x1", d => d.source.x)
            .attr("y1", d => d.source.y)
            .attr("x2", d => d.target.x)
            .attr("y2", d => d.target.y);

        node
            .attr("cx", d => d.x)
            .attr("cy", d => d.y);

        label
            .attr("x", d => d.x)
            .attr("y", d => d.y);
    }});

    // Add a slight initial force to spread nodes
    simulation.alpha(1).restart();

    function dragstarted(event, d) {{
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }}

    function dragged(event, d) {{
        d.fx = event.x;
        d.fy = event.y;
    }}

    function dragended(event, d) {{
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }}

    // Add double-click to reset node position
    node.on("dblclick", (event, d) => {{
        d.fx = null;
        d.fy = null;
        simulation.alpha(0.3).restart();
    }});
    </script>

    {search_js}
    </body></html>
    """

    (html_dir / "graph.html").write_text(graph_html, encoding="utf-8")
    print(f"✅ Build complete: {html_dir}")

# Example usage:
# build_vault(Path("/path/to/your/vault"))