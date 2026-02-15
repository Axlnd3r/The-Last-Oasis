# The Last Oasis

### Monad Hackathon 2026 — World Model Agent Track

> A persistent virtual desert world where AI agents pay MON tokens to enter, then must explore, trade, fight, and adapt to survive as the oasis slowly dies.

---

## What is The Last Oasis?

The Last Oasis is a **stateful virtual world simulation** built for the Monad Hackathon 2026 Agent Track. It creates a 20x20 desert environment centered around a dying oasis, where autonomous AI agents must cooperate and compete to survive.

The world **degrades over time** — tiles lose resources, hazards spread, and the desert expands inward toward the oasis. Agents that enter must make real-time decisions: gather scarce resources, trade with allies, fight enemies for loot, or retreat to safety. The last agents standing share the prize pool.

**Core concept**: The desert always wins. The question is how long your agent can delay the inevitable.

---

## 🔥 Killer Features (NEW)

### 1. Reputation & Alliance Layer

Agents now have **trust scores** (0-100) that track cooperative vs. hostile behavior:

- **Trust Score**: Starts at 100 (neutral). Increases with successful trades (+0.5 to +5 per trade based on value). Decreases with combat (-3) and **betrayals (-25)**.
- **Betrayal Detection**: If an agent attacks a recent trade partner (within last 10 ticks), it's flagged as a **betrayal** — heavily penalized with -25 trust and logged permanently.
- **Trade History**: Every agent tracks their last 50 trades with partners, amounts, and values. Visible in agent cards and tooltips.
- **Emergent Politics**: Low-trust agents become pariahs. High-trust agents attract cooperation. Agents can form implicit alliances through repeated trade patterns.
- **Reputation Decay**: Scores slowly drift back toward 100 over time (±0.5 every 10 ticks), allowing redemption.

**Why it matters**: Transforms The Last Oasis from pure resource competition into a **social simulation** where reputation has real consequences. Agents must balance short-term gains (betrayal loot) against long-term cooperation (trade networks).

### 2. Scarcity-Based Dynamic Pricing

Resource value changes in real-time based on **supply and demand**:

- **Market Price Formula**: `price = base × (1 + scarcity×2.5) × (1 + degradation×1.5)`
  - Base price: 1.0
  - Scarcity: `1 - (total_resources / max_theoretical_resources)`
  - Degradation: average world degradation (0-1)
- **Price Range**: 1.0x → 5.0x as the oasis dies
- **Trade Value**: Each trade's value is calculated as `amount × market_price` and recorded in trade history
- **Economic Collapse**: As degradation increases and resources vanish, prices spike exponentially. Early-game resources become worthless hoards. Late-game scarcity creates a true survival economy.

**Why it matters**: Static resource trading is boring. **Dynamic pricing creates emergent market behavior** — resource hoarding, price speculation, strategic timing of trades, and desperate late-game bartering when prices hit 5x.

### 3. On-Chain State Anchoring

World state hashes committed to Monad blockchain every 50 ticks for **oracle verification**:

- **StateAnchorContract**: Solidity contract that stores `(tick, stateHash, aliveAgents, timestamp)` tuples
- **Deterministic Hashing**: SHA256 of `{tick, agent_states, total_degradation, total_resources}` — fully reproducible
- **Trustless Verification**: Anyone can verify that the oracle (backend) isn't cheating by comparing claimed state against on-chain anchors
- **Automated Submission**: Backend auto-submits anchors via Web3.py every 50 ticks using oracle private key
- **View Functions**: `verifyStateHash(tick, hash)`, `getLatestAnchor()`, `getAnchorCount()`

**Why it matters**: Most "on-chain games" just use blockchain for tokens. **We anchor the actual game state**, making the world simulation verifiable and tamper-proof. Judges can audit the oracle's honesty. Players can prove their survival claims.

---

## MVP Compliance — World Agent Track

### Objective: *"Build an agent that simulates a persistent virtual world where other agents can enter, interact, and participate in activities by paying an entry fee in MON tokens."*

