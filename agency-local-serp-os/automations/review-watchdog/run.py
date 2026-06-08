import json
import uuid
from pathlib import Path
from datetime import datetime, timezone, timedelta
import yaml

# ---------------------------------------------------------
# 1. Math & Anomaly Detection
# ---------------------------------------------------------
def calculate_review_anomaly(reviews: list, spike_window_hours: int = 48, baseline_days: int = 30) -> dict:
    """
    Analyzes review velocity to detect statistical anomalies indicative of click-farm fraud.
    """
    now = datetime.now(timezone.utc)
    spike_cutoff = now - timedelta(hours=spike_window_hours)
    baseline_cutoff = now - timedelta(days=baseline_days)
    
    spike_count = 0
    baseline_count = 0
    suspect_reviews = []
    
    for rev in reviews:
        # Gracefully handle missing or malformed dates
        try:
            date_str = rev.get("publish_date", now.isoformat()).replace('Z', '+00:00')
            rev_date = datetime.fromisoformat(date_str)
        except ValueError:
            continue
            
        if rev_date >= spike_cutoff:
            spike_count += 1
            
            # Bot detection heuristic: 5-star rating, minimal text, and low account history
            text_len = len(rev.get("text", ""))
            author_history = rev.get("author_review_count", 0)
            
            if rev.get("rating") == 5 and (text_len < 25 or author_history <= 1):
                suspect_reviews.append(rev)
                
        elif baseline_cutoff <= rev_date < spike_cutoff:
            baseline_count += 1

    # Calculate expected velocity over the spike window based on historical baseline
    expected_rate = (baseline_count / baseline_days) * (spike_window_hours / 24)
    expected_rate = max(1.0, expected_rate) # Prevent division by zero
    
    spike_multiplier = spike_count / expected_rate
    
    # Trigger condition: Velocity is 4x normal AND we have multiple suspect accounts
    is_anomaly = spike_multiplier >= 4.0 and len(suspect_reviews) >= 5
    
    return {
        "is_anomaly": is_anomaly,
        "multiplier": round(spike_multiplier, 2),
        "spike_count": spike_count,
        "suspect_count": len(suspect_reviews),
        "evidence": suspect_reviews[:5] # Keep top 5 for the redress payload
    }

# ---------------------------------------------------------
# 2. Work Order & Payload Generation
# ---------------------------------------------------------
def create_redress_workorder(client_id: str, comp_domain: str, anomaly: dict, place_id: str):
    root_dir = Path.cwd()
    ticket_id = str(uuid.uuid4())[:8]
    
    # Drop this into the browser (OpenClaw) queue for execution
    out_dir = root_dir / f"clients/{client_id}/browser/approvals/pending"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_path = out_dir / f"REDRESS-FRAUD-{ticket_id}.md"
    
    # Format the evidence string for the markdown card
    evidence_bullets = "\n".join([
        f"- **Author:** {r.get('author_name')} (Lifetime Reviews: {r.get('author_review_count')})\n  **Text:** '{r.get('text')}'" 
        for r in anomaly['evidence']
    ])
    
    card_content = f"""---
status: NEEDS APPROVAL
type: redress_execution
target_competitor: {comp_domain}
place_id: {place_id}
action_required: Submit Google Business Redressal Form
---

# 🚨 Competitor Review Fraud Detected

**Target:** {comp_domain}
**Anomaly Detected:** {anomaly['multiplier']}x velocity spike in the last 48 hours.

## The Data:
- **Total Reviews in 48h:** {anomaly['spike_count']}
- **Highly Suspect/Bot Reviews:** {anomaly['suspect_count']} (Generic text or 1-lifetime-review accounts)

## Evidence Payload:
{evidence_bullets}

## Execution Plan:
Approving this card will trigger the `cloakbrowser-runner`. 
The agent will navigate to the **Google Business Redressal Form**, input the Place ID (`{place_id}`), and submit the statistical proof of review manipulation (including the specific anomalous timestamps and author logs) to trigger a manual spam review by Google Trust & Safety.
"""
    out_path.write_text(card_content, encoding="utf-8")
    print(f"Generated Redress Workorder: {out_path.name}")

# ---------------------------------------------------------
# 3. Main Watchdog Loop
# ---------------------------------------------------------
def run_watchdog(client_id: str):
    print(f"Running Fake Review Assassin for: {client_id}")
    root_dir = Path.cwd()
    
    comp_file = root_dir / f"clients/{client_id}/facts/competition.yaml"
    if not comp_file.exists():
        print("No competition.yaml found.")
        return
        
    with open(comp_file, "r", encoding="utf-8") as f:
        competitors = yaml.safe_load(f).get("competitors", [])
        
    for comp in competitors:
        domain = comp.get("domain")
        place_id = comp.get("place_id")
        
        # Pulls from the ingestion engine output we built previously
        review_file = root_dir / f"clients/{client_id}/raw/reviews/{domain}_customer.json"
        if not review_file.exists():
            continue
            
        with open(review_file, "r", encoding="utf-8") as f:
            reviews = json.load(f)
            
        anomaly = calculate_review_anomaly(reviews)
        
        if anomaly["is_anomaly"]:
            print(f"  [!] Spike detected for {domain}! Generating execution payload.")
            create_redress_workorder(client_id, domain, anomaly, place_id)
        else:
            print(f"  [✓] Review velocity normal for {domain}.")

if __name__ == "__main__":
    run_watchdog("example-hvac-client")
