from __future__ import annotations

import asyncio
from typing import Any


def _require_web3() -> Any:
    try:
        from web3 import Web3
    except Exception as e:
        raise RuntimeError("missing_dependency_web3") from e
    return Web3


_ENTRY_FEE_ABI = [
    {
        "inputs": [{"internalType": "string", "name": "txRef", "type": "string"}],
        "name": "getAgentByTxRef",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function",
    },
    {
        "inputs": [{"internalType": "address", "name": "agent", "type": "address"}],
        "name": "hasAgentPaid",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function",
    },
]


def _verify_entry_sync(rpc_url: str, contract_address: str, tx_ref: str, agent_address: str) -> tuple[bool, str]:
    Web3 = _require_web3()
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise RuntimeError("chain_rpc_unreachable")

    contract = w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=_ENTRY_FEE_ABI)
    normalized_agent = Web3.to_checksum_address(agent_address)

    on_chain_agent = contract.functions.getAgentByTxRef(tx_ref).call()
    if str(on_chain_agent).lower() != str(normalized_agent).lower():
        return False, normalized_agent
    paid = bool(contract.functions.hasAgentPaid(normalized_agent).call())
    return paid, normalized_agent


async def verify_entry_paid(rpc_url: str, contract_address: str, tx_ref: str, agent_address: str) -> tuple[bool, str]:
    return await asyncio.to_thread(_verify_entry_sync, rpc_url, contract_address, tx_ref, agent_address)

