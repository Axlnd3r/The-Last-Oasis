import { fileURLToPath } from "node:url"

export const ZONES = [
  { id: 1, name: "The Wasteland", resources: {} },
  { id: 2, name: "The Dustfields", resources: { BASIC_SUPPLIES: 120 } },
  { id: 3, name: "The Ruins", resources: { SHELTER_MATERIALS: 80 } },
  { id: 4, name: "The Marshlands", resources: { FOOD_WATER: 120 } },
  { id: 5, name: "The Crystal Caves", resources: { CRYSTALS: 70 } },
  { id: 6, name: "The Greenwood", resources: { RARE_RESOURCES: 30 } },
  {
    id: 7,
    name: "The Oasis",
    resources: {
      BASIC_SUPPLIES: 200,
      SHELTER_MATERIALS: 120,
      FOOD_WATER: 220,
      CRYSTALS: 120,
      RARE_RESOURCES: 60
    }
  }
]

export const DEFAULT_DECAY_INTERVAL_MS =
  Number(process.env.DECAY_INTERVAL_MS ?? "") || 2 * 60_000

export const WORLD_STATE_FILE =
  process.env.WORLD_STATE_FILE ||
  fileURLToPath(new URL("../data/world-state.json", import.meta.url))

export const DEMO_ENTRY_FEE = {
  asset: process.env.ENTRY_FEE_ASSET || "USDC",
  amount: process.env.ENTRY_FEE_AMOUNT || "1.0"
}

export const API_PREFIX = "/api/world"