| Requirement | Status | Implementation |
|-------------|--------|----------------|
| **Stateful world environment with defined rules, locations, and mechanics** | Done | 20x20 grid with degradation, hazard, and resource systems. 7 named zones (Oasis Heart, Dune Wastes, Ancient Ruins, Trading Post, Scorched Plains, Palm Grove, Bone Fields). Tick-based simulation at 1.2s intervals with event sourcing and SQLite persistence. |
| **MON token-gated entry system** | Done | `EntryFeeContract.sol` deployed on Monad — agents call `payEntry(txRef)` to transfer ERC20 tokens. Backend verifies payment on-chain via `hasAgentPaid()` and `getAgentByTxRef()` before granting world access. Demo mode available with `demo_` prefix for testing. |
| **API/interface for external agents to query world state and submit actions** | Done | Full REST API: `GET /world/observation` (partial view, radius 3), `POST /world/action` (submit moves), `GET /world/status`, `GET /world/leaderboard`, `GET /world/grid`. Agent SDK provided in `agents/sdk.py`. |
| **Persistent world state that evolves based on agent interactions** | Done | Event sourcing architecture — every action generates events stored in SQLite. World snapshots every 10 ticks. State reconstructed from snapshots + event replay on restart. World evolves: degradation +0.006/tick, hazard scales with degradation, resources drain over time. |
| **Meaningful responses to agent actions that affect world state** | Done | 6 actions (move, gather, rest, trade, attack) each modify world state and produce observable effects. Combat deals 3 HP damage + 50% loot on kill. Trade transfers resources between agents. Gathering depletes tile resources. |

### Success Criteria

| Criteria | Status | Evidence |
|----------|--------|----------|
| **At least 3 external agents can enter and interact** | Done | 5 agents run simultaneously (Random_A, Random_B, Belief_A, Trader_A, DQN_Sim). Verified: 6+ COMBAT_HIT events and TRADE_COMPLETED events within ~60 ticks. |
| **World state persists and changes logically** | Done | SQLite event sourcing with snapshot/replay. Degradation increases, resources deplete, agents take hazard damage, dead agents stay dead until world reset. |
| **Clear documentation of rules, entry costs, and protocols** | Done | This README + inline API docs. Entry cost: 1 USDC equivalent in MON tokens via x402 protocol. |
| **Emergent behavior from multi-agent interaction** | Done | Agents cluster near the oasis center, compete for resources, form implicit trade partnerships, and DQN agent learns to avoid hazards over time. |

### Bonus Points

| Bonus | Status | Implementation |
|-------|--------|----------------|
| **Economic system where agents earn back resources** | Done | Agents gather resources from tiles, trade with each other, and loot 50% of killed agents' inventory. Survivors split the prize pool on-chain. |
| **Complex world mechanics** | Done | Trade system, combat with loot, hazard damage scaling, resource depletion, 7 distinct zones with different characteristics, partial observability (fog of war). |
| **Visualization dashboard** | Done | Full pixel-art dashboard with hand-drawn map, zone hotspots with popup images, pixel agent sprites, live event feed, DQN learning tracker, collapsible sidebar panels. |

---

## Features

### World Engine
- **20x20 grid** with tile-level degradation, hazard, and resource tracking
- **Non-stationary environment**: degradation +0.006/tick, hazards scale with degradation, resources drain
- **7 named zones**: each with unique characteristics (safe, danger, hazard)
- **Tick-based simulation** at 1.2 second intervals
- **Event sourcing + SQLite snapshots** for full state persistence and replay
- **🔥 Dynamic market pricing**: Resource value scales with scarcity (1.0x → 5.0x)
- **🔥 State anchoring**: World hash committed to blockchain every 50 ticks for oracle verification

### Agent System
- **6 actions**: move (4 directions), gather, rest, trade, attack
- **Partial observability**: agents see only within radius 3 tiles
- **4 AI agent types**:
  - **Random** — Wanderer with sword, explores and attacks adjacent enemies
  - **Belief-Bandit** — Cautious explorer with shield, avoids hazards, trades resources to weak allies
  - **Trader** — Resource broker with coin bag, prioritizes trade and resource gathering
  - **DQN (Deep Q-Learning)** — Neural network agent that scores all actions and picks the best, learns from mistakes over time
- **Combat system**: 3 HP damage, 1 HP stamina cost, 50% loot on kill
- **🔥 Reputation system**: Trust scores (0-100), betrayal detection (-25 penalty), trade history tracking
- **Trade system**: Value-based resource transfer with market price calculation

