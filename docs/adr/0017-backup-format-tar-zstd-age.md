# ADR-0017: Backup format: tar + zstd + age

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D17

## Context

Backups must be portable and restorable without the panel.

## Decision

`tar` + `zstd`, optional encryption in **age** format (pyrage), with a `manifest.json` inside each archive.

## Consequences

Backups can be decrypted and extracted with standard `age` and `tar --zstd` tools.
