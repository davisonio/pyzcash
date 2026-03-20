# pyzcash

Python bindings for [librustzcash](https://github.com/zcash/librustzcash). Built with [PyO3](https://pyo3.rs).

Wraps `zcash_address`, `zip321`, and `zcash_keys` into four Python functions. All crypto runs in Rust.

## Install

```
pip install pyzcash
```

A pre-built wheel is available for macOS ARM64 / Python 3.14. For other platforms, pip will build from the source distribution, which requires a [Rust toolchain](https://rustup.rs).

To build from source directly:

```
git clone https://github.com/davisonio/pyzcash && cd pyzcash
pip install maturin
maturin develop
```

## Usage

```python
import pyzcash

# Parse any Zcash address (full checksum validation, not prefix matching)
info = pyzcash.parse_address("tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU")
info.address_type  # "p2pkh"
info.network       # "test"
info.is_shielded   # False

# Parse a ZIP-321 payment URI
payments = pyzcash.parse_payment_uri("zcash:tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU?amount=42.5")
payments[0].amount_zatoshis  # 4250000000
payments[0].amount_zec       # 42.5

# Generate a ZIP-321 payment URI
pyzcash.create_payment_uri("tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU", 4_250_000_000)
# "zcash:tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU?amount=42.5"

# Derive a unified address from a seed
import os
result = pyzcash.derive_address(os.urandom(32), network="main", account=0)
result.unified_address  # "u1..."
```

## What it wraps

| Function | Crate | Does |
|---|---|---|
| `parse_address()` | `zcash_address` | Validate + classify addresses |
| `parse_payment_uri()` | `zip321` | Parse ZIP-321 URIs |
| `create_payment_uri()` | `zip321` | Generate ZIP-321 URIs |
| `derive_address()` | `zcash_keys` | Seed to unified address (Orchard + Sapling) |

No reimplemented crypto. Checksums, key derivation, encoding are all handled by the Rust libraries.

## Status

Alpha. Four functions that work. Next steps:

- Transaction building
- Wallet scanning via `zcash_client_backend`
- Viewing key import/export
- Pre-built wheels so you don't need Rust installed

## License

MIT
