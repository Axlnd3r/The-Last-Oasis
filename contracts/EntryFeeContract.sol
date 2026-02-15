// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface IPrizePool {
    function receiveFunds(uint256 amount) external;
}

contract EntryFeeContract is Ownable, ReentrancyGuard {
    IERC20 public paymentToken;
    uint256 public entryFee;
    address public prizePool;

    mapping(address => bool) public hasPaid;
    mapping(string => address) public txRefToAgent;

    uint256 public totalAgentsEntered;

    event EntryPaid(address indexed agent, string txRef, uint256 amount, uint256 timestamp);
    event EntryFeeUpdated(uint256 oldFee, uint256 newFee);
    event PaymentTokenUpdated(address indexed oldToken, address indexed newToken);
    event PrizePoolUpdated(address indexed oldPool, address indexed newPool);

    error AlreadyPaid();
    error TransferFailed();
    error InvalidTxRef();
    error TxRefAlreadyUsed();
    error ZeroAddress();

    constructor(address _paymentToken, uint256 _entryFee, address _prizePool) Ownable(msg.sender) {
        if (_paymentToken == address(0) || _prizePool == address(0)) revert ZeroAddress();
        paymentToken = IERC20(_paymentToken);
        entryFee = _entryFee;
        prizePool = _prizePool;
    }

    function payEntry(string calldata txRef) external nonReentrant {
        if (hasPaid[msg.sender]) revert AlreadyPaid();
        if (bytes(txRef).length == 0) revert InvalidTxRef();
        if (txRefToAgent[txRef] != address(0)) revert TxRefAlreadyUsed();

        hasPaid[msg.sender] = true;
        txRefToAgent[txRef] = msg.sender;
        totalAgentsEntered += 1;

        bool ok = paymentToken.transferFrom(msg.sender, address(this), entryFee);
        if (!ok) revert TransferFailed();

        ok = paymentToken.transfer(prizePool, entryFee);
        if (!ok) revert TransferFailed();

        IPrizePool(prizePool).receiveFunds(entryFee);

        emit EntryPaid(msg.sender, txRef, entryFee, block.timestamp);
    }

    function hasAgentPaid(address agent) external view returns (bool) {
        return hasPaid[agent];
    }

    function getAgentByTxRef(string calldata txRef) external view returns (address) {
        return txRefToAgent[txRef];
    }

    function setEntryFee(uint256 newFee) external onlyOwner {
        uint256 oldFee = entryFee;
        entryFee = newFee;
        emit EntryFeeUpdated(oldFee, newFee);
    }

    function setPaymentToken(address newToken) external onlyOwner {
        if (newToken == address(0)) revert ZeroAddress();
        address oldToken = address(paymentToken);
        paymentToken = IERC20(newToken);
        emit PaymentTokenUpdated(oldToken, newToken);
    }

    function setPrizePool(address newPrizePool) external onlyOwner {
        if (newPrizePool == address(0)) revert ZeroAddress();
        address oldPool = prizePool;
        prizePool = newPrizePool;
        emit PrizePoolUpdated(oldPool, newPrizePool);
    }
}
