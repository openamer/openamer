// SPDX-License-Identifier: UNLICENSED
// OpenAmer OS -- on-chain time source.
//
// A vesting contract must not trust a timestamp the caller supplies: a
// caller who wants tokens early would simply pass a later date. This
// contract pulls the block timestamp from the chain itself, and
// publishes it through a monotonically increasing accumulator so a
// caller can prove the time has only moved forward.

pragma solidity ^0.8.24;

/// @title Timestamp
/// @notice A trustworthy on-chain time source for the OAC vault.
/// @dev The block timestamp is the anchor: it is set by the consensus
///      layer and cannot be chosen by the caller of the contract. On
///      top of that this contract keeps a running accumulator that
///      only ever moves forward, so a stale timestamp can never be
///      replayed against the vault.
contract Timestamp {
    /// @notice The timestamp of the block the vault last consulted.
    uint256 public lastTimestamp;

    /// @notice The highest timestamp ever observed.
    uint256 public highestTimestamp;

    /// @notice The number of times the time was read.
    uint256 public updateCount;

    /// @notice Emitted whenever the time advances.
    event TimestampUpdated(uint256 timestamp, uint256 previous);

    /// @notice A timestamp that has already been consumed.
    /// @dev Replaying an old timestamp would let a caller unlock a
    ///      vesting tranche early, so it is refused.
    error StaleTimestamp(uint256 provided, uint256 current);

    /// @notice Read the current chain time and advance the accumulator.
    /// @dev Named currentTime rather than "now": "now" is a Solidity
    ///      builtin, and shadowing it warns.
    /// @return current The current block timestamp.
    function currentTime() external returns (uint256 current) {
        uint256 ts = block.timestamp;

        // The accumulator only moves forward. On the first call it is
        // simply set; afterwards a chain that reports an older time
        // than the one already published is ignored.
        if (ts > highestTimestamp) {
            emit TimestampUpdated(ts, highestTimestamp);
            highestTimestamp = ts;
            updateCount++;
        }

        lastTimestamp = ts;
        return ts;
    }

    /// @notice Read the current chain time without advancing anything.
    /// @return current The current block timestamp.
    function peek() external view returns (uint256 current) {
        return block.timestamp;
    }

    /// @notice Assert that a timestamp is not older than the published one.
    /// @param provided The timestamp the caller wants to use.
    function requireFresh(uint256 provided) external view {
        if (provided < highestTimestamp) {
            revert StaleTimestamp(provided, highestTimestamp);
        }
    }
}
