# ADR-0002: Target operating system

- Status: Accepted
- Date: 2026-11-13
- Source: MASTER_PROMPT §4, decision D2

## Context

Supporting many distributions multiplies installer and package-name differences.

## Decision

Ubuntu Server 22.04, 24.04 and 26.04 LTS on amd64 and arm64, with systemd as PID 1. Other distros are LATER.

## Consequences

Installer preflight rejects other systems. Package names and repository setup only need to handle Ubuntu.
