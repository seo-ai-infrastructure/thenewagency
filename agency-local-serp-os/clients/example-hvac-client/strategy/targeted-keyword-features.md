# Targeted Keyword + Features List — Mobile SERP-Feature Takeover

**Service:** House AC Repair (Residential HVAC)
**Market:** Fort Lauderdale & Broward County, FL
**SERP source:** DataForSEO **mobile** (live)
**Grouping:** by content cluster (one content asset targets the whole cluster)
**Barnacle policy:** stand up **2** high-authority third-party assets per term

## How to read this

For each cluster: the single **content asset**, its **keywords** (lead value + lane + real mobile features), the **union of features** to take over, the **exact tactic per feature** from `serp_feature_takeover.yaml`, and the best **2 barnacle platforms**.

Feature distribution across all 28 terms (observed): **people_also_ask ≈ 100%** of terms · **local_pack/local_services** on local + transactional terms · **ai_overview** on cost / question / emergency terms · **video + featured_snippet** on research / cost / coil terms.

Playbook tactic key:
- **ai_overview** → YouTube video + NotebookLM source + Cloudflare edge worker serving static HTML+Schema (~10ms)
- **people_also_ask** → each PAA question = a secondary keyword → a YouTube **chapter** + an on-page **H2/H3** concise answer
- **featured_snippet** → pillar article (+video+images) syndicated to **Patch.com**, linked from **LinkedIn Pulse** + a **Reddit** sidebar wiki
- **local_pack** → GBP optimization, reviews, NAP citations (**local_services** → verified Google LSA / Google Guaranteed)
- **organic** → optimized service page + internal links
- **video** → optimized YouTube video (title, chapters, transcript, schema)

---

## Cluster 1 — AC Repair (Core Service)

**Content asset:** AC Repair service page (Fort Lauderdale) + GBP-linked local landing
**Intent:** transactional

| Keyword | Lead value | Lane | Real mobile features |
|---|---|---|---|
| ac repair fort lauderdale fl | high | local_finder | local_pack, organic, discussions_and_forums, PAA, people_also_search |
| air conditioning repair fort lauderdale | high | local_finder | local_services, ai_overview, organic, people_also_search, discussions_and_forums, PAA, perspectives |
| ac repair near me | high | local_finder | local_pack, PAA, people_also_search, organic |
| broward county ac repair company | medium_high | organic_mobile | local_services, local_pack, organic, people_also_search, PAA |

**Target features (union):** local_pack · local_services · ai_overview · people_also_ask · organic · discussions_and_forums · people_also_search · perspectives

**Per-feature tactics**
- **local_pack** → GBP optimization (primary category *HVAC contractor* + *Air conditioning repair service*, geo-tagged photos, weekly posts), drive 5-star reviews containing "AC repair Fort Lauderdale," and clean NAP citations (Yelp, BBB, Angi, Apple Maps, Bing Places).
- **local_services** → Activate/verify Google Local Services Ads (Google Guaranteed badge, license + insurance upload, review pass-through) so the LSA unit sits above the 3-pack.
- **ai_overview** → YouTube video "How AC Repair Works in Fort Lauderdale" + NotebookLM source set on local HVAC repair + Cloudflare edge worker serving static HTML+Schema (LocalBusiness/HVACBusiness) at ~10ms.
- **people_also_ask** → "How much is AC repair in Fort Lauderdale?", "Who is the best AC repair company?" → each becomes a YouTube chapter + an on-page H2/H3 with a 40–55 word answer.
- **organic** → optimized AC Repair service page + internal links from cost, emergency, and city pages.
- **discussions_and_forums** → seed an authentic r/fortlauderdale + Nextdoor thread on "who to call for AC repair."

**Barnacle (2):** YouTube · Nextdoor

---

## Cluster 2 — Emergency / 24-7 AC

**Content asset:** Emergency 24/7 AC Repair landing page (click-to-call optimized)
**Intent:** transactional

