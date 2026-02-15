from __future__ import annotations

import os


class Settings:
    def __init__(self) -> None:
        self.db_path = os.environ.get("DB_PATH", "last_oasis.sqlite3")
        self.tick_interval_ms = int(os.environ.get("TICK_INTERVAL_MS", "1200"))
        self.snapshot_every_ticks = int(os.environ.get("SNAPSHOT_EVERY_TICKS", "10"))
        self.map_size = int(os.environ.get("MAP_SIZE", "20"))
        self.obs_radius = int(os.environ.get("OBS_RADIUS", "3"))
        self.entry_price_asset = os.environ.get("ENTRY_PRICE_ASSET", "USDC")
        self.entry_price_amount = os.environ.get("ENTRY_PRICE_AMOUNT", "1.0")
        self.entry_demo_secret = os.environ.get("ENTRY_DEMO_SECRET", "demo")
        self.chain_rpc_url = os.environ.get("CHAIN_RPC_URL") or os.environ.get("MONAD_RPC_URL")
        self.entry_fee_contract_address = os.environ.get("ENTRY_FEE_CONTRACT_ADDRESS")


settings = Settings()
