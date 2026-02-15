import { ethers } from "hardhat"

async function main() {
  const [deployer] = await ethers.getSigners()

  const decimals = 6n
  const entryFee = 10_000_000n
  const txRef = `demo_local_${Date.now()}`

  const Mock = await ethers.getContractFactory("MockERC20")
  const token = await Mock.deploy("MockUSDC", "mUSDC", Number(decimals))
  await token.waitForDeployment()

  const PrizePool = await ethers.getContractFactory("PrizePoolContract")
  const prizePool = await PrizePool.deploy(await token.getAddress(), deployer.address)
  await prizePool.waitForDeployment()

  const EntryFee = await ethers.getContractFactory("EntryFeeContract")
  const entryFeeContract = await EntryFee.deploy(await token.getAddress(), entryFee, await prizePool.getAddress())
  await entryFeeContract.waitForDeployment()

  await (await prizePool.setEntryFeeContract(await entryFeeContract.getAddress())).wait()

  await (await token.mint(deployer.address, entryFee * 3n)).wait()
  await (await token.approve(await entryFeeContract.getAddress(), entryFee)).wait()
  await (await entryFeeContract.payEntry(txRef)).wait()

  const onChainAgent = await entryFeeContract.getAgentByTxRef(txRef)
  const paid = await entryFeeContract.hasAgentPaid(deployer.address)
  const poolBalance = await token.balanceOf(await prizePool.getAddress())

  console.log(
    JSON.stringify(
      {
        chain: "localhost_hardhat",
        txRef,
        agentAddress: deployer.address,
        token: await token.getAddress(),
        entryFee: entryFee.toString(),
        entryFeeContract: await entryFeeContract.getAddress(),
        prizePool: await prizePool.getAddress(),
        onChainAgent,
        paid,
        poolBalance: poolBalance.toString(),
        backendEnv: {
          CHAIN_RPC_URL: "http://127.0.0.1:8545",
          ENTRY_FEE_CONTRACT_ADDRESS: await entryFeeContract.getAddress(),
        },
      },
      null,
      2
    )
  )
}

main().catch((err) => {
  console.error(err)
  process.exitCode = 1
})