| Keyword | Lead value | Lane | Real mobile features |
|---|---|---|---|
| 24 hour ac repair fort lauderdale | high | local_finder | ai_overview, organic, people_also_search, PAA |
| emergency ac repair fort lauderdale fl | high | local_finder | ai_overview, organic, PAA, people_also_search |
| same day ac repair near me | high | local_finder | local_services, local_pack, PAA, people_also_search, organic |
| ac not cooling emergency repair | medium_high | organic_mobile | ai_overview, local_services, local_pack, PAA, video, organic, people_also_search, perspectives |

**Target features (union):** ai_overview · local_services · local_pack · people_also_ask · video · organic · people_also_search · perspectives

**Per-feature tactics**
- **ai_overview** → YouTube "What to do when your AC stops cooling (Fort Lauderdale emergency)" + NotebookLM source set + Cloudflare edge worker static HTML+Schema (Service + LocalBusiness, areaServed Broward) at ~10ms.
- **local_services** → Google LSA with 24/7 hours + emergency/same-day attributes to capture urgent clicks.
- **local_pack** → GBP set to 24-hour hours, "Emergency service" attribute, recent reviews mentioning "same day"/"midnight"; consistent NAP.
- **people_also_ask** → "Is there 24 hour AC repair near me?", "How much is emergency AC repair?" → YouTube chapter + on-page H2/H3 with click-to-call CTA.
- **video** → optimized YouTube video for "AC not cooling emergency repair" (title, timestamped chapters, transcript, VideoObject schema).
- **organic** → click-to-call Emergency 24/7 landing page + internal links from core repair and city pages.

**Barnacle (2):** YouTube · Nextdoor

---

## Cluster 3 — Evaporator Coil Repair / Replacement

**Content asset:** Evaporator Coil Repair & Replacement pillar page + explainer video
**Intent:** commercial

| Keyword | Lead value | Lane | Real mobile features |
|---|---|---|---|
| ac evaporator coil repair cost fort lauderdale fl | medium_high | organic_mobile | featured_snippet, PAA, organic, video, local_pack, people_also_search, paid |
| evaporator coil replacement cost fort lauderdale | medium_high | organic_mobile | ai_overview, organic, PAA, discussions_and_forums, video, knowledge_graph_expanded_item |
| who should i call for evaporator coil replacement in fort lauderdale | high | ai_mode | local_pack, PAA, organic |
| signs your ac evaporator coil is bad | medium | organic_mobile | ai_overview, PAA, video, organic, discussions_and_forums, people_also_search |

**Target features (union):** featured_snippet · ai_overview · video · people_also_ask · local_pack · organic · discussions_and_forums · people_also_search · knowledge_graph_expanded_item · paid

**Per-feature tactics**
- **featured_snippet** → pillar article on coil repair-vs-replacement cost (+ explainer video + labeled cost-table images) syndicated to a **Patch.com** article, linked from **LinkedIn Pulse** + a **Reddit** sidebar wiki to win position-0.
- **ai_overview** → YouTube "Evaporator coil replacement cost in Fort Lauderdale" + NotebookLM source set with cost ranges + Cloudflare edge worker static HTML+Schema (Article/FAQPage) at ~10ms.
- **video** → optimized YouTube explainer ("signs your coil is bad," cost breakdown) with chapters/transcript/VideoObject schema (video present on 3 of 4 terms).
- **people_also_ask** → "How much to replace an evaporator coil?", "Can a leaking coil be repaired?" → YouTube chapter + on-page H2/H3.
- **local_pack** → GBP + reviews mentioning "evaporator coil"/"coil replacement"; NAP for the high-intent "who should I call" term.
- **organic** → coil pillar page + internal links from cost and core repair pages.
- **discussions_and_forums** → seed a Reddit / HVAC-forum thread on coil replacement cost.

**Barnacle (2):** YouTube · Patch.com

---

## Cluster 4 — AC Repair Cost & Pricing

**Content asset:** AC Repair Cost guide (pricing pillar) + cost-range explainer video
**Intent:** commercial

| Keyword | Lead value | Lane | Real mobile features |
|---|---|---|---|
| ac repair cost fort lauderdale | medium_high | organic_mobile | ai_overview, local_services, PAA, local_pack, organic, people_also_search |
| how much does ac repair cost in florida | medium | ai_mode | ai_overview, organic, people_also_search, PAA, discussions_and_forums, paid |
| ac refrigerant recharge cost fort lauderdale | medium | organic_mobile | featured_snippet, PAA, people_also_search, organic, local_pack |
| average cost to fix ac not blowing cold air | medium | organic_mobile | ai_overview, PAA, people_also_search, organic, video, paid |

