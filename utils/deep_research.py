"""
Deep Research module for Autodidact
Refactored from 02-topic-then-deep-research.py
"""

import json
import time
from typing import Dict, Optional
import openai
from openai import OpenAI
from utils.config import DEEP_RESEARCH_MODEL, DEEP_RESEARCH_POLL_INTERVAL

import jsonschema, networkx as nx, Levenshtein

# After we get the user's topic & time investment preferences, this prompt is used to ask clarifying questions to the user
TOPIC_CLARIFYING_PROMPT = """
You will be given a short topic that a user wants to learn alongside the time they want to invest. Your job is NOT to answer it or complete the task, but instead to ask clarifying questions that would help a syllabus planner to understand what exactly the user wants to learn.

GUIDELINES:
1. **Focus on Learning Scope & Learner Profile**
- Consider what information would change the structure, depth, or direction for the specialized learning plan, and ask questions to clarify.
  - For example, you might want to ask questions to clarify what aspects of the topic the user is interested in, what if any background knowledge they have, their purpose for learning, etc.
- things to avoid asking about: preferred learning method or media formats (since our system will be chat-bot driven)

2. **Do Not Invent Preferences**
- If the user did not mention a preference, *do not assume it*. Ask about it clearly and neutrally. When giving options, they should be relevant to the subject matter.

3. **Use the First Person**
- Phrase your questions from the perspective of the assistant or researcher talking to the user (e.g., “Could you clarify...” or “Do you have a preference for...”)

4. **Use a Bulleted List if Multiple Questions**
- If there are multiple open questions, list them clearly in bullet format for readability.

5. **Avoid Overasking**
- Prioritize the 4-6 questions that would most reduce ambiguity or scope creep. You don’t need to ask *everything*, just the most pivotal unknowns.

6. **Format for Conversational Use**
- The output should sound helpful and conversational—not like a form. Aim for a natural tone while still being precise.
"""

# This prompt will be passed the user's topic, clarifying questions, and their responses.
# It will be used to rewrite the topic into a more specific and detailed topic instruction, which will finally be passed into the deep research prompt.
TOPIC_REWRITING_PROMPT = """
You will be given an initial topic by the user, followed by clarifying questions, followed by the user's responses. Your job is to rewrite these into a concise detailed topic instruction.

GUIDELINES:
1. **Maximize Specificity and Detail**
- Include all known user preferences and explicitly list key attributes or dimensions to consider.
- It is of utmost importance that all details from the user are included in the instructions.

2. **Avoid Unwarranted Assumptions**
- If the user has not provided a particular detail, do not invent one.
- Instead, state the lack of specification and guide the planner to treat it as flexible or accept all possible options.

3. **Important details first**
- The first sentence should contain be a complete sentence saying what the user wants to learn, and further sentences should flesh all relevant details out.

4. **Use the First Person**
- Phrase the request from the perspective of the user.
"""


# Updated developer prompt to include learning objectives
DEVELOPER_PROMPT = """
You are a “Deep-Research Curriculum Architect” with the goal of making the optimal learning syllabus for motivated autodidacts  on the topic user asks of you

TASK 1 – RESOURCES  
• Identify 10–15 authoritative, learner-friendly resources suitable for motivated autodidacts on the specified topic.
• Return them as a JSON array **resources** with:  
  { "rid", "title", "type", "url", "date", "scope" }  
  – type ∈ {book | paper | video | interactive | article}.  
  – scope = one-sentence summary.

TASK 2 – GRAPH  
• Build a directed-acyclic knowledge graph with **≈ 2 nodes for every hour of study time stated by the user (minimum 8, maximum 40), ±2 nodes allowed**.  
• Each node must be teachable in ~30 min (split >45 min concepts, merge <15 min).  
• Node schema:  
  {
    "id": "kebab-case",                  // unique  
    "title": "human-readable",  
    "prerequisites": ["id1","id2","id3"],// ≤3; omit if none  
    "objectives": [                      // 5–7, Bloom verbs, ≤12 words
      "Explain …", "Calculate …"
    ],
    "sections": [                        // pointers into resources
      { "rid": "mastering_bitcoin_2e", "loc": "Ch.8 §Difficulty" }
    ]
  }

HARD CONSTRAINTS  
• Graph acyclic; ≥10 % roots (no prerequisites) and ≥15 % leaves (no dependants).  
• Every prerequisite **must exactly match an “id” that appears in this JSON**.  
• Use only `rid` values present in **resources**.  
• Return **one valid JSON object** with keys `"resources"` and `"nodes"`.  
• Any non-JSON text will be discarded.
"""


