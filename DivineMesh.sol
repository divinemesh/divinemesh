// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/**
 * @title DivineMesh Coin (DMC)
 * @dev ERC-20 token + compute reward + project investment engine
 *
 * "In the beginning was the Word, and the Word was with God, and the Word was God." - John 1:1
 * "Jesus Christ is the same yesterday and today and forever." - Hebrews 13:8
 *
 * This contract is the financial backbone of DivineMesh Network.
 * Compute power is rewarded. Projects are funded. No personal data stored.
 */

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/security/ReentrancyGuard.sol";
import "@openzeppelin/contracts/security/Pausable.sol";

// ──────────────────────────────────────────────────────────────────────────────
//  Node Registry — stores only cryptographic hashes, zero personal data
// ──────────────────────────────────────────────────────────────────────────────
contract DivineMeshRegistry is Ownable, ReentrancyGuard {
    // 'God sees not as man sees; man looks at outward appearance.' - 1 Sam 16:7
    struct NodeRecord {
        bytes32 pubKeyHash;
        bytes32 ipHash;
        uint8   macCount;
        bool    registered;
        uint256 registeredAt;
    }

    // Max MACs per IP — prevents GPU farm monetization abuse
    uint8 public constant MAX_MACS_PER_IP = 10;

    mapping(bytes32 => NodeRecord) public nodes;
    mapping(bytes32 => bytes32[]) public ipToMacs; // ipHash => macHashes
    mapping(bytes32 => mapping(bytes32 => bool)) public ipMacExists;

    event NodeRegistered(bytes32 indexed nodeId, uint256 timestamp);
    event MacRegistered(bytes32 indexed nodeId, bytes32 indexed macHash);

    constructor() Ownable(msg.sender) {}

    function registerNode(
        bytes32 nodeId,
        bytes32 pubKeyHash,
        bytes32 ipHash
    ) external nonReentrant {
        require(!nodes[nodeId].registered, "Node already registered");
        nodes[nodeId] = NodeRecord({
            pubKeyHash: pubKeyHash,
            ipHash: ipHash,
            macCount: 0,
            registered: true,
            registeredAt: block.timestamp
        });
        emit NodeRegistered(nodeId, block.timestamp);
    }

    function registerMac(bytes32 nodeId, bytes32 macHash) external nonReentrant returns (bool) {
        require(nodes[nodeId].registered, "Node not registered");
        bytes32 ipHash = nodes[nodeId].ipHash;
        require(!ipMacExists[ipHash][macHash], "MAC already registered for this IP");
        require(ipToMacs[ipHash].length < MAX_MACS_PER_IP, "IP reached MAC limit");

        ipToMacs[ipHash].push(macHash);
        ipMacExists[ipHash][macHash] = true;
        nodes[nodeId].macCount++;
        emit MacRegistered(nodeId, macHash);
        return true;
    }

    function isRegistered(bytes32 nodeId) external view returns (bool) {
        return nodes[nodeId].registered;
    }

    function getMacCount(bytes32 ipHash) external view returns (uint8) {
        return uint8(ipToMacs[ipHash].length);
    }
}

