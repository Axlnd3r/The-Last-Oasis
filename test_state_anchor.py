import asyncio
import os
from dotenv import load_dotenv

load_dotenv()

async def test_state_anchor():
    from app.chain.state_anchor import get_state_anchor_service
    
    print("=== Testing State Anchor Service ===\n")
    
    svc = get_state_anchor_service()
    
    if not svc.enabled:
        print("❌ State anchor service not enabled")
        print("Check your .env file:")
        print(f"  CHAIN_RPC_URL: {os.getenv('CHAIN_RPC_URL')}")
        print(f"  STATE_ANCHOR_CONTRACT_ADDRESS: {os.getenv('STATE_ANCHOR_CONTRACT_ADDRESS')}")
        print(f"  ORACLE_PRIVATE_KEY: {'***' if os.getenv('ORACLE_PRIVATE_KEY') else 'NOT SET'}")
        return
    
    print("✓ State anchor service enabled")
    print(f"  RPC: {svc.rpc_url}")
    print(f"  Contract: {svc.contract_address}")
    print(f"  Oracle: {svc.oracle_account.address}\n")
    
    # Check anchor count
    count = await svc.get_anchor_count()
    print(f"Total anchors on-chain: {count}")
    
    if count > 0:
        latest = await svc.get_latest_anchor()
        print(f"\nLatest anchor:")
        print(f"  Tick: {latest['tick']}")
        print(f"  Hash: {latest['state_hash']}")
        print(f"  Alive Agents: {latest['alive_agents']}")
        print(f"  Timestamp: {latest['timestamp']}")
    
    # Test submission (tick 50 example)
    print("\n=== Testing Anchor Submission ===")
    test_hash = "a" * 64  # dummy hash
    success = await svc.anchor_state(50, test_hash, 5)
    
    if success:
        print("✓ Test anchor submitted successfully!")
    else:
        print("ℹ Anchor submission skipped (might already exist)")

asyncio.run(test_state_anchor())