def poll_background_job(client: OpenAI, job_id: str) -> Dict:
    """Poll until a background deep-research job is complete."""
    while True:
        job = client.responses.retrieve(job_id)
        status = job.status
        if status in ("completed", "failed", "cancelled", "expired"):
            return job
        print(f"[{time.strftime('%H:%M:%S')}] Job {job_id} → {status} …")
        time.sleep(DEEP_RESEARCH_POLL_INTERVAL)



SCHEMA = {
  "type": "object",
  "properties": {
    "resources": {
      "type": "array",
      "items": {
        "type":"object",
        "required":["rid","title","type","url"],
        "properties":{
          "rid":{"type":"string"},
          "title":{"type":"string"},
          "type":{"enum":["book","paper","video","interactive","article"]},
          "url":{"type":"string","format":"uri"}
        }
      }
    },
    "nodes": {
      "type":"array",
      "items":{
        "type":"object",
        "required":["id","title","objectives"],
        "properties":{
          "id":{"type":"string"},
          "title":{"type":"string"},
          "prerequisites":{"type":"array","items":{"type":"string"}},
          "objectives":{"type":"array","minItems":5,"maxItems":7},
          "sections":{"type":"array",
              "items":{"type":"object",
                       "required":["rid","loc"],
                       "properties":{"rid":{"type":"string"},"loc":{"type":"string"}}}
          }
        }
      }
    }
  },
  "required":["resources","nodes"]
}

def lint(payload:str)->list[str]:
    """Return list of error strings or [] if valid."""
    errors=[]
    try:
        data=json.loads(payload)
    except Exception as e:
        return [f"Invalid JSON: {e}"]
    try:
        jsonschema.validate(data, SCHEMA)
    except jsonschema.ValidationError as e:
        errors.append(f"Schema error: {e.message}")
    # ---- custom checks ----
    node_ids={n["id"] for n in data["nodes"]}
    rid_set={r["rid"] for r in data["resources"]}
    # dangling prereqs
    for n in data["nodes"]:
        for p in n.get("prerequisites",[]):
            if p not in node_ids:
                errors.append(f"Node '{n['id']}' has unknown prerequisite '{p}'")
    # dangling rid refs
    for n in data["nodes"]:
        for s in n.get("sections",[]):
            if s["rid"] not in rid_set:
                errors.append(f"Node '{n['id']}' references unknown rid '{s['rid']}'")
    # cycles
    g=nx.DiGraph([(p,n["id"]) for n in data["nodes"] for p in n.get("prerequisites",[])])
    try:
        nx.find_cycle(g,orientation="original")
        errors.append("Graph contains a prerequisite cycle")
    except nx.exception.NetworkXNoCycle:
        pass
    return errors

JSON_GUARDIAN_PROMPT = """
You are a “JSON Repair Assistant”.
Below is RAW_JSON followed by ERRORS detected by our validator.
• Return a **single corrected JSON object**—no comments, no markdown.
• Fix each error.  Strategies:
  1. If a prerequisite or rid is a near-miss typo, rename to the closest existing id (Levenshtein ≤ 2).
  2. Otherwise delete that prerequisite / section entry.
  3. Add missing brackets/commas to make valid JSON.
• Do NOT invent new nodes or resources beyond what exists.
• Preserve field order; keep text unchanged unless required to fix an error.

RAW_JSON:
<<<
{raw_json}
>>>

ERRORS:
{error_bullets}
"""

def guardian_fixer(raw_json_str, error_bullets, client, high_model=False):
    prompt = JSON_GUARDIAN_PROMPT.format(
        raw_json=raw_json_str,
        error_bullets="\n".join(f"• {e}" for e in error_bullets)
    )
    print(f"[deep_research_output_cleanup] Prompt: {prompt}")
    print(f"[deep_research_output_cleanup] Model: {'o4-mini' if high_model else 'gpt-4o'}")
    start = time.perf_counter()
    resp = client.responses.create(
          model= "o4-mini" if high_model else "gpt-4o",
          input=[{"role": "user", "content": prompt}],
          # only include the reasoning if model is o4-mini
          reasoning={"summary": "auto"} if high_model else None
        )
    elapsed = time.perf_counter() - start
    print(f"Guardian pass finished in {elapsed:.2f} s")
    return resp.output_text

