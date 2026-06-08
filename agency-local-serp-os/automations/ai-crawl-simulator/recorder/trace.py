import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

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

    def log_step(self, step_type: str, data: Dict[str, Any]):
        """step_type: llm_input, llm_output, browser_action, observation, skip_reason, network, extraction, metadata"""
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
