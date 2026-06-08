import json
import uuid
from pathlib import Path

def extract_context_snippet(run_id: str, comp_domain: str) -> str:
    """
    Mock function to look up matching citation context from raw archived responses.
    """
    # In a real system, this would parse `history/{run_id}_ai_overview.json` 
    # to find the specific text snippet where the competitor was cited.
    return f"Provides comprehensive {comp_domain} service comparisons and real-time pricing grids."

def create_work_order(client_id: str, subsystem: str, title: str, body: str):
    root_dir = Path.cwd()
    ticket_id = str(uuid.uuid4())[:8]
    
    # E.g. clients/<client_id>/wordpress/approvals/pending
    if subsystem == "wordpress-publisher":
        out_dir = root_dir / f"clients/{client_id}/wordpress/approvals/pending"
    else:
        out_dir = root_dir / f"clients/{client_id}/{subsystem}/approvals/pending"
        
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"AI-CONQUEST-{ticket_id}.md"
    
    content = f"""---
status: NEEDS APPROVAL
type: ai_citation_conquest
title: "{title}"
---

# 🚨 AI Citation Gap Detected

{body}

## Execution Plan:
Approving this card will trigger the `{subsystem}`. 
The AI writer will generate a highly optimized piece of content or schema markup that specifically answers the nuanced topic the competitor is currently being cited for. The goal is to ingest this into the client's asset to displace the competitor in the AI Overview.
"""
    if not out_path.exists():
        out_path.write_text(content, encoding="utf-8")
        print(f"Generated AI Conquest Workorder: {out_path.name}")

def analyze_ai_citations(record: dict):
    """
    Evaluates AI Search citations. If the client is missing but competitors are present,
    it triggers a conversion gap work order.
    """
    client_cited = record.get('client_cited', False)
    cited_competitors = record.get('cited_competitors', [])
    
    if not client_cited and cited_competitors:
        for comp_domain in cited_competitors:
            citation_context = extract_context_snippet(record.get('run_id', 'latest'), comp_domain)
            
            create_work_order(
                client_id=record.get('client_id', 'unknown'),
                subsystem="wordpress-publisher",
                title=f"AI Citation Conquest: Target {record.get('keyword', 'unknown')}",
                body=f"Competitor **{comp_domain}** cited for: *'{citation_context}'*.\n\nGenerate content covering this specific nuance to displace their citation entry."
            )

if __name__ == "__main__":
    # Test execution
    mock_record = {
        "client_id": "example-hvac-client",
        "keyword": "best ac brands fort lauderdale",
        "run_id": "run_942",
        "client_cited": False,
        "cited_competitors": ["competitor-hvac.com", "another-local-tech.com"]
    }
    analyze_ai_citations(mock_record)