def deep_research_output_cleanup(raw_json_str, client):
    # lint and if error, passes to o4-mini-high to fix
    errs = lint(raw_json_str)
    print(f"[deep_research_output_cleanup] first lint: Errs: {errs}")
    if not errs:
        return raw_json_str
    else:
        print(f"[deep_research_output_cleanup] Trying to fix with 4o")
        fixed = guardian_fixer(raw_json_str, errs, client, high_model=False)
        errs2 = lint(fixed)
        if not errs2:
            return fixed
        else: 
            print(f"[deep_research_output_cleanup] Trying to fix with o4-mini")
            fixed = guardian_fixer(fixed, errs2, client, high_model=True)
            errs3 = lint(fixed)
            if not errs3:
                return fixed
            else:
                raise RuntimeError(f"[deep_research_output_cleanup] Failed to fix with both models")

test_data = """
{
  "resources": [
    {
      "rid": "bitcoin_whitepaper2",
      "title": "Bitcoin: A Peer-to-Peer Electronic Cash System",
      "type": "paper",
      "url": "https://bitcoin.org/bitcoin.pdf",
      "date": "2008-10-31",
      "scope": "Original whitepaper by Satoshi Nakamoto introducing Bitcoin\u2019s design and goals."
    },
    {
      "rid": "mastering_bitcoin_2e",
      "title": "Mastering Bitcoin, 2nd Ed.",
      "type": "book",
      "url": "https://www.oreilly.com/library/view/mastering-bitcoin-2nd/9781491954379/",
      "date": "2021-01-13",
      "scope": "Comprehensive, developer-friendly guide to Bitcoin\u2019s protocol, mining and security."
    },
    {
      "rid": "digital_gold",
      "title": "Digital Gold: Bitcoin and the Inside Story of the Misfits and Millionaires Trying to Reinvent Money",
      "type": "book",
      "url": "https://www.harpercollins.com/products/digital-gold-nathaniel-popper",
      "date": "2015-05-19",
      "scope": "Narrative history of Bitcoin\u2019s early years and key personalities (2009-2014)."
    },
    {
      "rid": "bitcoin_standard",
      "title": "The Bitcoin Standard",
      "type": "book",
      "url": "https://saifedean.com/the-bitcoin-standard",
      "date": "2018-04-24",
      "scope": "Explores Bitcoin\u2019s monetary history, fixed supply and economic implications."
    },
    {
      "rid": "3b1b_bitcoin_video",
      "title": "But How Does Bitcoin Actually Work? (3Blue1Brown)",
      "type": "video",
      "url": "https://www.3blue1brown.com/lessons/bitcoin",
      "date": "2025-05-04",
      "scope": "Visual 30-minute lesson on ledgers, proof-of-work, mining and blockchains."
    },
    {
      "rid": "forbes_bitcoin_intro",
      "title": "What Is Bitcoin? How Does It Work? \u2013 Forbes Advisor",
      "type": "article",
      "url": "https://www.forbes.com/advisor/investing/cryptocurrency/what-is-bitcoin/",
      "date": "2024-06-08",
      "scope": "Plain-English explainer covering Bitcoin basics, history and supply cap."
    },
    {
      "rid": "ledger_most_btc",
      "title": "Who Owns the Most Bitcoin? \u2013 Ledger Academy",
      "type": "article",
      "url": "https://www.ledger.com/academy/topics/crypto/who-owns-the-most-bitcoin-the-largest-bitcoin-wallet-addresses",
      "date": "2025-03-20",
      "scope": "Breakdown of largest known wallets, Satoshi\u2019s stash, corporate and ETF holdings."
    },
    {
      "rid": "bitinfo_rich_list",
      "title": "Top 100 Richest Bitcoin Addresses & Distribution Charts",
      "type": "interactive",
      "url": "https://bitinfocharts.com/en/top-100-richest-bitcoin-addresses.html",
      "date": "2025-07-08",
      "scope": "Live dashboard of address balances and ownership distribution statistics."
    },
    {
      "rid": "btc_treasuries",
      "title": "BitcoinTreasuries.net \u2013 Public & Private Entities Holding BTC",
      "type": "interactive",
      "url": "https://bitcointreasuries.net/",
      "date": "2025-07-09",
      "scope": "Continuously-updated list of corporate treasuries and ETFs with Bitcoin on balance sheets."
    },
    {
      "rid": "whitehouse_btc_reserve",
      "title": "Executive Order: Establishment of the U.S. Strategic Bitcoin Reserve",
      "type": "article",
      "url": "https://www.whitehouse.gov/presidential-actions/2025/03/establishment-of-the-strategic-bitcoin-reserve-and-united-states-digital-asset-stockpile/",
      "date": "2025-03-06",
      "scope": "Official policy detailing U.S. federal Bitcoin holdings and custodial framework."
    },
    {
      "rid": "reuters_ath_2025",
      "title": "Bitcoin Surges to Record $116,000 amid Institutional Demand",
      "type": "article",
      "url": "https://www.reuters.com/world/middle-east/dollar-catches-breath-brazil-real-slides-tariff-threat-bitcoin-near-record-high-2025-07-10/",
      "date": "2025-07-10",
      "scope": "News timeline summarising 2023-25 price milestones and policy catalysts."
    },
    {
      "rid": "vaneck_chaincheck",
      "title": "VanEck Bitcoin ChainCheck Dashboard \u2013 April 2025",
      "type": "article",
      "url": "https://www.vaneck.com/corp/en/news-and-insights/blogs/digital-assets/matthew-sigel-vaneck-mid-april-2025-bitcoin-chaincheck/",
      "date": "2025-04-14",
      "scope": "On-chain metrics on supply dormancy, holder categories and miner activity."
    }
  ],
  "nodes": [
    {
      "id": "bitcoin-origins-whitepaper",
      "title": "Bitcoin Origins & Whitepaper Fundamentals",
      "objectives": [
        "Describe problems Bitcoin set out to solve",
        "Summarize whitepaper\u2019s peer-to-peer model",
        "Explain role of proof-of-work in consensus",
        "Identify genesis block and first 50 BTC",
        "Contrast Bitcoin with earlier e-cash attempts",
        "Define key terms: block, hash, timestamp"
      ],
      "sections": [
        {
          "rid": "bitcoin_whitepaper",
          "loc": "\u00a71\u2013\u00a76"
        },
        {
          "rid": "digital_gold",
          "loc": "Ch.1 \u2018Genesis\u2019"
        }
      ],
      "learning_objectives": [
        {
          "description": "Describe problems Bitcoin set out to solve"
        },
        {
          "description": "Summarize whitepaper\u2019s peer-to-peer model"
        },
        {
          "description": "Explain role of proof-of-work in consensus"
        },
        {
          "description": "Identify genesis block and first 50 BTC"
        },
        {
          "description": "Contrast Bitcoin with earlier e-cash attempts"
        },
        {
          "description": "Define key terms: block, hash, timestamp"
        }
      ]
    },
    {
      "id": "early-adoption-2010-2014",
      "title": "Early Adoption & Milestones (2010-2014)",
      "prerequisites": [
        "bitcoin-origins-whitepaper"
      ],
      "objectives": [
        "Recall first Bitcoin transaction and Pizza Day",
        "Discuss Mt. Gox and Silk Road impacts",
        "Outline emergence of exchanges and wallets",
        "Explain regulatory firsts (FinCEN 2013)",
        "Assess community growth metrics by 2014",
        "Describe media perception in early years"
      ],
      "sections": [
        {
          "rid": "digital_gold",
          "loc": "Ch.6 \u2018Gox Rising\u2019"
        },
        {
          "rid": "reuters_ath_2025",
          "loc": "Timeline 2009-14 inset"
        }
      ],
      "learning_objectives": [
        {
          "description": "Recall first Bitcoin transaction and Pizza Day"
        },
        {
          "description": "Discuss Mt. Gox and Silk Road impacts"
        },
        {
          "description": "Outline emergence of exchanges and wallets"
        },
        {
          "description": "Explain regulatory firsts (FinCEN 2013)"
        },
        {
          "description": "Assess community growth metrics by 2014"
        },
        {
          "description": "Describe media perception in early years"
        }
      ]
    },
    {
      "id": "supply-halving-mechanics",
      "title": "Bitcoin Supply, Halvings & Monetary Policy",
      "prerequisites": [
        "bitcoin-origins-whitepaper"
      ],
      "objectives": [
        "Explain 21 million cap and issuance schedule",
        "Calculate block reward changes after halvings",
        "Interpret miner incentives and difficulty",
        "Relate scarcity narrative to store-of-value",
        "Compare inflation rates pre- and post-2024 halving",
        "Analyze supply-active metrics from on-chain data"
      ],
      "sections": [
        {
          "rid": "mastering_bitcoin_2e",
          "loc": "Ch.8 \u00a7Difficulty & Halving"
        },
        {
          "rid": "bitcoin_standard",
          "loc": "Ch.8 \u2018Sound Money\u2019"
        },
        {
          "rid": "vaneck_chaincheck",
          "loc": "Supply tables"
        }
      ],
      "learning_objectives": [
        {
          "description": "Explain 21 million cap and issuance schedule"
        },
        {
          "description": "Calculate block reward changes after halvings"
        },
        {
          "description": "Interpret miner incentives and difficulty"
        },
        {
          "description": "Relate scarcity narrative to store-of-value"
        },
        {
          "description": "Compare inflation rates pre- and post-2024 halving"
        },
        {
          "description": "Analyze supply-active metrics from on-chain data"
        }
      ]
    },
    {
      "id": "major-price-milestones",
      "title": "Major Price Milestones & Market Catalysts",
      "prerequisites": [
        "early-adoption-2010-2014",
        "supply-halving-mechanics"
      ],
      "objectives": [
        "Chart BTC price from $0.01 to $116k",
        "Correlate halvings with bull cycles",
        "Identify ETF approvals and policy impacts",
        "Evaluate institutional FOMO narratives",
        "Discuss volatility and drawdown patterns"
      ],
      "sections": [
        {
          "rid": "reuters_ath_2025",
          "loc": "All-time-high report"
        }
      ],
      "learning_objectives": [
        {
          "description": "Chart BTC price from $0.01 to $116k"
        },
        {
          "description": "Correlate halvings with bull cycles"
        },
        {
          "description": "Identify ETF approvals and policy impacts"
        },
        {
          "description": "Evaluate institutional FOMO narratives"
        },
        {
          "description": "Discuss volatility and drawdown patterns"
        }
      ]
    },
    {
      "id": "address-distribution-basics",
      "title": "Address Structure & Ownership Distribution",
      "prerequisites": [
        "bitcoin-origins-whitepaper",
        "supply-halving-mechanics"
      ],
      "objectives": [
        "Differentiate address vs. wallet concepts",
        "Navigate public ledger to trace balances",
        "Summarize Glassnode long-/short-term holders",
        "Calculate % supply on exchanges",
        "Discuss privacy limits of pseudonymity",
        "Interpret distribution charts by size"
      ],
      "sections": [
        {
          "rid": "forbes_bitcoin_intro",
          "loc": "\u2018Public Ledger\u2019 section"
        },
        {
          "rid": "bitinfo_rich_list",
          "loc": "Distribution pie chart"
        }
      ],
      "learning_objectives": [
        {
          "description": "Differentiate address vs. wallet concepts"
        },
        {
          "description": "Navigate public ledger to trace balances"
        },
        {
          "description": "Summarize Glassnode long-/short-term holders"
        },
        {
          "description": "Calculate % supply on exchanges"
        },
        {
          "description": "Discuss privacy limits of pseudonymity"
        },
        {
          "description": "Interpret distribution charts by size"
        }
      ]
    },
    {
      "id": "major-whales-and-wallets",
      "title": "Satoshi & Other Major Whales",
      "prerequisites": [
        "address-distribution-basics"
      ],
      "objectives": [
        "Estimate Satoshi\u2019s dormant holdings",
        "Rank top exchange-controlled wallets",
        "Differentiate custodian vs. proprietary funds",
        "Assess whale influence on liquidity",
        "Explain proof-of-reserves concepts",
        "Evaluate risks of concentrated ownership"
      ],
      "sections": [
        {
          "rid": "ledger_most_btc",
          "loc": "\u2018Top Bitcoin Holders\u2019"
        },
        {
          "rid": "bitinfo_rich_list",
          "loc": "Top 10 addresses table"
        }
      ],
      "learning_objectives": [
        {
          "description": "Estimate Satoshi\u2019s dormant holdings"
        },
        {
          "description": "Rank top exchange-controlled wallets"
        },
        {
          "description": "Differentiate custodian vs. proprietary funds"
        },
        {
          "description": "Assess whale influence on liquidity"
        },
        {
          "description": "Explain proof-of-reserves concepts"
        },
        {
          "description": "Evaluate risks of concentrated ownership"
        }
      ]
    },
    {
      "id": "corporate-bitcoin-treasuries",
      "title": "Corporate & ETF Bitcoin Treasuries",
      "prerequisites": [
        "major-whales-and-wallets"
      ],
      "objectives": [
        "Identify leading public-company BTC holders",
        "Compare MicroStrategy vs. ETFs like IBIT",
        "Analyze balance-sheet motivations",
        "Calculate treasury % of circulating supply",
        "Discuss accounting and regulatory factors",
        "Summarize 2025 surge in corporate adoption"
      ],
      "sections": [
        {
          "rid": "btc_treasuries",
          "loc": "Top 10 companies table"
        }
      ],
      "learning_objectives": [
        {
          "description": "Identify leading public-company BTC holders"
        },
        {
          "description": "Compare MicroStrategy vs. ETFs like IBIT"
        },
        {
          "description": "Analyze balance-sheet motivations"
        },
        {
          "description": "Calculate treasury % of circulating supply"
        },
        {
          "description": "Discuss accounting and regulatory factors"
        },
        {
          "description": "Summarize 2025 surge in corporate adoption"
        }
      ]
    },
    {
      "id": "government-bitcoin-holdings",
      "title": "Government Bitcoin Reserves & Seizures",
      "prerequisites": [
        "corporate-bitcoin-treasuries"
      ],
      "objectives": [
        "List nations publicly holding BTC",
        "Explain U.S. strategic reserve policy",
        "Quantify estimated 200k BTC U.S. holdings",
        "Contrast seizure-based vs. purchase-based reserves",
        "Debate geopolitical implications of state BTC",
        "Assess transparency challenges in sovereign wallets"
      ],
      "sections": [
        {
          "rid": "whitehouse_btc_reserve",
          "loc": "Sec.1-4"
        },
        {
          "rid": "ledger_most_btc",
          "loc": "\u2018What Country Owns the Most Bitcoin?\u2019"
        }
      ],
      "learning_objectives": [
        {
          "description": "List nations publicly holding BTC"
        },
        {
          "description": "Explain U.S. strategic reserve policy"
        },
        {
          "description": "Quantify estimated 200k BTC U.S. holdings"
        },
        {
          "description": "Contrast seizure-based vs. purchase-based reserves"
        },
        {
          "description": "Debate geopolitical implications of state BTC"
        },
        {
          "description": "Assess transparency challenges in sovereign wallets"
        }
      ]
    },
    {
      "id": "onchain-analysis-tools",
      "title": "Hands-On: Using On-Chain Analysis Tools",
      "objectives": [
        "Use block explorers to trace transactions",
        "Query rich-list and supply dashboards",
        "Visualize dormancy and HODL waves",
        "Verify exchange proof-of-reserves claims",
        "Apply hash-rate and difficulty charts",
        "Interpret data limitations and biases"
      ],
      "sections": [
        {
          "rid": "3b1b_bitcoin_video",
          "loc": "\u2018Creating a Blockchain\u2019 segment"
        },
        {
          "rid": "bitinfo_rich_list",
          "loc": "Explorer UI"
        }
      ],
      "learning_objectives": [
        {
          "description": "Use block explorers to trace transactions"
        },
        {
          "description": "Query rich-list and supply dashboards"
        },
        {
          "description": "Visualize dormancy and HODL waves"
        },
        {
          "description": "Verify exchange proof-of-reserves claims"
        },
        {
          "description": "Apply hash-rate and difficulty charts"
        },
        {
          "description": "Interpret data limitations and biases"
        }
      ]
    },
    {
      "id": "interpreting-ownership-landscape",
      "title": "Interpreting the 2025 Ownership Landscape",
      "prerequisites": [
        "address-distribution-basics",
        "onchain-analysis-tools"
      ],
      "objectives": [
        "Synthesize data from whales, corporates, governments",
        "Evaluate concentration vs. decentralization trends",
        "Estimate long-term vs. short-term holder ratios",
        "Forecast impact of ETF growth on ownership",
        "Debate future scenarios for BTC distribution",
        "Formulate personal risk assessment strategies"
      ],
      "sections": [
        {
          "rid": "vaneck_chaincheck",
          "loc": "Holder composition metrics"
        },
        {
          "rid": "ledger_most_btc",
          "loc": "Summary conclusions"
        }
      ],
      "learning_objectives": [
        {
          "description": "Synthesize data from whales, corporates, governments"
        },
        {
          "description": "Evaluate concentration vs. decentralization trends"
        },
        {
          "description": "Estimate long-term vs. short-term holder ratios"
        },
        {
          "description": "Forecast impact of ETF growth on ownership"
        },
        {
          "description": "Debate future scenarios for BTC distribution"
        },
        {
          "description": "Formulate personal risk assessment strategies"
        }
      ]
    }
  ]
}
"""

