#!/usr/bin/env python3
"""
Agent Recorder Demo – Full observability for LLM web agents.
Run: python agent_recorder_demo.py --url https://example.com --output ./demo_run
"""

import asyncio
import json
import argparse
import uuid
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional

# Try importing Playwright – user must install: playwright install
try:
    from playwright.async_api import async_playwright
except ImportError:
    raise ImportError("Install playwright: pip install playwright && playwright install")

# Optional: for real LLM, set OPENAI_API_KEY env var
try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None

# -------------------------------
# 1. Trace Writer (JSONL + metadata)
# -------------------------------
class TraceWriter:
    def __init__(self, output_dir: Path, goal: str):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trace_id = uuid.uuid4().hex[:8]
        self.goal = goal
        self.step_counter = 0
        self.log_file = output_dir / f"trace_{self.trace_id}.jsonl"
        self.metadata = {
            "trace_id": self.trace_id,
            "goal": goal,
            "started_at": datetime.utcnow().isoformat(),
            "steps": []
        }

    def log_step(self, step_type: str, data: Dict[str, Any]) -> Dict:
        record = {
            "step_id": self.step_counter,
            "trace_id": self.trace_id,
            "timestamp": datetime.utcnow().isoformat(),
            "step_type": step_type,
            "data": data
        }
        self.step_counter += 1
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return record

    def close(self):
        self.metadata["finished_at"] = datetime.utcnow().isoformat()
        self.metadata["total_steps"] = self.step_counter
        with open(self.output_dir / f"metadata_{self.trace_id}.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, indent=2)

# -------------------------------
# 2. Stealth Browser with HAR + Network Logging
# -------------------------------
class StealthBrowser:
    def __init__(self, trace_writer: TraceWriter, output_dir: Path, headless: bool = True):
        self.trace = trace_writer
        self.output_dir = output_dir
        self.headless = headless
        self.context = None
        self.page = None
        self.playwright = None

    async def start(self):
        self.playwright = await async_playwright().start()
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        # Temp profile stored inside the workspace output directory
        user_data_dir = self.output_dir / "playwright_demo_profile"
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        # Launch persistent context with HAR recording (Playwright built‑in)
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=self.headless,
            user_agent=user_agent,
            viewport={"width": 1280, "height": 720},
            record_har_path=str(self.output_dir / "trace.har"),
            record_har_content="embed"
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        # Inject stealth script
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        # Manual network logging (optional, but adds detail)
        self.page.on("request", self._log_request)
        self.page.on("response", self._log_response)
        return self.page

    def _log_request(self, request):
        self.trace.log_step("network", {
            "type": "request",
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": request.post_data[:200] if request.post_data else None
        })

    def _log_response(self, response):
        self.trace.log_step("network", {
            "type": "response",
            "url": response.url,
            "status": response.status,
            "headers": dict(response.headers)
        })

    async def goto(self, url: str):
        self.trace.log_step("browser_action", {"action": "goto", "url": url})
        response = await self.page.goto(url, wait_until="networkidle")
        # Capture DOM snapshot (truncated)
        dom = await self.page.content()
        truncated = dom[:3000] + "…" if len(dom) > 3000 else dom
        self.trace.log_step("observation", {
            "type": "dom_snapshot",
            "url": self.page.url,
            "dom_truncated": truncated,
            "dom_full_length": len(dom)
        })
        # Screenshot
        screenshot_path = self.output_dir / f"screenshot_{self.trace.step_counter}.png"
        await self.page.screenshot(path=str(screenshot_path))
        self.trace.log_step("observation", {
            "type": "screenshot",
            "path": str(screenshot_path)
        })
        return response

    async def click(self, selector: str):
        self.trace.log_step("browser_action", {"action": "click", "selector": selector})
        await self.page.click(selector)

    async def extract_text(self, selector: str = "body"):
        self.trace.log_step("browser_action", {"action": "extract", "selector": selector})
        element = await self.page.query_selector(selector)
        text = await element.inner_text() if element else ""
        preview = text[:500] + "…" if len(text) > 500 else text
        self.trace.log_step("extraction", {"selector": selector, "text_preview": preview})
        return text

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        self.trace.log_step("metadata", {"har_file": str(self.output_dir / "trace.har")})

# -------------------------------
# 3. Mock LLM Agent (or real OpenAI)
# -------------------------------
class MockLLMAgent:
    """Simplistic mock agent that looks for emails and phone numbers."""
    def __init__(self, browser: StealthBrowser, trace: TraceWriter, goal: str):
        self.browser = browser
        self.trace = trace
        self.goal = goal

    async def run(self, max_steps: int = 5):
        await self.browser.start()
        conversation = []
        for step in range(max_steps):
            # Log LLM input (mock)
            self.trace.log_step("llm_input", {
                "step": step,
                "goal": self.goal,
                "chat_history": conversation
            })
            # Simple state machine: first navigate, then extract
            if step == 0:
                # Extract URL from goal (crude)
                url_match = re.search(r'https?://[^\s]+', self.goal)
                url = url_match.group(0) if url_match else "https://example.com"
                await self.browser.goto(url)
                output = f"Navigated to {url}. Now extracting page text."
            else:
                page_text = await self.browser.extract_text()
                # Mock "thinking" – look for emails and phone numbers
                emails = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', page_text)
                phones = re.findall(r'(\+\d{1,2}\s?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', page_text)
                output = f"Found emails: {emails[:3]}, phones: {phones[:3]}. "
                if not emails and not phones:
                    output += "No contact info found. Skipping rest of page (irrelevant ads, navigation menus)."
                    self.trace.log_step("skip_reason", {"reason": "No contact info, skipping remaining content"})
                else:
                    output += "Goal achieved (extracted contact info)."
                    self.trace.log_step("skip_reason", {"reason": "Goal achieved, stopping"})
                    break
            # Log LLM output
            self.trace.log_step("llm_output", {"output": output})
            conversation.append(("assistant", output))
            await asyncio.sleep(0.5)  # simulate thinking
        await self.browser.close()
        return conversation

# -------------------------------
# 4. HTML Report Generator (embedded)
# -------------------------------
REPORT_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>Agent Trace Report - {trace_id}</title>
<style>
body {{ font-family: system-ui, -apple-system, sans-serif; margin: 20px; background: #0b0f14; color: #e6edf3; }}
.container {{ max-width: 1200px; margin: auto; background: #11171f; padding: 20px; border-radius: 8px; border: 1px solid #222c39; }}
.step {{ border-left: 4px solid #7d8a9a; margin: 15px 0; padding: 10px; background: #161d27; border: 1px solid #222c39; border-radius: 4px; }}
.step-llm_input {{ border-left-color: #3498db; }}
.step-llm_output {{ border-left-color: #2ecc71; }}
.step-browser_action {{ border-left-color: #e67e22; }}
.step-observation {{ border-left-color: #9b59b6; }}
.step-extraction {{ border-left-color: #1abc9c; }}
.step-skip_reason {{ border-left-color: #e74c3c; }}
.step-network {{ border-left-color: #95a5a6; }}
pre {{ background: #0b0f14; padding: 8px; overflow-x: auto; max-height: 200px; color: #86efac; border: 1px solid #222c39; }}
.screenshot {{ max-width: 200px; cursor: pointer; border: 1px solid #222c39; border-radius: 4px; }}
.modal {{ display: none; position: fixed; top:0; left:0; width:100%; height:100%; background: rgba(0,0,0,0.8); justify-content: center; align-items: center; }}
.modal img {{ max-width: 90%; max-height: 90%; border: 2px solid #cfe1ff; border-radius: 8px; }}
.filter-bar {{ margin: 15px 0; }}
.filter-bar input, .filter-bar select {{ padding: 0.5rem; background: #161d27; color: #e6edf3; border: 1px solid #222c39; border-radius: 4px; }}
</style>
</head>
<body>
<div class="container">
<h1>🤖 Agent Trace: {trace_id}</h1>
<p><strong>Goal:</strong> {goal}</p>
<p><strong>Started:</strong> {started_at} &nbsp;|&nbsp; <strong>Finished:</strong> {finished_at}</p>
<p><strong>Total steps:</strong> {total_steps}</p>
<div class="filter-bar">
    <input type="text" id="search" placeholder="Search...">
    <select id="typeFilter">
        <option value="all">All types</option>
        <option value="llm_input">LLM Input</option>
        <option value="llm_output">LLM Output</option>
        <option value="browser_action">Browser Action</option>
        <option value="observation">Observation</option>
        <option value="extraction">Extraction</option>
        <option value="skip_reason">Skip Reason</option>
        <option value="network">Network</option>
    </select>
    <button id="reset" style="padding: 0.5rem 1rem; background: #21262d; border: 1px solid #30363d; color: #e6edf3; border-radius: 6px; cursor: pointer;">Reset</button>
</div>
<div id="stepsContainer"></div>
</div>
<div id="modal" class="modal" onclick="this.style.display='none'"><img id="modalImg"></div>
<script>
const steps = {steps_json};
function renderSteps(typeFilter, searchTerm) {{
    const container = document.getElementById('stepsContainer');
    container.innerHTML = '';
    steps.forEach(step => {{
        if (typeFilter !== 'all' && step.step_type !== typeFilter) return;
        if (searchTerm && !JSON.stringify(step).toLowerCase().includes(searchTerm.toLowerCase())) return;
        const div = document.createElement('div');
        div.className = `step step-${{step.step_type.replace('_', '-')}}`;
        let content = `<strong>${{step.timestamp}}</strong> &nbsp; <span style="background:#222c39; color:#e6edf3; padding:2px 6px; border-radius:4px; border:1px solid #30363d;">${{step.step_type}}</span><br>`;
        if (step.step_type === 'llm_input') {{
            content += `<pre>${{JSON.stringify(step.data, null, 2)}}</pre>`;
        }} else if (step.step_type === 'llm_output') {{
            content += `<div style="margin-top:8px;">${{step.data.output}}</div>`;
        }} else if (step.step_type === 'browser_action') {{
            content += `<div style="margin-top:8px;">Action: ${{step.data.action}} on ${{step.data.selector || step.data.url}}</div>`;
        }} else if (step.step_type === 'observation') {{
            if (step.data.type === 'dom_snapshot') {{
                content += `<div style="margin-top:8px;"><strong>DOM snapshot</strong> (truncated):</div><pre>${{step.data.dom_truncated}}</pre>`;
                content += `<div><em>Full DOM length: ${{step.data.dom_full_length}} chars</em></div>`;
            }} else if (step.data.type === 'screenshot') {{
                const imgPath = step.data.path.split('/').pop().split('\\\\').pop();
                content += `<div style="margin-top:8px;"><strong>Screenshot:</strong><br><img class="screenshot" src="${{imgPath}}" onclick="showModal('${{imgPath}}')"></div>`;
            }}
        }} else if (step.step_type === 'extraction') {{
            content += `<div style="margin-top:8px;"><strong>Selector:</strong> ${{step.data.selector}}</div><pre>${{step.data.text_preview}}</pre>`;
        }} else if (step.step_type === 'skip_reason') {{
            content += `<div style="color:#f85149; margin-top:8px;">⚠️ Skip: ${{step.data.reason}}</div>`;
        }} else if (step.step_type === 'network') {{
            content += `<div style="margin-top:8px;">${{step.data.method || ''}} ${{step.data.url}} → ${{step.data.status || ''}}</div>`;
        }}
        div.innerHTML = content;
        container.appendChild(div);
    }});
}}
function showModal(src) {{
    document.getElementById('modal').style.display = 'flex';
    document.getElementById('modalImg').src = src;
}}
document.getElementById('typeFilter').addEventListener('change', (e) => renderSteps(e.target.value, document.getElementById('search').value));
document.getElementById('search').addEventListener('input', (e) => renderSteps(document.getElementById('typeFilter').value, e.target.value));
document.getElementById('reset').addEventListener('click', () => {{
    document.getElementById('typeFilter').value = 'all';
    document.getElementById('search').value = '';
    renderSteps('all', '');
}});
renderSteps('all', '');
</script>
</body>
</html>"""

def generate_html_report(trace_dir: Path):
    meta_file = list(trace_dir.glob("metadata_*.json"))[0]
    meta = json.loads(meta_file.read_text(encoding="utf-8"))
    trace_id = meta["trace_id"]
    trace_file = trace_dir / f"trace_{trace_id}.jsonl"
    steps = []
    with open(trace_file, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                steps.append(json.loads(line))
    steps_json = json.dumps(steps, default=str)
    html = REPORT_TEMPLATE.format(
        trace_id=trace_id,
        goal=meta["goal"],
        started_at=meta["started_at"],
        finished_at=meta["finished_at"],
        total_steps=meta["total_steps"],
        steps_json=steps_json
    )
    report_path = trace_dir / "report.html"
    report_path.write_text(html, encoding="utf-8")
    return report_path

# -------------------------------
# 5. Main CLI
# -------------------------------
async def main():
    parser = argparse.ArgumentParser(description="Agent Recorder Demo")
    parser.add_argument("--url", default="https://example.com", help="Target URL (or embed in goal)")
    parser.add_argument("--output", required=True, type=Path, help="Output directory")
    parser.add_argument("--max-steps", type=int, default=4, help="Max agent steps")
    parser.add_argument("--headless", action="store_true", default=True, help="Run browser headless")
    args = parser.parse_args()

    goal = f"Extract contact information from {args.url}"
    output_dir = args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    trace = TraceWriter(output_dir, goal)
    browser = StealthBrowser(trace, output_dir, headless=args.headless)
    agent = MockLLMAgent(browser, trace, goal)
    await agent.run(max_steps=args.max_steps)
    trace.close()

    report_path = generate_html_report(output_dir)
    print(f"\n✅ Trace saved to {output_dir}")
    print(f"📄 Open the report: {report_path}")
    print(f"📡 HAR file: {output_dir / 'trace.har'}")
    print("\nTo view the report with screenshots, run a webserver in the output directory:")
    print(f"    cd {output_dir} && python -m http.server 8789")
    print("    Then open http://localhost:8789/report.html")

if __name__ == "__main__":
    asyncio.run(main())
