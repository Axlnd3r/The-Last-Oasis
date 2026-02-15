import { ethers } from "hardhat"

function requireEnv(name: string): string {
  const v = process.env[name]
  if (!v) throw new Error(`Missing env ${name}`)
  return v
}

async function main() {
  const paymentToken = requireEnv("PAYMENT_TOKEN_ADDRESS")
  const entryFee = BigInt(requireEnv("ENTRY_FEE"))
  const worldOracle = requireEnv("WORLD_ORACLE_ADDRESS")

  const PrizePool = await ethers.getContractFactory("PrizePoolContract")
  const prizePool = await PrizePool.deploy(paymentToken, worldOracle)
  await prizePool.waitForDeployment()

  const EntryFee = await ethers.getContractFactory("EntryFeeContract")
  const entryFeeContract = await EntryFee.deploy(paymentToken, entryFee, await prizePool.getAddress())
  await entryFeeContract.waitForDeployment()

  const tx = await prizePool.setEntryFeeContract(await entryFeeContract.getAddress())
  await tx.wait()

  console.log(JSON.stringify({
    prizePool: await prizePool.getAddress(),
    entryFee: await entryFeeContract.getAddress(),
    paymentToken,
    entryFeeAmount: entryFee.toString(),
    worldOracle,
  }, null, 2))
}

main().catch((err) => {
  console.error(err)
  process.exitCode = 1
})
