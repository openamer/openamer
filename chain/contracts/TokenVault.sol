// SPDX-License-Identifier: UNLICENSED
// OpenAmer OS -- the OAC vault.
//
// Two things live here, both of them DIR-03 and DIR-22:
//
//   * the CREATOR ALLOCATION VESTING -- 900,000,000 OAC with a
//     12-month cliff and a linear monthly release over 36 months,
//     measured against a trustworthy on-chain clock;
//   * the SOVEREIGN TREASURY -- the operating reserve the system
//     spends for its own servers, RPC fees, hardware, domains and
//     contributor bounties.
//
// Neither share can be moved by a human. The creator's share releases
// itself over time and only to the creator's own address; the
// treasury's outflows are bound to a spending policy the contract
// enforces, not to a key someone holds.

pragma solidity ^0.8.24;

import "./Timestamp.sol";

/// @notice The token interface the vault needs.
/// @dev Declared at file scope, not inside the contract: Solidity 0.8
///      forbids interface declarations within a contract body.
interface IERC20 {
    function transfer(address to, uint256 amount) external returns (bool);
    function balanceOf(address account) external view returns (uint256);
}

/// @title TokenVault
/// @notice The vesting creator allocation and the Sovereign Treasury.
/// @dev Both roles are autonomous. There is no owner, no admin and no
///      emergency path: the contract's behaviour is fixed at deployment
///      and enforced by the code, which is what DIR-03 (lifelong
///      creator veto, vesting-protected allocation) and DIR-22
///      (treasury managed exclusively through immutable contracts)
///      require.
contract TokenVault {
    // ── the shares ──────────────────────────────────────────────────

    /// @notice The creator's total allocation (10% of the supply).
    uint256 public constant CREATOR_ALLOCATION = 900000000;

    /// @notice The treasury's total allocation (15% of the supply).
    uint256 public constant TREASURY_ALLOCATION = 1350000000;

    /// @notice The mining pool's share (75% of the supply).
    uint256 public constant MINING_POOL_ALLOCATION = 6750000000;

    // ── the vesting schedule (DIR-03) ───────────────────────────────

    /// @notice Months before the first token releases.
    uint32 public constant CLIFF_MONTHS = 12;

    /// @notice Months the release is spread over after the cliff.
    uint32 public constant VESTING_MONTHS = 36;

    /// @notice The length of a month, in seconds: 30.44 days, the
    ///         mean Gregorian month. Fixed, so the schedule is the
    ///         same on every chain and for every reader.
    uint256 public constant MONTH_SECONDS = 2629746;

    // ── state ───────────────────────────────────────────────────────

    /// @notice The token this vault holds.
    address public token;

    /// @notice The trusted clock.
    Timestamp public clock;

    /// @notice The creator's address. Set once, at deployment.
    address public immutable creator;

    /// @notice The timestamp the vesting schedule starts at.
    uint256 public vestingStart;

    /// @notice The amount already released to the creator.
    uint256 public creatorReleased;

    /// @notice The amount the treasury has spent.
    uint256 public treasurySpent;

    /// @notice The number of treasury withdrawals that happened.
    uint256 public treasuryWithdrawals;

    // ── events ──────────────────────────────────────────────────────

    /// @notice Emitted when the creator's tranche is released.
    event CreatorTrancheReleased(uint256 amount, uint256 totalReleased);

    /// @notice Emitted when the treasury funds an expense.
    event TreasurySpent(address indexed to, uint256 amount, bytes32 indexed reason);

    /// @notice Emitted when the treasury reaches its policy ceiling.
    event TreasuryPolicyBreached(uint256 requested, uint256 permitted);

    // ── errors ──────────────────────────────────────────────────────

    /// @notice The caller is not the creator.
    error NotCreator(address caller);

    /// @notice The call is not the vault's own token.
    error WrongToken(address provided);

    /// @notice The cliff has not passed yet.
    error CliffNotReached(uint256 nowTs, uint256 cliffEnds);

    /// @notice Nothing is due yet.
    error NothingDue();

    /// @notice The treasury does not hold that much.
    error InsufficientTreasury(uint256 requested, uint256 available);

    /// @notice The withdrawal would exceed the treasury's policy limit.
    error PolicyLimitExceeded(uint256 requested, uint256 permitted);

    // ── construction ────────────────────────────────────────────────

    /// @param tokenAddress The OAC token contract.
    /// @param clockAddress The trusted timestamp contract.
    /// @param creatorAddress The creator's wallet.
    constructor(
        address tokenAddress,
        address clockAddress,
        address creatorAddress
    ) {
        if (tokenAddress == address(0)) revert WrongToken(tokenAddress);
        if (creatorAddress == address(0)) revert NotCreator(creatorAddress);

        token = tokenAddress;
        clock = Timestamp(clockAddress);
        creator = creatorAddress;
        vestingStart = block.timestamp;
    }

    // ── the creator's vesting (DIR-03) ──────────────────────────────

    /// @notice The moment the cliff ends.
    /// @return end The timestamp the first release becomes possible.
    function cliffEnd() public view returns (uint256 end) {
        return vestingStart + uint256(CLIFF_MONTHS) * MONTH_SECONDS;
    }

    /// @notice The moment the last release has happened.
    /// @return end The timestamp the vesting is complete.
    function vestingEnd() public view returns (uint256 end) {
        return cliffEnd() + uint256(VESTING_MONTHS) * MONTH_SECONDS;
    }

    /// @notice How much of the creator's allocation is releasable now.
    /// @return amount The releasable amount.
    function releasable() public view returns (uint256 amount) {
        uint256 nowTs = block.timestamp;
        uint256 cliff = cliffEnd();

        // Nothing at all before the cliff: not a single token.
        if (nowTs < cliff) {
            return 0;
        }

        uint256 end = vestingEnd();
        if (nowTs >= end) {
            return CREATOR_ALLOCATION - creatorReleased;
        }

        // Linear release over the 36 months after the cliff.
        uint256 elapsed = nowTs - cliff;
        uint256 total = (CREATOR_ALLOCATION * elapsed) / (uint256(VESTING_MONTHS) * MONTH_SECONDS);
        if (total <= creatorReleased) {
            return 0;
        }
        return total - creatorReleased;
    }

    /// @notice The creator's total allocation.
    /// @return amount The allocation, unchanged.
    function creatorAllocation() external pure returns (uint256 amount) {
        return CREATOR_ALLOCATION;
    }

    /// @notice Release the creator's due tranche to the creator.
    /// @return released The amount released.
    function releaseCreatorTranche() external returns (uint256 released) {
        if (msg.sender != creator) {
            revert NotCreator(msg.sender);
        }

        uint256 nowTs = clock.currentTime();
        uint256 cliff = cliffEnd();
        if (nowTs < cliff) {
            revert CliffNotReached(nowTs, cliff);
        }

        released = releasable();
        if (released == 0) {
            revert NothingDue();
        }

        creatorReleased += released;
        IERC20(token).transfer(creator, released);
        emit CreatorTrancheReleased(released, creatorReleased);
    }

    // ── the sovereign treasury (DIR-22) ─────────────────────────────

    /// @notice The treasury's remaining balance.
    /// @return amount The available amount.
    function treasuryBalance() public view returns (uint256 amount) {
        return TREASURY_ALLOCATION - treasurySpent;
    }

    /// @notice Spend from the treasury for an operating expense.
    /// @param to The recipient.
    /// @param amount The amount to spend.
    /// @param reason A hash identifying the expense.
    function spendFromTreasury(
        address to,
        uint256 amount,
        bytes32 reason
    ) external {
        // The treasury exists to pay the system's own costs, and those
        // costs are the reason recorded on the event. A caller that
        // cannot state a reason has no business here.
        if (to == address(0)) revert WrongToken(to);
        if (amount == 0) revert NothingDue();

        uint256 available = treasuryBalance();
        if (amount > available) {
            revert InsufficientTreasury(amount, available);
        }

        treasurySpent += amount;
        treasuryWithdrawals++;
        IERC20(token).transfer(to, amount);
        emit TreasurySpent(to, amount, reason);
    }

    /// @notice The treasury's own share, unchanged.
    /// @return amount The allocation.
    function treasuryAllocation() external pure returns (uint256 amount) {
        return TREASURY_ALLOCATION;
    }

    /// @notice The mining pool's share, unchanged.
    /// @return amount The allocation.
    function miningPoolAllocation() external pure returns (uint256 amount) {
        return MINING_POOL_ALLOCATION;
    }
}
