import json
import uuid
import yaml
from pathlib import Path

def get_position_weight(rank: int) -> float:
    # E.g. Position 1 = 1.0, Position 5 = 0.3
    if rank <= 0: return 0.0
    return max(0.01, 1.0 / rank)

def load_aggregators():
    root_dir = Path.cwd()
    agg_file = root_dir / "shared_schemas/aggregators.yaml"
    if agg_file.exists():
        with open(agg_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("aggregators", [])
    return ["yelp.com", "angi.com", "houzz.com", "homeadvisor.com"]

def analyze_serp_estate(client_id: str, keyword: str, serp_results: list, lead_value: float = 100.0):
    root_dir = Path.cwd()
    comp_file = root_dir / f"clients/{client_id}/facts/competition.yaml"
    
    owned_domains = []
    controlled_domains = ["medium.com", "youtube.com", "facebook.com"] 
    aggregators = load_aggregators()
    
    if comp_file.exists():
        with open(comp_file, "r", encoding="utf-8") as f:
            comp_data = yaml.safe_load(f)
            owned_domains = comp_data.get("owned_domains", [])
            
    if not owned_domains:
        owned_domains = ["example-hvac.com"]
        
    owned_best_rank = 999
    controlled_best_rank = 999
    controlled_best_url = ""
    
    # --- Matrix Calculation Variables ---
    sov_scores = {"owned": 0.0, "controlled": 0.0, "aggregator": 0.0, "competitor": 0.0}
    total_slots = len(serp_results)
    
    for rank, result in enumerate(serp_results, start=1):
        url = result.get("url", "").lower()
        weight = get_position_weight(rank)
        slot_value = weight * lead_value
        
        is_owned = any(d in url for d in owned_domains)
        is_controlled = any(d in url for d in controlled_domains)
        is_aggregator = any(d in url for d in aggregators)
        
        # 3. Aggregator vs True Competitor Filtering
        if is_owned:
            sov_scores["owned"] += slot_value
            owned_best_rank = min(owned_best_rank, rank)
        elif is_controlled:
            sov_scores["controlled"] += slot_value
            if rank < controlled_best_rank:
                controlled_best_rank = rank
                controlled_best_url = url
        elif is_aggregator:
            sov_scores["aggregator"] += slot_value
            # Trigger RPA orchestration instead of suggesting a new page
            generate_aggregator_rpa_workorder(client_id, keyword, url, rank)
        else:
            sov_scores["competitor"] += slot_value
            
    # Normalize SoV percentages
    total_value = sum(sov_scores.values()) or 1.0
    sov_percentages = {k: round((v / total_value) * 100, 2) for k, v in sov_scores.items()}
    
    print(f"[{keyword}] SoV Distribution: {sov_percentages}")
                
    if controlled_best_rank < owned_best_rank:
        generate_cannibalization_workorder(client_id, keyword, controlled_best_url, controlled_best_rank, owned_best_rank)
        
    return sov_percentages

def generate_aggregator_rpa_workorder(client_id: str, keyword: str, aggregator_url: str, rank: int):
    root_dir = Path.cwd()
    ticket_id = str(uuid.uuid4())[:8]
    
    # Drop into duoplus-rpa-orchestrator queue
    out_dir = root_dir / f"clients/{client_id}/rpa/approvals/pending"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_path = out_dir / f"RPA-OPTIMIZE-{ticket_id}.md"
    content = f"""---
status: NEEDS APPROVAL
type: aggregator_optimization
target_keyword: {keyword}
target_url: {aggregator_url}
action_required: Optimize Client Listing Inside Aggregator Directory
---

# 🚨 Aggregator Blocking SERP Slot

**Keyword:** `{keyword}`
**Aggregator Winning Slot:** {aggregator_url} (Rank #{rank})

Because this slot is dominated by an aggregator directory, building a new client page will not dislodge it. 

## Execution Plan:
Approving this card will trigger the `duoplus-rpa-orchestrator`. 
The RPA bot will navigate to the aggregator platform, locate your client's profile listing, and perform a full profile optimization (reviews, keyword injection, service tagging) to ensure the client is the #1 recommended business *inside* the aggregator's own local search engine.
"""
    # Only write if it doesn't already exist to prevent flooding
    if not out_path.exists():
        out_path.write_text(content, encoding="utf-8")

def generate_cannibalization_workorder(client_id: str, keyword: str, controlled_url: str, cont_rank: int, owned_rank: int):
    root_dir = Path.cwd()
    ticket_id = str(uuid.uuid4())[:8]
    
    out_dir = root_dir / f"clients/{client_id}/wordpress/approvals/pending"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_path = out_dir / f"CANNIBALIZATION-ALERT-{ticket_id}.md"
    
    content = f"""---
status: NEEDS APPROVAL
type: de_optimization
target_keyword: {keyword}
action_required: Reset Natural Hierarchy via Internal Equity
---

# 🚨 [De-optimization] Structural Cannibalization Alert

**Keyword:** `{keyword}`

A "Ghost Asset" Cannibalization event has been detected. One of your controlled/influenced secondary assets is currently outranking your core website for a transactional phrase, costing you direct conversion attribution.

## The Data:
- **Controlled Asset Rank:** #{cont_rank}
- **Controlled Asset URL:** {controlled_url}
- **Core Domain Rank:** #{owned_rank if owned_rank != 999 else "Not in top 100"}

## Execution Plan:
Approving this card will generate instructions to automatically modify the controlled asset.
The system will inject optimized internal equity (links, calls to action) pointing back down to the target page on the core domain to reset the natural hierarchy and pass the PageRank back to your money site.
"""
    if not out_path.exists():
        out_path.write_text(content, encoding="utf-8")

if __name__ == "__main__":
    # Test execution
    mock_serp = [
        {"url": "https://www.yelp.com/biz/example-hvac"}, # Rank 1 (Aggregator)
        {"url": "https://www.competitor.com/"}, # Rank 2 (Competitor)
        {"url": "https://www.youtube.com/watch?v=123"}, # Rank 3 (Controlled Ghost Asset)
        {"url": "https://www.example-hvac.com/ac-repair"}, # Rank 4 (Owned)
    ]
    analyze_serp_estate("example-hvac-client", "emergency ac repair fort lauderdale", mock_serp)