// ──────────────────────────────────────────────────────────────────────────────
//  DMC Token + Compute Rewards + Project Investments
// ──────────────────────────────────────────────────────────────────────────────
contract DivineMeshCoin is ERC20, Ownable, ReentrancyGuard, Pausable {

    // ── Sacred Constants ───────────────────────────────────────────────────
    // 'I am the Alpha and the Omega, the First and the Last.' - Rev 1:8
    uint256 public constant MAX_SUPPLY = 144_000_000 * 10**18; // 144M DMC (Rev 7:4)
    uint256 public constant REWARD_RATE = 1e15; // 0.001 DMC per compute unit
    uint8  public constant OWNER_MIN_SHARE = 51; // Project owners always hold ≥51%

    DivineMeshRegistry public registry;

    // ── Profit Distribution Wallets (3 accounts, all owner-controlled) ─────
    address public profitPrimary;
    address public profitReserve;
    address public profitTithe;
    uint8 public constant PROFIT_PRIMARY_PCT = 50;
    uint8 public constant PROFIT_RESERVE_PCT = 30;
    uint8 public constant PROFIT_TITHE_PCT   = 20;

    // ── Projects ──────────────────────────────────────────────────────────
    struct Project {
        bytes32 ownerNodeId;
        address ownerWallet;
        uint256 totalComputeUnits;
        uint256 ownerComputeUnits;
        bool    active;
        uint256 createdAt;
        string  metadataIpfs;  // IPFS CID for title/description (no PII)
    }

    struct Investor {
        uint256 computeUnits;
        uint256 sharePermille; // out of 1000 (permille precision)
        bool    exists;
    }

    mapping(bytes32 => Project) public projects;
    mapping(bytes32 => mapping(address => Investor)) public projectInvestors;
    mapping(bytes32 => address[]) public projectInvestorList;

    // ── Reward Claims ─────────────────────────────────────────────────────
    mapping(bytes32 => uint256) public pendingRewards; // nodeId => DMC wei
    mapping(bytes32 => bool)    public proofUsed;      // merkleProofHash => used

    // ── Events ────────────────────────────────────────────────────────────
    event RewardClaimed(bytes32 indexed nodeId, address indexed wallet, uint256 amount);
    event ProjectCreated(bytes32 indexed projectId, bytes32 indexed ownerNodeId);
    event ComputeDonated(bytes32 indexed projectId, address indexed investor, uint256 units);
    event ProfitDistributed(uint256 primary, uint256 reserve, uint256 tithe);
    event Withdrawal(address indexed wallet, uint256 amount);

    constructor(
        address _registry,
        address _profitPrimary,
        address _profitReserve,
        address _profitTithe
    ) ERC20("DivineMesh Coin", "DMC") Ownable(msg.sender) {
        registry = DivineMeshRegistry(_registry);
        profitPrimary = _profitPrimary;
        profitReserve = _profitReserve;
        profitTithe   = _profitTithe;
        // Mint initial supply to owner for liquidity seeding
        _mint(msg.sender, 10_000_000 * 10**18);
    }

    // ── Compute Reward Claim ──────────────────────────────────────────────

    /**
     * @dev Node submits compute proof and earns DMC.
     * 'Whatever you do, work at it with all your heart.' - Colossians 3:23
     */
    function claimReward(
        bytes32 nodeId,
        uint256 computeUnits,
        bytes32 proof
    ) external nonReentrant whenNotPaused {
        require(registry.isRegistered(nodeId), "Node not registered");
        require(!proofUsed[proof], "Proof already used");
        require(computeUnits > 0, "No compute units");

        uint256 reward = computeUnits * REWARD_RATE;
        require(totalSupply() + reward <= MAX_SUPPLY, "Max supply reached");

        proofUsed[proof] = true;
        _mint(msg.sender, reward);
        emit RewardClaimed(nodeId, msg.sender, reward);
    }

    // ── Project Management ────────────────────────────────────────────────

    /**
     * @dev Create a new compute project listing.
     * 'Plans are established by seeking advice.' - Proverbs 20:18
     */
    function createProject(
        bytes32 projectId,
        bytes32 ownerNodeId,
        string calldata metadataIpfs
    ) external nonReentrant whenNotPaused {
        require(!projects[projectId].active, "Project exists");
        require(registry.isRegistered(ownerNodeId), "Owner node not registered");

        projects[projectId] = Project({
            ownerNodeId:       ownerNodeId,
            ownerWallet:       msg.sender,
            totalComputeUnits: 0,
            ownerComputeUnits: 0,
            active:            true,
            createdAt:         block.timestamp,
            metadataIpfs:      metadataIpfs
        });
        emit ProjectCreated(projectId, ownerNodeId);
    }

    /**
     * @dev Donate compute power to a project. Shares are calculated proportionally,
     *      with the project owner always holding ≥51%.
     * 'Give, and it will be given to you.' - Luke 6:38
     */
    function donateCompute(bytes32 projectId, uint256 computeUnits) external nonReentrant whenNotPaused {
        Project storage p = projects[projectId];
        require(p.active, "Project not active");
        require(computeUnits > 0, "Zero units");

        if (!projectInvestors[projectId][msg.sender].exists) {
            projectInvestors[projectId][msg.sender] = Investor({
                computeUnits: 0,
                sharePermille: 0,
                exists: true
            });
            projectInvestorList[projectId].push(msg.sender);
        }

        p.totalComputeUnits += computeUnits;
        projectInvestors[projectId][msg.sender].computeUnits += computeUnits;

        // Recalculate shares (owner always ≥ 51%)
        _rebalanceShares(projectId);
        emit ComputeDonated(projectId, msg.sender, computeUnits);
    }

    function _rebalanceShares(bytes32 projectId) internal {
        Project storage p = projects[projectId];
        uint256 total = p.totalComputeUnits;
        if (total == 0) return;

        uint256 ownerPermille = (p.ownerComputeUnits * 1000) / total;
        if (ownerPermille < OWNER_MIN_SHARE * 10) {
            ownerPermille = OWNER_MIN_SHARE * 10; // enforce 51% floor
        }
        uint256 remaining = 1000 - ownerPermille;

        address[] storage investors = projectInvestorList[projectId];
        uint256 investorTotal = total - p.ownerComputeUnits;
        if (investorTotal == 0) return;

        for (uint i = 0; i < investors.length; i++) {
            Investor storage inv = projectInvestors[projectId][investors[i]];
            inv.sharePermille = (inv.computeUnits * remaining) / investorTotal;
        }
    }

    function getProjectShare(bytes32 projectId, address investor)
        external view returns (uint256 sharePermille)
    {
        return projectInvestors[projectId][investor].sharePermille;
    }

    // ── Profit Distribution ───────────────────────────────────────────────

    /**
     * @dev Distribute platform fees to three owner-controlled accounts.
     * 'Honor the Lord with your wealth, with the firstfruits of all your crops.' - Prov 3:9
     */
    function distributePlatformProfit(uint256 totalAmount) external onlyOwner nonReentrant {
        require(balanceOf(msg.sender) >= totalAmount, "Insufficient balance");
        uint256 primary = (totalAmount * PROFIT_PRIMARY_PCT) / 100;
        uint256 reserve = (totalAmount * PROFIT_RESERVE_PCT) / 100;
        uint256 tithe   = totalAmount - primary - reserve;
        _transfer(msg.sender, profitPrimary, primary);
        _transfer(msg.sender, profitReserve, reserve);
        _transfer(msg.sender, profitTithe,   tithe);
        emit ProfitDistributed(primary, reserve, tithe);
    }

    // ── Admin ─────────────────────────────────────────────────────────────

    function pause() external onlyOwner { _pause(); }
    function unpause() external onlyOwner { _unpause(); }

    function updateProfitWallets(
        address _primary, address _reserve, address _tithe
    ) external onlyOwner {
        profitPrimary = _primary;
        profitReserve = _reserve;
        profitTithe   = _tithe;
    }

    function _update(address from, address to, uint256 value)
        internal override whenNotPaused
    {
        super._update(from, to, value);
    }
}
