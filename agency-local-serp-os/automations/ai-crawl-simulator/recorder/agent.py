import asyncio
import json
from langchain_openai import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import tool
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from .browser import StealthBrowser
from .trace import TraceWriter
from pathlib import Path

class RecordingAgent:
    def __init__(self, trace_writer: TraceWriter, goal: str, output_dir: Path, headless=True):
        self.trace = trace_writer
        self.goal = goal
        self.browser = StealthBrowser(trace_writer, output_dir, headless=headless)
        self.llm = ChatOpenAI(model="gpt-4o", temperature=0)

        # Define tools that call our wrapper
        @tool
        def goto(url: str) -> str:
            """Navigate to a specified URL."""
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(self.browser.goto(url), loop)
            future.result()
            return f"Successfully navigated to {url}"

        @tool
        def click(selector: str) -> str:
            """Click on an HTML element matching the given CSS selector."""
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(self.browser.click(selector), loop)
            future.result()
            return f"Successfully clicked {selector}"

        @tool
        def extract_text(selector: str = "body") -> str:
            """Extract visible text from the specified selector (default: body)."""
            loop = asyncio.get_event_loop()
            future = asyncio.run_coroutine_threadsafe(self.browser.extract_text(selector), loop)
            text = future.result()
            return f"Extracted text preview: {text[:500]}"

        self.tools = [goto, click, extract_text]

        prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a web research agent. Your goal: {goal}. Use the tools to browse and extract information. At each step, explain what you see and what you are skipping (e.g., ads, irrelevant columns, header links). If you find the required information, say 'goal achieved'. Return ONLY the tool calls to progress."),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        agent = create_openai_tools_agent(self.llm, self.tools, prompt)
        self.executor = AgentExecutor(agent=agent, tools=self.tools, verbose=True, handle_parsing_errors=True)

    async def run(self, max_steps=10):
        await self.browser.start()
        chat_history = []
        for step in range(max_steps):
            # Log LLM input
            self.trace.log_step("llm_input", {
                "goal": self.goal,
                "chat_history": [str(msg) for msg in chat_history],
                "step_number": step
            })
            
            # Formulate step prompt
            step_prompt = f"Step {step+1}: Continue working toward goal. Describe what you see and what you are skipping."
            
            # Invoke LLM loop
            response = await self.executor.ainvoke({
                "input": step_prompt,
                "goal": self.goal,
                "chat_history": chat_history,
            })
            
            # Log LLM output
            self.trace.log_step("llm_output", {
                "output": response["output"],
                "intermediate_steps": [
                    (str(action), str(observation)) for action, observation in response.get("intermediate_steps", [])
                ]
            })
            
            # Extract and log skip reason if present in output
            if "skip" in response["output"].lower():
                self.trace.log_step("skip_reason", {
                    "reason": response["output"],
                    "step": step
                })
                
            chat_history.append(("human", response["output"]))
            
            if "goal achieved" in response["output"].lower():
                self.trace.log_step("metadata", {"status": "success", "message": "Goal achieved reported by agent"})
                break
        else:
            self.trace.log_step("metadata", {"status": "max_steps", "message": "Reached maximum allowed steps"})
            
        await self.browser.close()
