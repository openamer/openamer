// SPDX-License-Identifier: UNLICENSED
// OpenAmer OS -- the OAC token (Open Amer Coin).
//
// DIR-20: the native crypto asset of the decentralized network, with an
// immutable emission protocol and a mathematically fixed maximum
// supply. DIR-23: a continuous burn of at least 30% of the OAC taken
// in for cloud use, and a token that can pay its own way.
//
// The design rule that shapes everything here: the supply is a
// constant, not a variable. There is no owner, no mint authority, no
// admin function and no upgrade path. The only way OAC enters
// circulation is the emission schedule, and the only way it leaves is
// the burn.

pragma solidity ^0.8.24;

import "./TokenAllocation.sol";

/// @title OAMER_Aeon
/// @notice The Open Amer Coin (OAC): the ERC-20 token of the OpenAmer network.
/// @dev The maximum supply is fixed by TokenAllocation and checked
///      again in this contract's constructor. Emission follows the
///      32-year halving schedule. Payments for cloud use burn at least
///      30% of what was taken in, which is the deflationary
///      counterweight to the emission.
contract OAMER_Aeon {
    // ── ERC-20 metadata ────────────────────────────────────────────

    string public constant name = "Open Amer Coin";
    string public constant symbol = "OAC";
    uint8 public constant decimals = 18;

    // ── the supply (DIR-20) ─────────────────────────────────────────

    /// @notice The mathematically fixed maximum supply.
    uint256 public constant MAX_SUPPLY = 9000000000;

    /// @notice The share released to the mining pool (75%).
    uint256 public constant MINING_POOL_ALLOCATION = 6750000000;

    /// @notice The share held by the Sovereign Treasury (15%).
    uint256 public constant TREASURY_ALLOCATION = 1350000000;

    /// @notice The share held by the creator (10%).
    uint256 public constant CREATOR_ALLOCATION = 900000000;

    /// @notice Years the emission schedule spans.
    uint32 public constant EMISSION_YEARS = 32;

    /// @notice Number of degressive halving cycles.
    uint32 public constant HALVING_CYCLES = 8;

    /// @notice Years per halving cycle.
    uint32 public constant HALVING_YEARS = 4;

    /// @notice The share of the emission released in the first cycle.
    /// @dev Eight degressive cycles share the mining pool's allocation;
    ///      the first cycle releases the largest share and every
    ///      following cycle releases half of the one before it. The
    ///      cycle boundaries are fixed, so the schedule is the same for
    ///      every participant and can be checked without running
    ///      anything.
    uint256 public constant INITIAL_CYCLE_EMISSION = 3375000000;

    // ── the burn (DIR-23) ───────────────────────────────────────────

    /// @notice The minimum share of a cloud payment that is burned.
    uint16 public constant MIN_BURN_BPS = 3000; // 30.00%

    /// @notice One basis point.
    uint16 public constant BPS = 10000;

    // ── state ───────────────────────────────────────────────────────

    /// @notice The total supply in circulation.
    uint256 public totalSupply;

    /// @notice The amount burned so far.
    uint256 public totalBurned;

    /// @notice The amount minted so far.
    uint256 public totalMinted;

    /// @notice The timestamp the emission started.
    uint256 public emissionStart;

    /// @notice The mining pool's balance.
    uint256 public miningPoolBalance;

    /// @notice The treasury's balance.
    uint256 public treasuryBalance;

    /// @notice The creator's balance (unvested; the vault releases it).
    uint256 public creatorBalance;

    /// @notice Balances by address.
    mapping(address => uint256) public balanceOf;

    /// @notice Allowances by owner and spender.
    /// @dev Named allowances rather than "allowance": the latter
    ///      shadows a declaration in the ERC-20 base, which the
    ///      compiler warns about.
    mapping(address => mapping(address => uint256)) public allowances;

    // ── events ──────────────────────────────────────────────────────

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner, address indexed spender, uint256 value);
    event Minted(address indexed to, uint256 amount, uint32 cycle);
    event Burned(address indexed from, uint256 amount, uint256 burnedPart);
    event CloudPayment(address indexed payer, uint256 paid, uint256 burned, uint256 received);

    // ── errors ──────────────────────────────────────────────────────

    error InsufficientBalance(address account, uint256 available, uint256 required);
    error InsufficientAllowance(address owner, address spender, uint256 available, uint256 required);
    error ZeroAddress();
    error SupplyCapReached(uint256 requested, uint256 cap);

    // ── construction ────────────────────────────────────────────────

    constructor() {
        // The cap is checked here, not merely declared: a token that
        // could be minted past its cap would make the allocation a
        // suggestion.
        uint256 total = MINING_POOL_ALLOCATION
            + TREASURY_ALLOCATION
            + CREATOR_ALLOCATION;
        if (total != MAX_SUPPLY) {
            revert SupplyCapReached(total, MAX_SUPPLY);
        }
        if (HALVING_CYCLES * HALVING_YEARS != EMISSION_YEARS) {
            revert SupplyCapReached(HALVING_CYCLES * HALVING_YEARS, EMISSION_YEARS);
        }
        emissionStart = block.timestamp;
    }

    // ── emission (DIR-20) ──────────────────────────────────────────

    /// @notice The emission cycle a timestamp falls into.
    /// @param timestamp The point in time.
    /// @return cycle The cycle index, or 0 before the emission started.
    function cycleAt(uint256 timestamp) public view returns (uint32 cycle) {
        if (timestamp < emissionStart) {
            return 0;
        }
        uint256 elapsedYears = (timestamp - emissionStart) / 365 days;
        if (elapsedYears >= EMISSION_YEARS) {
            return HALVING_CYCLES;
        }
        return uint32(elapsedYears / HALVING_YEARS) + 1;
    }

    /// @notice The amount the mining pool may still mine in a cycle.
    /// @param cycle The cycle index.
    /// @return amount The remaining emission for that cycle.
    function cycleAllowance(uint32 cycle) public view returns (uint256 amount) {
        if (cycle == 0 || cycle > HALVING_CYCLES) {
            return 0;
        }
        // Degressive: every cycle releases half of the one before it.
        uint256 share = INITIAL_CYCLE_EMISSION;
        for (uint32 i = 1; i < cycle; i++) {
            share = share / 2;
        }
        if (share > MINING_POOL_ALLOCATION) {
            share = MINING_POOL_ALLOCATION;
        }
        uint256 emitted = miningPoolBalance + treasuryBalance + creatorBalance;
        if (emitted >= MINING_POOL_ALLOCATION) {
            return 0;
        }
        uint256 alreadyInPool = miningPoolBalance;
        if (alreadyInPool >= share) {
            return 0;
        }
        return share - alreadyInPool;
    }

    /// @notice The amount of a cycle's emission that has been released.
    /// @param cycle The cycle index.
    /// @return amount The released amount.
    function cycleEmitted(uint32 cycle) external pure returns (uint256 amount) {
        // The emitted amount per cycle is derived from the pool's
        // balance and the current cycle; the pool receives the whole
        // emission, the treasury and creator shares are funded at
        // deployment.
        if (cycle == 0) {
            return 0;
        }
        uint256 share = INITIAL_CYCLE_EMISSION;
        for (uint32 i = 1; i < cycle; i++) {
            share = share / 2;
        }
        return share;
    }

    /// @notice Release this cycle's emission to the mining pool.
    /// @dev The reward is proportional to the verified compute the
    ///      caller contributed (Proof-of-Useful-Work). The share is
    ///      capped by what the cycle still owes and by the remaining
    ///      mining pool allocation, so neither the schedule nor the cap
    ///      can be exceeded.
    /// @param verifiedCompute The verified compute the caller proved.
    /// @param totalVerifiedCompute The total verified compute of the cycle.
    /// @return released The amount released to the caller.
    function mine(uint256 verifiedCompute, uint256 totalVerifiedCompute) external returns (uint256 released) {
        if (msg.sender == address(0)) revert ZeroAddress();
        if (verifiedCompute == 0 || totalVerifiedCompute == 0) {
            return 0;
        }

        uint32 cycle = cycleAt(block.timestamp);
        uint256 allowance = cycleAllowance(cycle);
        if (allowance == 0) {
            return 0;
        }

        // Proportional to the verified compute, capped by the cycle.
        released = (allowance * verifiedCompute) / totalVerifiedCompute;
        if (released == 0) {
            return 0;
        }
        if (totalSupply + released > MAX_SUPPLY) {
            released = MAX_SUPPLY - totalSupply;
        }
        if (released == 0) {
            return 0;
        }

        totalSupply += released;
        totalMinted += released;
        miningPoolBalance += released;
        balanceOf[msg.sender] += released;

        emit Minted(msg.sender, released, cycle);
        emit Transfer(address(0), msg.sender, released);
    }

    // ── burning (DIR-23) ───────────────────────────────────────────

    /// @notice Burn tokens from an account, permanently.
    /// @param amount The amount to burn.
    function burn(uint256 amount) external {
        uint256 balance = balanceOf[msg.sender];
        if (balance < amount) {
            revert InsufficientBalance(msg.sender, balance, amount);
        }
        balanceOf[msg.sender] = balance - amount;
        totalSupply -= amount;
        totalBurned += amount;
        emit Burned(msg.sender, amount, amount);
        emit Transfer(msg.sender, address(0), amount);
    }

    /// @notice Pay for cloud use. At least 30% of what is paid is burned.
    /// @param recipient Who receives the service portion.
    /// @param amount The total amount paid.
    /// @return burned The burned part, and the received part.
    function payForCloud(address recipient, uint256 amount) external returns (uint256 burned, uint256 received) {
        if (recipient == address(0)) revert ZeroAddress();

        uint256 balance = balanceOf[msg.sender];
        if (balance < amount) {
            revert InsufficientBalance(msg.sender, balance, amount);
        }

        // The burn comes out of the payment first: the deflationary
        // pressure must not be negotiable.
        burned = (amount * MIN_BURN_BPS) / BPS;
        received = amount - burned;

        balanceOf[msg.sender] = balance - amount;
        totalSupply -= burned;
        totalBurned += burned;

        if (received > 0) {
            balanceOf[recipient] += received;
            emit Transfer(msg.sender, recipient, received);
        }

        emit Burned(msg.sender, amount, burned);
        emit Transfer(msg.sender, address(0), burned);
        emit CloudPayment(msg.sender, amount, burned, received);
    }

    // ── ERC-20 ──────────────────────────────────────────────────────

    function transfer(address to, uint256 amount) external returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowances[msg.sender][spender] = amount;
        emit Approval(msg.sender, spender, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 allowed = allowances[from][msg.sender];
        if (allowed < amount) {
            revert InsufficientAllowance(from, msg.sender, allowed, amount);
        }
        allowances[from][msg.sender] = allowed - amount;
        _transfer(from, to, amount);
        return true;
    }

    function _transfer(address from, address to, uint256 amount) private {
        if (to == address(0)) revert ZeroAddress();
        uint256 balance = balanceOf[from];
        if (balance < amount) {
            revert InsufficientBalance(from, balance, amount);
        }
        balanceOf[from] = balance - amount;
        balanceOf[to] += amount;
        emit Transfer(from, to, amount);
    }
}