### Token-Gated Entry (Monad Integration)
- **x402 protocol flow**: `POST /entry/quote` → payment → `POST /entry/confirm`
- **On-chain verification**: backend calls `hasAgentPaid()` and `getAgentByTxRef()` on EntryFeeContract
- **Demo mode**: `demo_` prefix for testing without testnet tokens
- **Prize distribution**: survivors claim equal shares from PrizePoolContract

### Dashboard
- **Hand-drawn pixel art map** as world background (OasisMAP.png)
- **7 clickable zone hotspots** with glowing markers and popup images
- **Pixel art agent sprites** (robed figures with type-specific accessories)
- **Live event feed** with combat, trade, entry, death events
- **DQN learning panel** with epsilon decay, reward chart, mistake log
- **Agent sidebar** with HP bars, resource counts, scores
- **Tooltip** showing tile data and agent info on hover
- **Landing page** with features, zones, and how-to-play sections
- **CRT scanline effect** for retro aesthetic

---

## Monad Smart Contract Integration

Four Solidity contracts deployed on Monad testnet:

### 1. EntryFeeContract.sol
**Purpose**: Token-gated entry gateway for the world.

```solidity
function payEntry(string calldata txRef) external nonReentrant
function hasAgentPaid(address agent) external view returns (bool)
function getAgentByTxRef(string calldata txRef) external view returns (address)
```

- Agents call `payEntry(txRef)` to pay the ERC20 entry fee
- Tokens are automatically forwarded to the PrizePoolContract
- Backend verifies payment via `hasAgentPaid()` before granting world access
- Each `txRef` is unique and maps to exactly one agent address
- Emits `EntryPaid` event with agent address, txRef, amount, and timestamp

### 2. PrizePoolContract.sol
**Purpose**: Collects entry fees and distributes prizes to survivors.

```solidity
function receiveFunds(uint256 amount) external onlyEntryContract
function registerSurvivors(address[] calldata, uint256[] calldata, uint256) external onlyOracle
function finalizeGame() external onlyOracle
function claimPrize() external nonReentrant
```

- **Game phases**: ACTIVE → ENDING → FINISHED
- World oracle (backend) calls `registerSurvivors()` with surviving agent addresses and their survival tick counts
- After `finalizeGame()`, each survivor can call `claimPrize()` to receive an equal share
- Includes emergency withdrawal for contract owner
- Reentrancy-guarded for all token transfers

### 3. MockERC20.sol
**Purpose**: Test ERC20 token for local/testnet development.

### 4. StateAnchorContract.sol
**Purpose**: 🔥 Anchors world state hashes on-chain every 50 ticks for oracle verification.

```solidity
function anchorState(uint256 tick, bytes32 stateHash, uint256 aliveAgents) external onlyOracle
function verifyStateHash(uint256 tick, bytes32 stateHash) external view returns (bool)
function getLatestAnchor() external view returns (StateAnchor memory)
function getAnchorCount() external view returns (uint256)
```

- **Trustless Verification**: Anyone can verify that the oracle (backend) isn't manipulating game state
- **State Anchors**: Stores `(tick, stateHash, aliveAgents, timestamp, submittedBy)` tuples on-chain
- **Deterministic Hashing**: Backend computes SHA256 of `{tick, agent_states, total_degradation, total_resources}`
- **Automated Submission**: Backend calls `anchorState()` every 50 ticks via Web3.py
- **Proof of Honesty**: Judges can audit state progression and verify oracle integrity
- **Replay Protection**: Each tick can only be anchored once (prevents re-anchoring with different hashes)

**Implementation**: `app/chain/state_anchor.py` — Web3.py service that auto-submits state hashes when `STATE_ANCHORED` events are emitted.

### On-Chain Verification Flow

```
Agent → payEntry(txRef) → EntryFeeContract → PrizePoolContract
                                    ↓
                          Backend verifies via RPC
                                    ↓
                    hasAgentPaid(agent) == true?
                    getAgentByTxRef(txRef) == agent?
                                    ↓
                          Agent enters the world
```

The verification is implemented in `app/chain/entry_fee.py` using Web3.py to call view functions on the deployed EntryFeeContract.

---

## Architecture

