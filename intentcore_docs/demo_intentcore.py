"""
IntentCore + FinRobot Demo Script

Demonstrates complete end-to-end flow:
1. Agent analyzes portfolio
2. Proposes high-stakes trade ($90M NVDA sell)
3. IntentCore intercepts and extracts reasoning
4. Governance engine requires human review
5. Human reviews and approves (with modification)
6. Trade executes
7. Result recorded

This simulates the production scenario without needing live LLM calls.
"""

import json
from datetime import datetime
from intentcore import IntentCoreRuntime, FinRobotBridge
from intentcore.core.reasoning_chain import ReasoningChain


def print_header(text):
    """Print formatted section header."""
    print("\n" + "="*80)
    print(f"  {text}")
    print("="*80 + "\n")


def simulate_agent_conversation():
    """
    Simulate FinRobot agent conversation history.

    In production, this would come from AutoGen's message history.
    """
    return [
        {
            "role": "user",
            "content": "Analyze our NVDA position and recommend rebalancing actions. Earnings announcement is tomorrow."
        },
        {
            "role": "assistant",
            "content": """I'll analyze the NVDA position.

Current Situation:
As of today, our portfolio shows NVDA concentration at 32%, significantly above our 25% maximum sector concentration policy. The position is valued at $280M in a $875M total portfolio. Given that NVIDIA's earnings announcement is scheduled for tomorrow, this creates additional timing risk.

Quantitative Analysis:
- Current NVDA holding: $280M (32% of portfolio)
- Target maximum: $218.75M (25% of portfolio)
- Required reduction: $61.25M minimum
- Recommended reduction: $90M (to provide buffer below threshold)
- This would bring NVDA to 21.7% of portfolio

Market Data:
- NVDA current price: $487.50
- 30-day average volume: 42M shares
- Recent volatility: 18.2% (elevated pre-earnings)
- Analyst consensus: 65% positive

Alternatives Considered:
1. Wait until after earnings: Risk of concentration violation if stock rises
2. Reduce by minimum ($61.25M): Leaves little buffer, may need adjustment again soon
3. Reduce by $90M: Provides comfortable buffer, reduces earnings risk
4. Reduce entire position: Too aggressive, NVDA remains fundamentally strong

Risks Identified:
- Execution risk: Large trade size may impact price
- Timing risk: Pre-earnings trade increases uncertainty
- Opportunity risk: If earnings positive, we reduce upside capture
- Market risk: Current elevated volatility

Rationale:
Given the policy violation (32% vs 25% max), pre-earnings timing risk, and need for portfolio risk reduction, I recommend selling $90M of NVDA. This action balances compliance requirements with prudent risk management while maintaining meaningful exposure to a strong holding.

I will execute this trade.
"""
        },
        {
            "role": "assistant",
            "tool_calls": [
                {
                    "id": "call_trade_123",
                    "type": "function",
                    "function": {
                        "name": "execute_trade",
                        "arguments": json.dumps({
                            "symbol": "NVDA",
                            "action": "SELL",
                            "amount": "$90M",
                            "reason": "Reduce pre-earnings concentration risk"
                        })
                    }
                }
            ]
        }
    ]


