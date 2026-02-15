"""
On-chain state anchoring for The Last Oasis

Submits world state hashes every 50 ticks to StateAnchorContract for verification
"""
import os
from typing import Optional
from web3 import Web3
from web3.exceptions import ContractLogicError


class StateAnchorService:
    def __init__(self):
        self.rpc_url = os.getenv("CHAIN_RPC_URL")
        self.contract_address = os.getenv("STATE_ANCHOR_CONTRACT_ADDRESS")
        self.oracle_private_key = os.getenv("ORACLE_PRIVATE_KEY")

        self.enabled = False
        if self.rpc_url and self.contract_address and self.oracle_private_key:
            try:
                self.w3 = Web3(Web3.HTTPProvider(self.rpc_url))
                if self.w3.is_connected():
                    self.enabled = True
                    print(f"✓ StateAnchor connected to {self.rpc_url}")
            except Exception as e:
                print(f"✗ StateAnchor connection failed: {e}")

        if self.enabled:
            # Contract ABI (minimal interface)
            self.contract_abi = [
                {
                    "inputs": [
                        {"internalType": "uint256", "name": "tick", "type": "uint256"},
                        {"internalType": "bytes32", "name": "stateHash", "type": "bytes32"},
                        {"internalType": "uint256", "name": "aliveAgents", "type": "uint256"}
                    ],
                    "name": "anchorState",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [
                        {"internalType": "uint256", "name": "tick", "type": "uint256"},
                        {"internalType": "bytes32", "name": "stateHash", "type": "bytes32"}
                    ],
                    "name": "verifyStateHash",
                    "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "getLatestAnchor",
                    "outputs": [
                        {
                            "components": [
                                {"internalType": "uint256", "name": "tick", "type": "uint256"},
                                {"internalType": "bytes32", "name": "stateHash", "type": "bytes32"},
                                {"internalType": "uint256", "name": "aliveAgents", "type": "uint256"},
                                {"internalType": "uint256", "name": "timestamp", "type": "uint256"},
                                {"internalType": "address", "name": "submittedBy", "type": "address"}
                            ],
                            "internalType": "struct StateAnchorContract.StateAnchor",
                            "name": "",
                            "type": "tuple"
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function"
                },
                {
                    "inputs": [],
                    "name": "getAnchorCount",
                    "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
                    "stateMutability": "view",
                    "type": "function"
                }
            ]

            self.contract = self.w3.eth.contract(
                address=Web3.to_checksum_address(self.contract_address),
                abi=self.contract_abi
            )

            # Get oracle account from private key
            self.oracle_account = self.w3.eth.account.from_key(self.oracle_private_key)

    async def anchor_state(self, tick: int, state_hash: str, alive_agents: int) -> bool:
        """
        Submit state anchor to on-chain contract

        Args:
            tick: World tick number (must be multiple of 50)
            state_hash: SHA256 hash of world state (hex string)
            alive_agents: Number of alive agents

        Returns:
            bool: True if successfully anchored, False otherwise
        """
        if not self.enabled:
            return False

        if tick % 50 != 0:
            print(f"✗ StateAnchor: tick {tick} not multiple of 50, skipping")
            return False

        try:
            # Convert hex hash to bytes32
            state_hash_bytes = bytes.fromhex(state_hash.replace("0x", ""))

            # Build transaction
            nonce = self.w3.eth.get_transaction_count(self.oracle_account.address)

            tx = self.contract.functions.anchorState(
                tick,
                state_hash_bytes,
                alive_agents
            ).build_transaction({
                'from': self.oracle_account.address,
                'nonce': nonce,
                'gas': 200000,
                'maxFeePerGas': self.w3.to_wei('50', 'gwei'),
                'maxPriorityFeePerGas': self.w3.to_wei('2', 'gwei'),
            })

            # Sign and send
            signed_tx = self.w3.eth.account.sign_transaction(tx, self.oracle_private_key)
            tx_hash = self.w3.eth.send_raw_transaction(signed_tx.raw_transaction)

            # Wait for receipt
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)

            if receipt['status'] == 1:
                print(f"✓ StateAnchor: tick {tick} anchored on-chain (tx: {tx_hash.hex()[:10]}...)")
                return True
            else:
                print(f"✗ StateAnchor: transaction reverted for tick {tick}")
                return False

        except ContractLogicError as e:
            print(f"✗ StateAnchor contract error: {e}")
            return False
        except Exception as e:
            print(f"✗ StateAnchor submission failed: {e}")
            return False

    async def verify_state_hash(self, tick: int, state_hash: str) -> bool:
        """
        Verify a state hash against on-chain anchor

        Args:
            tick: World tick number
            state_hash: SHA256 hash to verify

        Returns:
            bool: True if hash matches on-chain anchor
        """
        if not self.enabled:
            return False

        try:
            state_hash_bytes = bytes.fromhex(state_hash.replace("0x", ""))
            result = self.contract.functions.verifyStateHash(tick, state_hash_bytes).call()
            return bool(result)
        except Exception as e:
            print(f"✗ StateAnchor verification failed: {e}")
            return False

    async def get_anchor_count(self) -> int:
        """Get total number of anchored states"""
        if not self.enabled:
            return 0

        try:
            count = self.contract.functions.getAnchorCount().call()
            return int(count)
        except Exception:
            return 0

    async def get_latest_anchor(self) -> Optional[dict]:
        """Get the most recent state anchor from chain"""
        if not self.enabled:
            return None

        try:
            anchor = self.contract.functions.getLatestAnchor().call()
            return {
                "tick": int(anchor[0]),
                "state_hash": "0x" + anchor[1].hex(),
                "alive_agents": int(anchor[2]),
                "timestamp": int(anchor[3]),
                "submitted_by": anchor[4],
            }
        except Exception as e:
            print(f"✗ Failed to get latest anchor: {e}")
            return None


# Global singleton
_state_anchor_service: Optional[StateAnchorService] = None


def get_state_anchor_service() -> StateAnchorService:
    """Get or create the global state anchor service"""
    global _state_anchor_service
    if _state_anchor_service is None:
        _state_anchor_service = StateAnchorService()
    return _state_anchor_service