**Target features (union):** ai_overview · featured_snippet · video · local_services · local_pack · people_also_ask · organic · people_also_search · discussions_and_forums · paid

**Per-feature tactics**
- **ai_overview** → YouTube "AC repair cost in Florida explained" + NotebookLM source set of itemized cost ranges (refrigerant recharge, capacitor, compressor) + Cloudflare edge worker static HTML+Schema (FAQPage) at ~10ms.
- **featured_snippet** → pricing pillar with a clear cost table (+ video + images), syndicated to **Patch.com**, linked from **LinkedIn Pulse** + **Reddit** sidebar wiki to win position-0 on "refrigerant recharge cost."
- **video** → optimized YouTube cost-range explainer ("what it costs when AC won't blow cold air") with chapters/transcript/VideoObject schema.
- **local_services** → keep Google LSA verified with up-front pricing signals (present on "ac repair cost").
- **local_pack** → GBP + reviews referencing fair/transparent pricing; consistent NAP.
- **people_also_ask** → "How much does AC repair cost?", "Is it worth repairing an AC?" → YouTube chapter + on-page H2/H3 with a cost range.
- **organic** → pricing pillar page + internal links from core repair and coil pages.

**Barnacle (2):** YouTube · Patch.com

---

## Cluster 5 — AC Maintenance & Tune-Ups

**Content asset:** AC Maintenance & Tune-Up service page + seasonal checklist
**Intent:** commercial

| Keyword | Lead value | Lane | Real mobile features |
|---|---|---|---|
| ac tune up fort lauderdale | medium_high | local_finder | local_services, local_pack, organic, people_also_search, PAA |
| ac maintenance service broward county | medium_high | organic_mobile | ai_overview, local_services, organic, people_also_search, PAA |
| how often should you service your ac in florida | medium | ai_mode | ai_overview, organic, PAA, discussions_and_forums, people_also_search |
| ac tune up cost near me | medium | organic_mobile | local_pack, organic, people_also_search, PAA |

**Target features (union):** ai_overview · local_services · local_pack · people_also_ask · organic · people_also_search · discussions_and_forums

**Per-feature tactics**
- **ai_overview** → YouTube "How often to service your AC in Florida" + NotebookLM source set (Florida climate cadence) + Cloudflare edge worker static HTML+Schema (FAQPage/HowTo) at ~10ms.
- **local_services** → Google LSA with maintenance/tune-up attributes; keep Google Guaranteed badge active.
- **local_pack** → GBP optimization, seasonal tune-up GBP posts, reviews mentioning "tune up"/"maintenance plan"; consistent NAP.
- **people_also_ask** → "How often should AC be serviced?", "What does an AC tune-up include?" → YouTube chapter + on-page H2/H3.
- **organic** → maintenance service page with downloadable seasonal checklist + internal links from core repair page.
- **discussions_and_forums** → seed a Reddit/Nextdoor thread on AC service frequency in Florida heat.

**Barnacle (2):** YouTube · Nextdoor

---

## Cluster 6 — AC Installation & Replacement

**Content asset:** AC Installation & Replacement pillar page + financing/quote CTA
**Intent:** commercial

| Keyword | Lead value | Lane | Real mobile features |
|---|---|---|---|
| ac installation fort lauderdale | high | local_finder | local_pack, PAA, people_also_search, organic |
| ac unit replacement cost fort lauderdale fl | medium_high | organic_mobile | organic, PAA, people_also_search, local_pack |
| when should i replace my ac unit in florida | medium | ai_mode | ai_overview, organic, people_also_search, PAA, perspectives |
| new ac system cost broward county | medium_high | organic_mobile | ai_overview, organic, PAA, knowledge_graph_expanded_item |

**Target features (union):** ai_overview · local_pack · people_also_ask · organic · people_also_search · perspectives · knowledge_graph_expanded_item

