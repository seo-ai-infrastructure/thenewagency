#!/usr/bin/env python3
import asyncio
import argparse
from pathlib import Path
from recorder.trace import TraceWriter
from recorder.agent import RecordingAgent
from generate_report import generate_report

async def main():
    parser = argparse.ArgumentParser(description="Fully Instrumented Browser Agent Recorder CLI")
    parser.add_argument("--goal", required=True, help="Research goal or target description for the web agent")
    parser.add_argument("--output-dir", required=True, type=Path, help="Directory where logs, HAR, screenshots, and report will be saved")
    parser.add_argument("--max-steps", type=int, default=10, help="Maximum decision steps allowed for the agent loop")
    parser.add_argument("--headless", action="store_true", help="Launch the Chromium stealth browser in headless mode")
    args = parser.parse_args()

    # Create trace directory and trace writer
    args.output_dir.mkdir(parents=True, exist_ok=True)
    trace = TraceWriter(args.output_dir, args.goal)
    
    print(f"[*] Spawning Agent Recorder session. Trace ID: {trace.trace_id}")
    print(f"[*] Goal: '{args.goal}'")
    print(f"[*] Logs and screenshots output directory: {args.output_dir}")

    # Build and execute the LLM browser agent
    agent = RecordingAgent(trace, args.goal, args.output_dir, headless=args.headless)
    try:
        await agent.run(max_steps=args.max_steps)
    finally:
        trace.close()
        
    print(f"[*] Trace closed. Generating HTML report...")
    try:
        generate_report(args.output_dir)
    except Exception as e:
        print(f"[!] Error generating report: {e}")

if __name__ == "__main__":
    try:
        # Standard asyncio launch
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Recording agent session interrupted by operator.")
