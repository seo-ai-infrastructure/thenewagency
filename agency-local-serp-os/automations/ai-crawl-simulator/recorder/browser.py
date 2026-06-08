from playwright.async_api import async_playwright
import asyncio
from pathlib import Path

class StealthBrowser:
    def __init__(self, trace_writer, output_dir: Path, headless=True):
        self.trace_writer = trace_writer
        self.output_dir = output_dir
        self.headless = headless
        self.context = None
        self.page = None
        self.playwright = None

    async def start(self):
        self.playwright = await async_playwright().start()
        user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        # Temp dir inside output directory to keep user data clean and portable
        user_data_dir = self.output_dir / "playwright_profile"
        user_data_dir.mkdir(parents=True, exist_ok=True)
        
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=self.headless,
            user_agent=user_agent,
            viewport={"width": 1280, "height": 720},
            record_har_path=str(self.output_dir / "trace.har"),
            record_har_content="embed"
        )
        self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
        
        # Inject custom simple stealth definitions
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)
        
        # Bind network listeners
        self.page.on("request", self._log_request)
        self.page.on("response", self._log_response)
        return self.page

    def _log_request(self, request):
        post_data = request.post_data
        self.trace_writer.log_step("network", {
            "type": "request",
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": post_data[:500] if post_data else None
        })

    def _log_response(self, response):
        try:
            body_len = len(response.body()) if response.ok else 0
        except Exception:
            body_len = 0
        self.trace_writer.log_step("network", {
            "type": "response",
            "url": response.url,
            "status": response.status,
            "headers": dict(response.headers),
            "body_size": body_len
        })

    async def goto(self, url: str):
        self.trace_writer.log_step("browser_action", {"action": "goto", "url": url})
        response = await self.page.goto(url, wait_until="networkidle")
        
        # Capture full DOM
        dom = await self.page.content()
        truncated_dom = dom[:5000] + "…" if len(dom) > 5000 else dom
        self.trace_writer.log_step("observation", {
            "type": "dom_snapshot",
            "url": self.page.url,
            "dom_truncated": truncated_dom,
            "dom_full_length": len(dom)
        })
        
        # Capture screenshot
        screenshot_path = self.output_dir / f"screenshot_{self.trace_writer.step_counter}.png"
        await self.page.screenshot(path=str(screenshot_path))
        self.trace_writer.log_step("observation", {
            "type": "screenshot",
            "path": str(screenshot_path)
        })
        return response

    async def click(self, selector: str):
        self.trace_writer.log_step("browser_action", {"action": "click", "selector": selector})
        await self.page.click(selector)
        
        # Capture DOM & screenshot after interaction
        dom = await self.page.content()
        truncated_dom = dom[:5000] + "…" if len(dom) > 5000 else dom
        self.trace_writer.log_step("observation", {
            "type": "dom_snapshot_post_click",
            "url": self.page.url,
            "dom_truncated": truncated_dom,
            "dom_full_length": len(dom)
        })
        
        screenshot_path = self.output_dir / f"screenshot_{self.trace_writer.step_counter}.png"
        await self.page.screenshot(path=str(screenshot_path))
        self.trace_writer.log_step("observation", {
            "type": "screenshot_post_click",
            "path": str(screenshot_path)
        })

    async def extract_text(self, selector: str = "body"):
        element = await self.page.query_selector(selector)
        text = await element.inner_text() if element else ""
        self.trace_writer.log_step("extraction", {"selector": selector, "text_preview": text[:500]})
        return text

    async def close(self):
        if self.context:
            await self.context.close()
        if self.playwright:
            await self.playwright.stop()
        
        har_path = self.output_dir / "trace.har"
        self.trace_writer.log_step("metadata", {
            "har_file": str(har_path)
        })
