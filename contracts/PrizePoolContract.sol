// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract PrizePoolContract is Ownable, ReentrancyGuard {
    IERC20 public paymentToken;
    address public entryFeeContract;
    address public worldOracle;

    enum GamePhase {
        ACTIVE,
        ENDING,
        FINISHED
    }

    GamePhase public currentPhase;

    uint256 public totalDeposited;
    uint256 public finalPrizePool;
    uint256 public gameEndTick;

    address[] public survivors;
    mapping(address => bool) public isSurvivor;
    mapping(address => bool) public hasClaimed;
    mapping(address => uint256) public survivalTicks;

    event FundsReceived(address indexed from, uint256 amount);
    event SurvivorRegistered(address indexed agent, uint256 survivalTicks, uint256 timestamp);
    event PrizeClaimed(address indexed agent, uint256 amount, uint256 timestamp);
    event GamePhaseChanged(GamePhase oldPhase, GamePhase newPhase);
    event GameEnded(uint256 tick, uint256 totalSurvivors, uint256 prizePool);
    event EntryFeeContractUpdated(address indexed oldEntryContract, address indexed newEntryContract);
    event WorldOracleUpdated(address indexed oldOracle, address indexed newOracle);

    error GameNotFinished();
    error NotASurvivor();
    error AlreadyClaimed();
    error NoSurvivors();
    error TransferFailed();
    error Unauthorized();
    error ZeroAddress();
    error InvalidPhase();
    error LengthMismatch();

    modifier onlyOracle() {
        if (msg.sender != worldOracle) revert Unauthorized();
        _;
    }

    modifier onlyEntryContract() {
        if (msg.sender != entryFeeContract) revert Unauthorized();
        _;
    }

    constructor(address _paymentToken, address _worldOracle) Ownable(msg.sender) {
        if (_paymentToken == address(0) || _worldOracle == address(0)) revert ZeroAddress();
        paymentToken = IERC20(_paymentToken);
        worldOracle = _worldOracle;
        currentPhase = GamePhase.ACTIVE;
    }

    function setEntryFeeContract(address newEntryContract) external onlyOwner {
        if (newEntryContract == address(0)) revert ZeroAddress();
        address old = entryFeeContract;
        entryFeeContract = newEntryContract;
        emit EntryFeeContractUpdated(old, newEntryContract);
    }

    function receiveFunds(uint256 amount) external onlyEntryContract {
        totalDeposited += amount;
        emit FundsReceived(msg.sender, amount);
    }

    receive() external payable {
        revert("Use ERC20 transfers only");
    }

    function registerSurvivors(address[] calldata _survivors, uint256[] calldata _survivalTicks, uint256 _gameEndTick)
        external
        onlyOracle
    {
        if (currentPhase != GamePhase.ACTIVE) revert InvalidPhase();
        if (_survivors.length == 0) revert NoSurvivors();
        if (_survivors.length != _survivalTicks.length) revert LengthMismatch();

        GamePhase oldPhase = currentPhase;
        currentPhase = GamePhase.ENDING;
        emit GamePhaseChanged(oldPhase, currentPhase);

        gameEndTick = _gameEndTick;

        for (uint256 i = 0; i < _survivors.length; i++) {
            address survivor = _survivors[i];
            if (!isSurvivor[survivor]) {
                survivors.push(survivor);
                isSurvivor[survivor] = true;
                survivalTicks[survivor] = _survivalTicks[i];
                emit SurvivorRegistered(survivor, _survivalTicks[i], block.timestamp);
            }
        }
    }

    function finalizeGame() external onlyOracle {
        if (currentPhase != GamePhase.ENDING) revert InvalidPhase();

        GamePhase oldPhase = currentPhase;
        currentPhase = GamePhase.FINISHED;
        finalPrizePool = paymentToken.balanceOf(address(this));

        emit GamePhaseChanged(oldPhase, currentPhase);
        emit GameEnded(gameEndTick, survivors.length, finalPrizePool);
    }

    function claimPrize() external nonReentrant {
        if (currentPhase != GamePhase.FINISHED) revert GameNotFinished();
        if (!isSurvivor[msg.sender]) revert NotASurvivor();
        if (hasClaimed[msg.sender]) revert AlreadyClaimed();
        if (survivors.length == 0) revert NoSurvivors();

        hasClaimed[msg.sender] = true;

        uint256 prizeShare = finalPrizePool / survivors.length;
        bool ok = paymentToken.transfer(msg.sender, prizeShare);
        if (!ok) revert TransferFailed();

        emit PrizeClaimed(msg.sender, prizeShare, block.timestamp);
    }

    function getSurvivorCount() external view returns (uint256) {
        return survivors.length;
    }

    function getPrizeShare() external view returns (uint256) {
        if (survivors.length == 0) return 0;
        return finalPrizePool / survivors.length;
    }

    function canClaim(address agent) external view returns (bool) {
        return currentPhase == GamePhase.FINISHED && isSurvivor[agent] && !hasClaimed[agent];
    }

    function setWorldOracle(address newOracle) external onlyOwner {
        if (newOracle == address(0)) revert ZeroAddress();
        address old = worldOracle;
        worldOracle = newOracle;
        emit WorldOracleUpdated(old, newOracle);
    }

    function emergencyWithdraw() external onlyOwner nonReentrant {
        if (currentPhase == GamePhase.FINISHED) revert InvalidPhase();
        uint256 balance = paymentToken.balanceOf(address(this));
        bool ok = paymentToken.transfer(owner(), balance);
        if (!ok) revert TransferFailed();
    }
}
