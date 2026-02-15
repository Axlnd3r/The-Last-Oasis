// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

/**
 * @title StateAnchorContract
 * @notice Anchors The Last Oasis world state hashes on-chain every 50 ticks
 * @dev Oracle (backend) submits state hashes to prove honest world simulation
 *      Anyone can verify that the oracle is not manipulating the game state
 */
contract StateAnchorContract is Ownable, ReentrancyGuard {
    struct StateAnchor {
        uint256 tick;
        bytes32 stateHash;
        uint256 aliveAgents;
        uint256 timestamp;
        address submittedBy;
    }

    // Mapping: tick => StateAnchor
    mapping(uint256 => StateAnchor) public anchors;

    // Array of all anchor ticks for enumeration
    uint256[] public anchorTicks;

    // Oracle address (backend that submits anchors)
    address public oracle;

    // Anchor interval (ticks between anchors)
    uint256 public constant ANCHOR_INTERVAL = 50;

    // Events
    event StateAnchored(
        uint256 indexed tick,
        bytes32 stateHash,
        uint256 aliveAgents,
        uint256 timestamp
    );

    event OracleUpdated(address indexed oldOracle, address indexed newOracle);

    constructor(address _oracle) Ownable(msg.sender) {
        require(_oracle != address(0), "Invalid oracle address");
        oracle = _oracle;
    }

    modifier onlyOracle() {
        require(msg.sender == oracle, "Only oracle can call this");
        _;
    }

    /**
     * @notice Submit a state anchor at a specific tick
     * @param tick The world tick number (must be multiple of ANCHOR_INTERVAL)
     * @param stateHash SHA256 hash of the world state
     * @param aliveAgents Number of alive agents at this tick
     */
    function anchorState(
        uint256 tick,
        bytes32 stateHash,
        uint256 aliveAgents
    ) external onlyOracle nonReentrant {
        require(tick % ANCHOR_INTERVAL == 0, "Tick must be multiple of anchor interval");
        require(anchors[tick].tick == 0, "Anchor already exists for this tick");
        require(stateHash != bytes32(0), "Invalid state hash");

        StateAnchor memory anchor = StateAnchor({
            tick: tick,
            stateHash: stateHash,
            aliveAgents: aliveAgents,
            timestamp: block.timestamp,
            submittedBy: msg.sender
        });

        anchors[tick] = anchor;
        anchorTicks.push(tick);

        emit StateAnchored(tick, stateHash, aliveAgents, block.timestamp);
    }

    /**
     * @notice Get anchor for a specific tick
     * @param tick The tick to query
     * @return StateAnchor data
     */
    function getAnchor(uint256 tick) external view returns (StateAnchor memory) {
        require(anchors[tick].tick != 0, "No anchor for this tick");
        return anchors[tick];
    }

    /**
     * @notice Get the latest anchor
     * @return StateAnchor data
     */
    function getLatestAnchor() external view returns (StateAnchor memory) {
        require(anchorTicks.length > 0, "No anchors yet");
        uint256 latestTick = anchorTicks[anchorTicks.length - 1];
        return anchors[latestTick];
    }

    /**
     * @notice Get total number of anchors
     * @return Count of anchors
     */
    function getAnchorCount() external view returns (uint256) {
        return anchorTicks.length;
    }

    /**
     * @notice Verify state hash matches anchor
     * @param tick The tick to verify
     * @param stateHash The claimed state hash
     * @return bool True if hash matches
     */
    function verifyStateHash(uint256 tick, bytes32 stateHash) external view returns (bool) {
        if (anchors[tick].tick == 0) {
            return false;
        }
        return anchors[tick].stateHash == stateHash;
    }

    /**
     * @notice Update oracle address (only owner)
     * @param newOracle The new oracle address
     */
    function updateOracle(address newOracle) external onlyOwner {
        require(newOracle != address(0), "Invalid oracle address");
        address oldOracle = oracle;
        oracle = newOracle;
        emit OracleUpdated(oldOracle, newOracle);
    }

    /**
     * @notice Get all anchor ticks
     * @return Array of ticks
     */
    function getAllAnchorTicks() external view returns (uint256[] memory) {
        return anchorTicks;
    }

    /**
     * @notice Get multiple anchors in a range
     * @param startIndex Start index in anchorTicks array
     * @param count Number of anchors to return
     * @return Array of StateAnchors
     */
    function getAnchorsRange(uint256 startIndex, uint256 count)
        external
        view
        returns (StateAnchor[] memory)
    {
        require(startIndex < anchorTicks.length, "Start index out of bounds");

        uint256 endIndex = startIndex + count;
        if (endIndex > anchorTicks.length) {
            endIndex = anchorTicks.length;
        }

        uint256 resultCount = endIndex - startIndex;
        StateAnchor[] memory result = new StateAnchor[](resultCount);

        for (uint256 i = 0; i < resultCount; i++) {
            uint256 tick = anchorTicks[startIndex + i];
            result[i] = anchors[tick];
        }

        return result;
    }
}