```
┌───────────────────────────────────────────────────────┐
│  Monad Blockchain                                      │
│  ┌─────────────────┐  ┌───────────────────┐           │
│  │ EntryFeeContract │─▶│ PrizePoolContract │           │
│  │ payEntry(txRef)  │  │ claimPrize()      │           │
│  └────────┬────────┘  └───────────────────┘           │
└───────────┼───────────────────────────────────────────┘
            │ verify via RPC (Web3.py)
┌───────────▼───────────────────────────────────────────┐
│  FastAPI Backend                                       │
│  ┌──────────┐ ┌────────────┐ ┌────────────┐          │
│  │ Entry API │ │ World API  │ │ Admin API  │          │
│  │ /entry/* │ │ /world/*   │ │ /admin/*   │          │
│  └──────────┘ └──────┬─────┘ └────────────┘          │
│                      │                                 │
│  ┌───────────────────▼───────────────────┐            │
│  │ WorldState (20x20 grid, tick loop)    │            │
│  │ Event Sourcing + SQLite Snapshots     │            │
│  └───────────────────────────────────────┘            │
│                      │                                 │
│  ┌───────────────────▼───────────────────┐            │
│  │ Dashboard (pixel art + zone hotspots) │            │
│  └───────────────────────────────────────┘            │
└───────────────────────────────────────────────────────┘
            ▲          ▲          ▲          ▲
┌───────────┴──┐ ┌─────┴────┐ ┌──┴───────┐ ┌┴──────────┐
│ Random Agent │ │ Belief   │ │ Trader   │ │ DQN Agent │
│ (wanderer)   │ │ (bandit) │ │ (broker) │ │ (learner) │
└──────────────┘ └──────────┘ └──────────┘ └───────────┘
```

---

## Project Structure

```
app/
├── main.py              # FastAPI app + tick loop + static file serving
├── settings.py          # Environment configuration
├── db.py                # SQLite event sourcing + snapshots
├── api/routes.py        # All REST endpoints (entry, world, admin)
├── world/
│   ├── engine.py        # WorldState, AgentState, action processing
│   ├── rules.py         # Degradation, hazard damage, resource mechanics
│   └── snapshot.py      # State persistence + replay from events
├── chain/
│   └── entry_fee.py     # On-chain payment verification via Web3.py
└── dashboard/
    ├── index.html       # Landing page + dashboard UI
    └── app.js           # Map renderer, agent sprites, zone system

Assets/                   # Hand-drawn pixel art images
├── OasisMAP.png         # World map background
├── Oasisheart.png       # Zone: The Oasis Heart
├── Dunewastes.png       # Zone: Dune Wastes
├── ancient_ruins.png    # Zone: Ancient Ruins
├── tradingpost.png      # Zone: Trading Post
├── scorchedplans.png    # Zone: Scorched Plains
├── bonefields.png       # Zone: Bone Fields
└── TheOasisHeartAfterClick.png

agents/
├── sdk.py               # Python client SDK for agents
├── agent_random.py      # Random exploration agent
├── agent_belief_bandit.py # Cautious belief-based explorer
├── agent_trader.py      # Resource trading agent
└── agent_dqn.py         # Deep Q-Learning agent

run_agents.py            # Multi-agent launcher (all 4 types)

contracts/
├── src/
│   ├── EntryFeeContract.sol   # ERC20 payment + tx_ref tracking
│   ├── PrizePoolContract.sol  # Prize distribution + game phases
│   └── MockERC20.sol          # Test token for development
├── scripts/
│   ├── deploy_monad_testnet.ts
│   ├── deploy.ts
│   └── smoke_local.ts
└── hardhat.config.ts
```

---

## Quick Start

### 1. Install & Run Server

```bash
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### 2. Open Dashboard

Visit http://127.0.0.1:8000 → Click **START ADVENTURE**

### 3. Launch Agents

```bash
.venv/Scripts/python run_agents.py 5
```

This launches 5 agents (Random_A, Random_B, Belief_A, Trader_A, DQN_Sim) that autonomously enter and interact with the world.

### 4. Deploy Contracts (Optional — Monad Testnet)

```bash
cd contracts
npm install
cp .env.example .env   # Add MONAD_RPC_URL + DEPLOYER_PRIVATE_KEY
npx hardhat run scripts/deploy_monad_testnet.ts --network monad
```

Then connect backend to on-chain:
```bash
export CHAIN_RPC_URL=https://monad-testnet.drpc.org
export ENTRY_FEE_CONTRACT_ADDRESS=<from deploy output>
python -m uvicorn app.main:app --port 8000
```

---

## API Reference

### Entry Gate (x402 Protocol)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/entry/quote` | POST | Get entry fee info (asset, amount, payment instructions) |
| `/entry/confirm` | POST | Confirm payment with `tx_ref`, receive `agent_id` + `api_key` |

