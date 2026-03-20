"""Smoke test for pyzcash — run this to verify the bindings work."""
import pyzcash
import os

# 1. Address parsing
info = pyzcash.parse_address("tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU")
assert info.address_type == "p2pkh"
assert info.network == "test"
assert info.is_shielded == False
print(f"[OK] parse_address: {info}")

# 2. ZIP-321 parse
payments = pyzcash.parse_payment_uri("zcash:tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU?amount=42.5")
assert len(payments) == 1
assert payments[0].amount_zatoshis == 4_250_000_000
print(f"[OK] parse_payment_uri: {payments[0].amount_zec} ZEC")

# 3. ZIP-321 parse without amount
payments_no_amount = pyzcash.parse_payment_uri("zcash:tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU")
assert payments_no_amount[0].amount_zatoshis is None
assert payments_no_amount[0].amount_zec is None
print("[OK] parse_payment_uri preserves omitted amount")

# 4. ZIP-321 generate + round-trip
uri = pyzcash.create_payment_uri("tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU", 100_000_000)
assert "amount=1" in uri
parsed_back = pyzcash.parse_payment_uri(uri)
assert parsed_back[0].amount_zatoshis == 100_000_000
print(f"[OK] create_payment_uri round-trip: {uri}")

# 5. Key derivation
seed = os.urandom(32)
addr = pyzcash.derive_address(seed, network="main", account=0)
assert addr.unified_address.startswith("u1")
info2 = pyzcash.parse_address(addr.unified_address)
assert info2.address_type == "unified"
assert info2.is_shielded == True
print(f"[OK] derive_address: {addr.unified_address[:30]}...")

# 6. Determinism check
addr2 = pyzcash.derive_address(seed, network="main", account=0)
assert addr.unified_address == addr2.unified_address
print("[OK] deterministic derivation")

# 7. Error handling
try:
    pyzcash.parse_address("garbage")
    assert False, "should have raised"
except ValueError:
    print("[OK] invalid address raises ValueError")

try:
    pyzcash.derive_address(b"\x00" * 31, network="main", account=0)
    assert False, "should have raised"
except ValueError:
    print("[OK] short seed raises ValueError")

print("\nAll checks passed.")
