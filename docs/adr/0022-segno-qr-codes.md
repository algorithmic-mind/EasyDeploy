# ADR-0022: segno for TOTP QR codes

- Status: Accepted
- Date: 2026-11-13

## Context

TOTP enrollment (§9.1) shows a QR code of the `otpauth://` URI. The spec lists pyotp but no QR library.
Rendering the QR in the browser would need a JavaScript dependency; rendering on the server needs a Python one.

## Decision

Use **segno** (pure Python, no dependencies, BSD-3-Clause) on the server to produce an SVG data URI returned by
`POST /api/v1/auth/2fa/setup`.

## Consequences

One small, license-compatible dependency. The secret never leaves the API except in the enrollment response,
which also shows the secret as text for manual entry.
