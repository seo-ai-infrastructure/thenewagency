#!/usr/bin/env python3
import json
import argparse
from pathlib import Path
from datetime import datetime

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Agent Trace Report - {trace_id}</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; margin: 2rem; background: #0b0f14; color: #e6edf3; }}
        .container {{ max-width: 1400px; margin: auto; background: #11171f; padding: 1.5rem; border-radius: 8px; border: 1px solid #222c39; }}
        h1, h2, h3 {{ color: #cfe1ff; font-family: monospace; }}
        .filter-bar {{ margin: 1.5rem 0; display: flex; gap: 1rem; flex-wrap: wrap; }}
        .filter-bar input, .filter-bar select {{ padding: 0.5rem; background: #161d27; color: #e6edf3; border: 1px solid #222c39; border-radius: 4px; }}
        .step {{ border-left: 4px solid #7d8a9a; margin: 1rem 0; padding: 1rem; background: #161d27; border-radius: 4px; border: 1px solid #222c39; border-left-width: 4px; }}
        .step-llm-input {{ border-left-color: #3498db; }}
        .step-llm-output {{ border-left-color: #2ecc71; }}
        .step-browser-action {{ border-left-color: #e67e22; }}
        .step-observation {{ border-left-color: #9b59b6; }}
        .step-extraction {{ border-left-color: #1abc9c; }}
        .step-skip-reason {{ border-left-color: #e74c3c; }}
        .step-network {{ border-left-color: #95a5a6; }}
        .step pre {{ background: #0b0f14; padding: 0.5rem; border-radius: 4px; border: 1px solid #222c39; overflow-x: auto; max-height: 300px; color: #86efac; }}
        .screenshot {{ max-width: 300px; cursor: pointer; border: 1px solid #222c39; margin-top: 0.5rem; border-radius: 4px; transition: opacity 0.2s; }}
        .screenshot:hover {{ opacity: 0.8; }}
        .modal {{ display: none; position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.9); justify-content: center; align-items: center; z-index:1000; }}
        .modal img {{ max-width: 90%; max-height: 90%; border: 3px solid #cfe1ff; border-radius: 8px; }}
        .badge {{ display: inline-block; background: #1f6feb; color: white; padding: 0.2rem 0.5rem; border-radius: 12px; font-size: 0.8rem; margin-right: 0.5rem; font-family: monospace; }}
        .network-summary {{ background: #161d27; padding: 0.8rem; border-radius: 6px; border: 1px solid #222c39; margin-bottom: 1.5rem; font-family: monospace; color: #fbbf24; }}
    </style>
</head>
<body>
<div class="container">
    <h1>🤖 Agent Trace Report</h1>
    <p><strong>Trace ID:</strong> {trace_id}</p>
    <p><strong>Goal:</strong> {goal}</p>
    <p><strong>Started:</strong> {started_at} &nbsp;|&nbsp; <strong>Finished:</strong> {finished_at}</p>
    <p><strong>Total steps:</strong> {total_steps}</p>

    <div class="filter-bar">
        <input type="text" id="search" placeholder="Search (URL, text, skip reason)" style="width: 300px;">
        <select id="typeFilter">
            <option value="all">All step types</option>
            <option value="llm_input">LLM Input</option>
            <option value="llm_output">LLM Output</option>
            <option value="browser_action">Browser Action</option>
            <option value="observation">Observation</option>
            <option value="extraction">Extraction</option>
            <option value="skip_reason">Skip Reason</option>
            <option value="network">Network</option>
        </select>
        <button id="resetFilters" style="padding: 0.5rem 1rem; background: #21262d; border: 1px solid #30363d; color: #e6edf3; border-radius: 6px; cursor: pointer;">Reset</button>
    </div>

    <div class="network-summary" id="networkSummary"></div>

    <div id="stepsContainer"></div>
</div>

<div id="modal" class="modal" onclick="this.style.display='none'">
    <img id="modalImg" src="">
</div>

<script>
const steps = {steps_json};
const traceId = "{trace_id}";
const screenshots = {screenshots_map};

function renderSteps(filterType, searchTerm) {{
    const container = document.getElementById('stepsContainer');
    container.innerHTML = '';
    let totalReqs = 0;
    let failed = 0;
    
    steps.forEach(step => {{
        if (step.step_type === 'network') {{
            if (step.data.type === 'request') totalReqs++;
            if (step.data.type === 'response' && step.data.status >= 400) failed++;
        }}
        
        if (filterType !== 'all' && step.step_type !== filterType) return;
        if (searchTerm && !JSON.stringify(step).toLowerCase().includes(searchTerm.toLowerCase())) return;
        
        const stepDiv = document.createElement('div');
        stepDiv.className = `step step-${{step.step_type.replace('_', '-')}}`;
        let content = `<div><span class="badge">${{step.step_type}}</span> <strong>${{step.timestamp}}</strong></div>`;
        
        if (step.step_type === 'llm_input') {{
            content += `<pre>${{JSON.stringify(step.data, null, 2)}}</pre>`;
        }} else if (step.step_type === 'llm_output') {{
            content += `<div style="margin-top:8px;"><strong>Output:</strong> ${{step.data.output}}</div>`;
            if (step.data.intermediate_steps && step.data.intermediate_steps.length) {{
                content += `<pre>${{JSON.stringify(step.data.intermediate_steps, null, 2)}}</pre>`;
            }}
        }} else if (step.step_type === 'browser_action') {{
            content += `<div style="margin-top:8px;">Action: ${{step.data.action}} on ${{step.data.selector || step.data.url}}</div>`;
        }} else if (step.step_type === 'observation') {{
            if (step.data.type.startsWith('dom_snapshot')) {{
                content += `<div style="margin-top:8px;"><strong>DOM snapshot</strong> (truncated):</div><pre>${{step.data.dom_truncated}}</pre>`;
                content += `<div><em>Full DOM length: ${{step.data.dom_full_length}} chars</em></div>`;
            }} else if (step.data.type.startsWith('screenshot')) {{
                const imgPath = step.data.path;
                const fileName = imgPath.split('/').pop().split('\\\\').pop();
                content += `<div style="margin-top:8px;"><strong>Screenshot:</strong></div><img class="screenshot" src="${{fileName}}" onclick="showModal('${{fileName}}')">`;
            }} else {{
                content += `<pre>${{JSON.stringify(step.data, null, 2)}}</pre>`;
            }}
        }} else if (step.step_type === 'extraction') {{
            content += `<div style="margin-top:8px;"><strong>Selector:</strong> ${{step.data.selector}}</div>`;
            content += `<div style="margin-top:4px;"><strong>Preview:</strong> ${{step.data.text_preview}}</div>`;
        }} else if (step.step_type === 'skip_reason') {{
            content += `<div style="color:#f85149; margin-top:8px;"><strong>⚠️ Skip reason:</strong> ${{step.data.reason}}</div>`;
        }} else if (step.step_type === 'network') {{
            content += `<div style="margin-top:8px;">${{step.data.method || 'GET'}} ${{step.data.url}} → ${{step.data.status || 'request'}}</div>`;
        }}
        
        stepDiv.innerHTML = content;
        container.appendChild(stepDiv);
    }});
    
    document.getElementById('networkSummary').innerHTML = `🌐 Network Summary: ${{totalReqs}} requests, ${{failed}} failed (4xx/5xx)`;
}}

function showModal(src) {{
    const modal = document.getElementById('modal');
    const modalImg = document.getElementById('modalImg');
    modal.style.display = 'flex';
    modalImg.src = src;
}}

document.getElementById('typeFilter').addEventListener('change', (e) => {{
    renderSteps(e.target.value, document.getElementById('search').value);
}});
document.getElementById('search').addEventListener('input', (e) => {{
    renderSteps(document.getElementById('typeFilter').value, e.target.value);
}});
document.getElementById('resetFilters').addEventListener('click', () => {{
    document.getElementById('typeFilter').value = 'all';
    document.getElementById('search').value = '';
    renderSteps('all', '');
}});

renderSteps('all', '');
</script>
</body>
</html>
"""

def generate_report(trace_dir: Path):
    metadata_files = list(trace_dir.glob("metadata_*.json"))
    if not metadata_files:
        raise FileNotFoundError(f"No metadata file found in {trace_dir}")
    metadata = json.loads(metadata_files[0].read_text(encoding="utf-8"))
    trace_id = metadata["trace_id"]
    goal = metadata["goal"]
    started_at = metadata["started_at"]
    finished_at = metadata.get("finished_at", "unknown")
    total_steps = metadata.get("total_steps", 0)

    trace_file = trace_dir / f"trace_{trace_id}.jsonl"
    steps = []
    screenshots = {}
    if trace_file.exists():
        with open(trace_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    step = json.loads(line)
                    steps.append(step)
                    if step.get("step_type") == "observation" and step["data"].get("type", "").startswith("screenshot"):
                        path = step["data"]["path"]
                        screenshots[path] = Path(path).name

    steps_json = json.dumps(steps, default=str)
    screenshots_map = json.dumps(screenshots)

    html = HTML_TEMPLATE.format(
        trace_id=trace_id,
        goal=goal,
        started_at=started_at,
        finished_at=finished_at,
        total_steps=total_steps,
        steps_json=steps_json,
        screenshots_map=screenshots_map
    )
    output_html = trace_dir / "report.html"
    output_html.write_text(html, encoding="utf-8")
    print(f"Report generated successfully: {output_html}")
    return output_html

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--trace-dir", required=True, type=Path, help="Directory containing trace_*.jsonl and metadata_*.json")
    args = parser.parse_args()
    generate_report(args.trace_dir)