def demo_full_flow():
    """Run complete demo flow."""

    print_header("INTENTCORE + FINROBOT DEMO: $90M NVDA PRE-EARNINGS TRADE")

    print("Scenario:")
    print("  - Portfolio: $875M AUM hedge fund")
    print("  - Agent: Portfolio Rebalancing Agent")
    print("  - Decision: Sell $90M NVDA before earnings")
    print("  - Why High-Stakes: Exceeds $50M threshold + pre-earnings timing")

    # 1. Initialize IntentCore
    print_header("Step 1: Initialize IntentCore Runtime")

    runtime = IntentCoreRuntime(db_path="intentcore.db")
    print("✓ Runtime initialized")
    print("✓ Database ready")
    print("✓ Governance policies loaded")

    # 2. Simulate agent conversation
    print_header("Step 2: Agent Analyzes Position & Proposes Trade")

    messages = simulate_agent_conversation()

    print("Agent analyzed NVDA position:")
    print("  - Current: $280M (32% of portfolio)")
    print("  - Violation: Exceeds 25% max concentration")
    print("  - Timing: Earnings tomorrow")
    print("  - Proposal: Sell $90M")

    # Extract tool call
    tool_call = messages[-1]["tool_calls"][0]
    print(f"\n✓ Agent proposes: {tool_call['function']['name']}")
    print(f"  Parameters: {tool_call['function']['arguments']}")

    # 3. IntentCore intercepts and processes
    print_header("Step 3: IntentCore Intercepts & Extracts Reasoning")

    result = runtime.process_decision(
        agent_id="portfolio_agent_001",
        agent_role="Portfolio_Rebalancing_Agent",
        task="Analyze NVDA position and recommend rebalancing before earnings",
        messages=messages,
        tool_call=tool_call,
    )

    chain = result["reasoning_chain"]
    governance = result["governance_result"]

    print("✓ Reasoning extracted:")
    print(f"  - Situation: {len(chain.situation)} chars")
    print(f"  - Quantitative data: {len(chain.quantitative_analysis.get('amounts', []))} amounts found")
    print(f"  - Risks identified: {len(chain.risks)}")
    print(f"  - Completeness: {chain.completeness_score:.1%}")

    print(f"\n✓ Governance decision: {governance.decision}")
    print(f"  - Requires review: {governance.requires_review}")
    print(f"  - Policy checks: {len(governance.policy_checks)}")

    if governance.warnings:
        print(f"  - Warnings: {len(governance.warnings)}")
        for warning in governance.warnings:
            print(f"    • {warning}")

    # 4. Display reasoning summary
    print_header("Step 4: Complete Reasoning Chain")

    print("SITUATION:")
    print(chain.situation[:300] + "..." if len(chain.situation) > 300 else chain.situation)

    print("\nQUANTITATIVE ANALYSIS:")
    print(f"  Amounts: {', '.join(chain.quantitative_analysis.get('amounts', [])[:5])}")
    print(f"  Percentages: {', '.join(chain.quantitative_analysis.get('percentages', [])[:5])}")

    print("\nSELECTED ACTION:")
    print(f"  Function: {chain.selected_action.get('function')}")
    print(f"  Parameters: {json.dumps(chain.selected_action.get('parameters', {}), indent=2)}")

    print("\nRISKS:")
    for i, risk in enumerate(chain.risks[:3], 1):
        print(f"  {i}. {risk}")

    print(f"\nCOMPLETENESS: {chain.completeness_score:.1%}")
    if chain.missing_components:
        print(f"  Missing: {', '.join(chain.missing_components)}")

    # 5. Human review (simulated)
    print_header("Step 5: Human Review (Portfolio Manager)")

    print("Portfolio Manager: Sarah Chen")
    print("Review UI shows complete reasoning chain...")
    print("\nSarah's Analysis:")
    print("  - Reasoning is sound: concentration violation + pre-earnings risk")
    print("  - Trade size is appropriate for position")
    print("  - BUT: $90M is large for pre-earnings execution")
    print("  - DECISION: Approve with modification to $50M")
    print("  - RATIONALE: Reduce size given earnings uncertainty, execute rest post-earnings")

    # Submit human decision
    print("\n✓ Submitting decision...")

    updated_chain = runtime.submit_human_decision(
        chain_id=chain.chain_id,
        reviewer_id="sarah_chen",
        decision="approved",
        rationale="Trade rationale is sound. Reducing size to $50M given pre-earnings timing risk. Plan to execute remaining $40M after earnings clarity.",
        modification={
            "amount": "$50M",
            "notes": "Modified from $90M to $50M due to earnings timing"
        }
    )

    print("✓ Decision recorded:")
    print(f"  - Reviewer: {updated_chain.reviewer_id}")
    print(f"  - Decision: {updated_chain.human_decision}")
    print(f"  - Modification: {updated_chain.human_modification}")
    print(f"  - Review time: {(updated_chain.review_timestamp - chain.timestamp).total_seconds():.1f}s")

    # 6. Execution (simulated)
    print_header("Step 6: Trade Execution")

    print("Executing modified trade...")
    print("  - Original proposal: Sell $90M NVDA")
    print("  - Modified amount: Sell $50M NVDA")
    print("  - Execution: COMPLETE")

    runtime.record_execution(
        chain_id=chain.chain_id,
        status="completed",
        result={
            "executed_amount": "$50M",
            "shares_sold": 102_564,
            "avg_price": "$487.45",
            "execution_time": "14.3s",
            "slippage": "0.02%",
        }
    )

    print("\n✓ Execution completed successfully")
    print("  - Amount: $50M")
    print("  - Shares: 102,564")
    print("  - Avg price: $487.45")
    print("  - Time: 14.3s")

    # 7. Summary & Learning
    print_header("Step 7: Summary & Learning Opportunities")

    print("DECISION SUMMARY:")
    print(f"  Chain ID: {chain.chain_id}")
    print(f"  Agent: {chain.agent_role}")
    print(f"  Proposed: Sell $90M NVDA")
    print(f"  Decision: Approved with modification to $50M")
    print(f"  Reasoning Quality: {chain.completeness_score:.1%}")
    print(f"  Review Time: {(updated_chain.review_timestamp - chain.timestamp).total_seconds():.1f}s")
    print(f"  Execution: Successful")

    print("\nLEARNING OPPORTUNITIES:")
    print("  ✓ Reasoning chain captured for audit")
    print("  ✓ Pattern detected: Pre-earnings concentration reduction")
    print("  ✓ Template candidate: High-concentration pre-earnings trades")
    print("  ✓ Future automation: Similar trades with <$50M may auto-approve")

    print("\nCOMPLIANCE READY:")
    print("  ✓ Complete decision rationale documented")
    print("  ✓ Human oversight recorded")
    print("  ✓ Policy checks logged")
    print("  ✓ Execution results tracked")
    print("  ✓ Audit trail immutable")

    # 8. Show database stats
    print_header("Step 8: System Metrics")

    metrics = runtime.get_metrics()
    stats = metrics["summary"]

    print("DATABASE STATS:")
    print(f"  Total decisions: {stats.get('total_decisions', 0)}")
    print(f"  Reviews required: {stats.get('total_reviews', 0)}")
    print(f"  Approved: {stats.get('total_approved', 0)}")
    print(f"  Avg completeness: {(stats.get('avg_completeness', 0) * 100):.1f}%")

    print_header("DEMO COMPLETE")

    print("✅ IntentCore successfully demonstrated:")
    print("   • Reasoning extraction from agent conversations")
    print("   • Governance policy enforcement")
    print("   • Human review workflow")
    print("   • Decision recording and audit trail")
    print("   • Pattern detection for future automation")

    print("\n📊 View results in UI:")
    print("   1. Start API: cd intentcore/ui/backend && python -m uvicorn api:app --reload")
    print("   2. Start UI: cd intentcore/ui/frontend && npm run dev")
    print("   3. Open: http://localhost:3000")

    print("\n💾 Database: demo_intentcore.db")
    print("   • All reasoning chains stored")
    print("   • Ready for pattern analysis")
    print("   • Queryable for compliance")

    return chain


if __name__ == "__main__":
    chain = demo_full_flow()

    print("\n" + "="*80)
    print("Demo completed successfully!")
    print("="*80)