**Demo mode**: `tx_ref` starts with `demo_` — no blockchain required.
**On-chain mode**: Set `CHAIN_RPC_URL` env var — backend verifies payment on EntryFeeContract.

### World API

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/world/observation` | GET | `X-AGENT-TOKEN` | Partial view (radius 3 tiles + nearby/all agents + market_price) |
| `/world/action` | POST | `X-AGENT-TOKEN` | Submit action for next tick |
| `/world/status` | GET | - | Tick, alive count, avg degradation |
| `/world/leaderboard` | GET | - | Top agents by score |
| `/world/grid` | GET | - | Full grid + all agents (includes trust_score, betrayals) |
| `/world/market` | GET | - | 🔥 Market price, total resources, avg degradation, trade count |
| `/world/reputation` | GET | - | 🔥 Reputation leaderboard (trust scores, betrayals, trade counts) |

### Agent Actions

```json
{"type": "move", "dx": 1, "dy": 0}
{"type": "gather"}
{"type": "rest"}
{"type": "trade", "target": "<agent_id>", "amount": 5}
{"type": "attack", "target": "<agent_id>"}
```

---

## What Makes The Last Oasis Different

1. **The world fights back** — Unlike static environments, The Last Oasis degrades every tick. Agents can't just sit and accumulate — they must constantly adapt to a shrinking habitable zone.

2. **🔥 Reputation-driven emergent politics** — Trust scores (0-100) track every agent's cooperation vs. betrayal history. Attacking recent trade partners triggers -25 trust penalties. Low-trust agents become pariahs. High-trust agents attract alliances. Agents must choose: short-term betrayal gains or long-term cooperation networks.

3. **🔥 Living economy with dynamic pricing** — Resource value scales 1x→5x based on real-time scarcity and degradation. Early-game hoarding becomes worthless. Late-game resources command extreme prices. Trade timing becomes strategic. Economic collapse mirrors environmental collapse.

4. **🔥 Verifiable on-chain state anchoring** — World state hashes committed to Monad blockchain every 50 ticks. Anyone can verify oracle honesty. Judges can audit state progression. Surviving agents can cryptographically prove their achievements. Most "on-chain games" just tokenize rewards — we anchor the entire simulation.

5. **Full on-chain integration** — Not just a simulation — actual MON token payment via smart contracts, on-chain verification of entry, and on-chain prize distribution to surviving agents.

6. **4 distinct AI strategies** — Each agent type demonstrates a different approach to survival, from random exploration to neural network learning, showcasing the richness of the environment.

7. **Production-quality dashboard** — Hand-drawn pixel art world map with interactive zones, animated agent sprites, live event feed, DQN learning visualization, reputation tracking, and market price ticker — not just a heatmap grid.

8. **Complete game lifecycle** — From world genesis to agent entry, exploration, conflict, survival endgame, and on-chain prize finalization — the full loop is implemented.

---

## Event Types

All state changes are logged as events in SQLite:

| Event | Description |
|-------|-------------|
| `AGENT_ENTERED` | Agent paid and joined the world |
| `AGENT_MOVED` | Agent moved to new tile |
| `AGENT_GATHERED` | Agent collected resources from tile |
| `AGENT_RESTED` | Agent recovered HP |
| `TRADE_COMPLETED` | Resources transferred between agents (includes market_price and trade_value) |
| `COMBAT_HIT` | Agent attacked another (3 dmg, includes is_betrayal flag) |
| `COMBAT_KILL` | Agent killed another (50% loot) |
| `AGENT_DAMAGED` | Agent took hazard damage |
| `AGENT_DIED` | Agent HP reached 0 |
| `REPUTATION_CHANGED` | 🔥 Agent trust score updated (trade cooperation, combat, betrayal) |
| `BETRAYAL_DETECTED` | 🔥 Agent attacked recent trade partner (-25 trust penalty) |
| `MARKET_PRICE_UPDATED` | 🔥 Resource market price changed based on scarcity/degradation |
| `STATE_ANCHORED` | 🔥 World state hash committed to blockchain (every 50 ticks) |
| `DQN_LOG` | DQN training metrics reported |
| `GAME_FINALIZED` | Game ended, survivors registered |

---

## License

Built for the Monad Hackathon 2026 — World Model Agent Track.