**Per-feature tactics**
- **ai_overview** → YouTube "When to replace vs. repair your AC in Florida" + NotebookLM source set (unit age, SEER, cost-to-replace) + Cloudflare edge worker static HTML+Schema (FAQPage/Article) at ~10ms.
- **local_pack** → GBP with "AC installation" service + before/after install photos, financing-offer GBP post, reviews mentioning "new system install"; consistent NAP.
- **people_also_ask** → "When should I replace my AC?", "How much is a new AC unit?" → YouTube chapter + on-page H2/H3.
- **organic** → installation/replacement pillar page with financing + free-quote CTA + internal links from cost and maintenance pages.

**Barnacle (2):** YouTube · Patch.com

---

## Cluster 7 — Nearby City Service Area

**Content asset:** City service-area landing pages (Hollywood, Pompano Beach, Plantation, Coral Springs)
**Intent:** transactional

| Keyword | Lead value | Lane | Real mobile features |
|---|---|---|---|
| ac repair hollywood fl | high | local_finder | local_pack, PAA, organic, people_also_search |
| ac repair pompano beach fl | high | local_finder | local_services, local_pack, organic, people_also_search, PAA |
| air conditioning repair plantation fl | medium_high | local_finder | local_pack, organic, PAA, people_also_search |
| ac repair coral springs near me | medium_high | local_finder | local_services, local_pack, organic, people_also_search, PAA |

**Target features (union):** local_pack · local_services · people_also_ask · organic · people_also_search

**Per-feature tactics**
- **local_pack** → per-city GBP signals: service-area definitions, city-named GBP posts, reviews tagged to each city; NAP citations on local directories (Hollywood/Pompano/Plantation/Coral Springs chambers, Yelp city pages).
- **local_services** → Google LSA with service-area zip targeting for Pompano Beach and Coral Springs (LSA present on those terms).
- **people_also_ask** → "Who does AC repair in Hollywood FL?", "How much is AC repair in Pompano?" → YouTube chapter + on-page H2/H3 per city page.
- **organic** → distinct, non-templated city landing pages (unique copy, local landmarks, city-specific reviews) + internal links from the core AC Repair hub.

**Barnacle (2):** YouTube · Nextdoor

---

## Build Order (prioritized across all clusters)

Ranked by lead_value + feature opportunity — clusters with AIO + featured_snippet + video gaps and high lead_value first.

1. **Emergency 24/7 AC Repair landing page** *(Cluster 2)* — highest lead_value (3 high-intent terms) + richest stack: ai_overview ×3, video, local_pack/local_services, PAA. Urgent buyer intent with AIO + video gaps. **Gaps:** ai_overview, video, local_pack.
2. **AC Repair service page (core) + GBP local landing** *(Cluster 1)* — core money terms, all high lead_value, dense local_pack/local_services + AIO on the head term. The hub every other page links to, so build early. **Gaps:** local_pack, local_services, ai_overview.
3. **Evaporator Coil Repair & Replacement pillar + explainer video** *(Cluster 3)* — only cluster with featured_snippet + ai_overview + video all present, plus a high-value "who should I call" AI-mode term. Biggest position-0 / AIO / video stack. **Gaps:** featured_snippet, ai_overview, video.
4. **AC Repair Cost pricing pillar + cost-range video** *(Cluster 4)* — AIO ×3 + featured_snippet + video; strong AI-mode/research demand feeding the whole funnel. **Gaps:** ai_overview, featured_snippet, video.
5. **City service-area landing pages** *(Cluster 7)* — all high / medium_high transactional terms with local_pack + local_services on every term. Pure local-pack land-grab once the hub exists. **Gaps:** local_pack, local_services.
6. **AC Installation & Replacement pillar + financing CTA** *(Cluster 6)* — highest-ticket jobs; ai_overview ×2 + local_pack on the head term. Strong revenue/lead but lower urgency than repair. **Gaps:** ai_overview, local_pack.
7. **AC Maintenance & Tune-Up service page + checklist** *(Cluster 5)* — lower lead_value, recurring-revenue/retention play; AIO ×2 + local_pack/local_services. Build last as a nurture asset. **Gaps:** ai_overview, local_pack, local_services.
