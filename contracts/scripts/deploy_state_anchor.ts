import { ethers } from "hardhat";

async function main() {
  const [deployer] = await ethers.getSigners();
  
  // Ganti dengan Oracle Address dari Step 1
  const ORACLE_ADDRESS = "0xF0699cA0c464C7100F316C4a76e6f82E53e7840a";
  
  console.log("Deploying StateAnchorContract...");
  console.log("Oracle address:", ORACLE_ADDRESS);
  
  const StateAnchor = await ethers.getContractFactory("StateAnchorContract");
  const stateAnchor = await StateAnchor.deploy(ORACLE_ADDRESS);
  await stateAnchor.waitForDeployment();
  
  const address = await stateAnchor.getAddress();
  console.log("StateAnchorContract deployed to:", address);
  
  // Verify oracle is set correctly
  const oracle = await stateAnchor.oracle();
  console.log("Verified oracle address:", oracle);
  
  console.log("\n=== Add to .env ===");
  console.log(`STATE_ANCHOR_CONTRACT_ADDRESS=${address}`);
  console.log(`ORACLE_ADDRESS=${ORACLE_ADDRESS}`);
  console.log(`ORACLE_PRIVATE_KEY=0xfb552110c893087d33681bf59d10fb0c8134c59405c1290e51474ce4668f7bda`);
  
  console.log("\n=== Explorer ===");
  console.log(`https://testnet.monadexplorer.com/address/${address}`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
