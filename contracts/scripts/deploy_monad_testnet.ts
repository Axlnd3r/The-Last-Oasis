import { ethers } from "hardhat"

/**
 * Deploy The Last Oasis contracts to Monad Testnet (chainId 10143)
 *
 * Prerequisites:
 *   1. Get MON testnet tokens from faucet: https://faucet.monad.xyz
 *   2. Create contracts/.env with:
 *        MONAD_RPC_URL=https://monad-testnet.drpc.org
 *        DEPLOYER_PRIVATE_KEY=0x<your_private_key>
 *
 * Run:
 *   cd contracts
 *   npx hardhat run scripts/deploy_monad_testnet.ts --network monad
 */

async function main() {
  const [deployer] = await ethers.getSigners()
  const network = await ethers.provider.getNetwork()

  console.log("=== The Last Oasis — Monad Testnet Deployment ===")
  console.log(`Network: chainId=${network.chainId}`)
  console.log(`Deployer: ${deployer.address}`)

  const balance = await ethers.provider.getBalance(deployer.address)
  console.log(`Balance: ${ethers.formatEther(balance)} MON`)

  if (balance === 0n) {
    throw new Error("Deployer has 0 MON. Get testnet tokens from https://faucet.monad.xyz")
  }

  // Step 1: Deploy MockERC20 as payment token (for testnet)
  console.log("\n[1/4] Deploying MockERC20 (testnet payment token)...")
  const Mock = await ethers.getContractFactory("MockERC20")
  const token = await Mock.deploy("LastOasis MON", "loMON", 18)
  await token.waitForDeployment()
  const tokenAddr = await token.getAddress()
  console.log(`  MockERC20 deployed: ${tokenAddr}`)

  // Step 2: Deploy PrizePoolContract
  console.log("[2/4] Deploying PrizePoolContract...")
  const PrizePool = await ethers.getContractFactory("PrizePoolContract")
  const prizePool = await PrizePool.deploy(tokenAddr, deployer.address)
  await prizePool.waitForDeployment()
  const prizePoolAddr = await prizePool.getAddress()
  console.log(`  PrizePoolContract deployed: ${prizePoolAddr}`)

  // Step 3: Deploy EntryFeeContract
  const entryFee = ethers.parseEther("1") // 1 loMON entry fee
  console.log("[3/4] Deploying EntryFeeContract...")
  const EntryFee = await ethers.getContractFactory("EntryFeeContract")
  const entryFeeContract = await EntryFee.deploy(tokenAddr, entryFee, prizePoolAddr)
  await entryFeeContract.waitForDeployment()
  const entryFeeAddr = await entryFeeContract.getAddress()
  console.log(`  EntryFeeContract deployed: ${entryFeeAddr}`)

  // Step 4: Link contracts + mint test tokens + do a test entry
  console.log("[4/4] Linking contracts & test entry...")
  const tx1 = await prizePool.setEntryFeeContract(entryFeeAddr)
  await tx1.wait()
  console.log(`  PrizePool linked to EntryFee: tx=${tx1.hash}`)

  const mintAmount = ethers.parseEther("100")
  const tx2 = await token.mint(deployer.address, mintAmount)
  await tx2.wait()
  console.log(`  Minted 100 loMON: tx=${tx2.hash}`)

  const tx3 = await token.approve(entryFeeAddr, entryFee)
  await tx3.wait()
  console.log(`  Approved EntryFee: tx=${tx3.hash}`)

  const testTxRef = `monad_testnet_${Date.now()}`
  const tx4 = await entryFeeContract.payEntry(testTxRef)
  await tx4.wait()
  console.log(`  Test entry paid: tx=${tx4.hash}`)

  // Verify
  const paid = await entryFeeContract.hasAgentPaid(deployer.address)
  const onChainAgent = await entryFeeContract.getAgentByTxRef(testTxRef)
  const poolBal = await token.balanceOf(prizePoolAddr)

  console.log("\n=== DEPLOYMENT COMPLETE ===")
  const result = {
    chain: "monad_testnet",
    chainId: Number(network.chainId),
    deployer: deployer.address,
    contracts: {
      MockERC20: tokenAddr,
      PrizePoolContract: prizePoolAddr,
      EntryFeeContract: entryFeeAddr,
    },
    testEntry: {
      txRef: testTxRef,
      txHash: tx4.hash,
      paid,
      onChainAgent,
      poolBalance: poolBal.toString(),
    },
    backendEnv: {
      CHAIN_RPC_URL: "https://monad-testnet.drpc.org",
      ENTRY_FEE_CONTRACT_ADDRESS: entryFeeAddr,
    },
    explorer: {
      MockERC20: `https://testnet.monadexplorer.com/address/${tokenAddr}`,
      PrizePool: `https://testnet.monadexplorer.com/address/${prizePoolAddr}`,
      EntryFee: `https://testnet.monadexplorer.com/address/${entryFeeAddr}`,
      TestEntryTx: `https://testnet.monadexplorer.com/tx/${tx4.hash}`,
    },
  }
  console.log(JSON.stringify(result, null, 2))
}

main().catch((err) => {
  console.error(err)
  process.exitCode = 1
})
