"""Tests for pyzcash bindings."""

import pytest
import pyzcash

# Valid addresses from the ZIP-321 spec and key derivation.
TESTNET_TRANSPARENT = "tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU"
MAINNET_P2SH = "t3JZcvsuaXE6ygokL4XUiZSTrQBUoPYFnXJ"
MAINNET_TEX = "tex1s2rt77ggv6q989lr49rkgzmh5slsksa9khdgte"
MAINNET_SPROUT = "zc8E5gYid86n4bo2Usdq1cpr7PpfoJGzttwBHEEgGhGkLUg7SPPVFNB2AkRFXZ7usfphup5426dt1buMmY3fkYeRrQGLa8y"
TESTNET_SAPLING = "ztestsapling10yy2ex5dcqkclhc7z7yrnjq2z6feyjad56ptwlfgmy77dmaqqrl9gyhprdx59qgmsnyfska2kez"
REGTEST_SAPLING = "zregtestsapling1qqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqqknpr3m"
# Derived from all-zero seed via derive_address.
MAINNET_UNIFIED = "u1028puzku37pr8qqtmmxn6t5qws64gn58w0mfw8fhj5lekzanzv50vxd8g6ry9trq495645g4kgtn6ppw73x6r6xje7na3jcs8sryx2el"


# ---- Address parsing ----


class TestParseAddress:
    def test_transparent_testnet(self):
        info = pyzcash.parse_address(TESTNET_TRANSPARENT)
        assert info.address_type == "p2pkh"
        assert info.network == "test"
        assert info.is_shielded is False

    def test_sapling_testnet(self):
        info = pyzcash.parse_address(TESTNET_SAPLING)
        assert info.address_type == "sapling"
        assert info.network == "test"
        assert info.is_shielded is True

    def test_unified_mainnet(self):
        info = pyzcash.parse_address(MAINNET_UNIFIED)
        assert info.address_type == "unified"
        assert info.network == "main"
        assert info.is_shielded is True

    def test_p2sh_mainnet(self):
        info = pyzcash.parse_address(MAINNET_P2SH)
        assert info.address_type == "p2sh"
        assert info.network == "main"
        assert info.is_shielded is False

    def test_tex_mainnet(self):
        info = pyzcash.parse_address(MAINNET_TEX)
        assert info.address_type == "tex"
        assert info.network == "main"
        assert info.is_shielded is False

    def test_sprout_mainnet(self):
        info = pyzcash.parse_address(MAINNET_SPROUT)
        assert info.address_type == "sprout"
        assert info.network == "main"
        assert info.is_shielded is True

    def test_sapling_regtest(self):
        info = pyzcash.parse_address(REGTEST_SAPLING)
        assert info.address_type == "sapling"
        assert info.network == "regtest"
        assert info.is_shielded is True

    def test_invalid_address_raises(self):
        with pytest.raises(ValueError, match="invalid address"):
            pyzcash.parse_address("not_an_address")

    def test_empty_address_raises(self):
        with pytest.raises(ValueError):
            pyzcash.parse_address("")

    def test_round_trip_encoding(self):
        info = pyzcash.parse_address(TESTNET_TRANSPARENT)
        assert info.encoded == TESTNET_TRANSPARENT

    def test_address_info_repr(self):
        info = pyzcash.parse_address(TESTNET_TRANSPARENT)
        r = repr(info)
        assert "p2pkh" in r
        assert "test" in r


# ---- ZIP-321 URI parsing ----


class TestParsePaymentURI:
    def test_simple_with_amount(self):
        uri = f"zcash:{TESTNET_TRANSPARENT}?amount=1.5"
        payments = pyzcash.parse_payment_uri(uri)
        assert len(payments) == 1
        assert payments[0].amount_zatoshis == 150_000_000
        assert payments[0].amount_zec == pytest.approx(1.5)

    def test_address_only(self):
        uri = f"zcash:{TESTNET_TRANSPARENT}"
        payments = pyzcash.parse_payment_uri(uri)
        assert len(payments) == 1
        assert TESTNET_TRANSPARENT in payments[0].address
        assert payments[0].amount_zatoshis is None
        assert payments[0].amount_zec is None

    def test_zero_amount_is_preserved(self):
        uri = f"zcash:{TESTNET_TRANSPARENT}?amount=0"
        payments = pyzcash.parse_payment_uri(uri)
        assert len(payments) == 1
        assert payments[0].amount_zatoshis == 0
        assert payments[0].amount_zec == 0

    def test_sapling_with_memo(self):
        uri = (
            f"zcash:{TESTNET_SAPLING}"
            "?amount=1&memo=VGhpcyBpcyBhIHNpbXBsZSBtZW1vLg"
            "&message=Thank%20you%20for%20your%20purchase"
        )
        payments = pyzcash.parse_payment_uri(uri)
        assert len(payments) == 1
        assert payments[0].amount_zatoshis == 100_000_000
        assert payments[0].memo is not None
        assert payments[0].message == "Thank you for your purchase"

    def test_multi_payment(self):
        uri = (
            f"zcash:?address={TESTNET_TRANSPARENT}&amount=123.456"
            f"&address.1={TESTNET_SAPLING}&amount.1=0.789"
            "&memo.1=VGhpcyBpcyBhIHVuaWNvZGUgbWVtbyDinKjwn6aE8J-PhvCfjok"
        )
        payments = pyzcash.parse_payment_uri(uri)
        assert len(payments) == 2

    def test_invalid_uri_raises(self):
        with pytest.raises(ValueError):
            pyzcash.parse_payment_uri("not_a_uri")

    def test_transparent_memo_raises(self):
        uri = f"zcash:{TESTNET_TRANSPARENT}?memo=VGhpcyBpcyBhIHNpbXBsZSBtZW1vLg"
        with pytest.raises(ValueError, match="transparent recipient"):
            pyzcash.parse_payment_uri(uri)

    def test_invalid_memo_base64_raises(self):
        uri = f"zcash:{TESTNET_SAPLING}?memo=***not-base64***"
        with pytest.raises(ValueError, match="base64"):
            pyzcash.parse_payment_uri(uri)

    def test_payment_info_repr(self):
        uri = f"zcash:{TESTNET_TRANSPARENT}?amount=1"
        payments = pyzcash.parse_payment_uri(uri)
        r = repr(payments[0])
        assert "PaymentInfo" in r


# ---- ZIP-321 URI generation ----


class TestCreatePaymentURI:
    def test_basic_generation(self):
        uri = pyzcash.create_payment_uri(TESTNET_TRANSPARENT, 150_000_000)
        assert uri.startswith("zcash:")
        assert TESTNET_TRANSPARENT in uri

    def test_round_trip(self):
        uri = pyzcash.create_payment_uri(TESTNET_TRANSPARENT, 100_000_000)
        payments = pyzcash.parse_payment_uri(uri)
        assert len(payments) == 1
        assert payments[0].amount_zatoshis == 100_000_000

    def test_invalid_address_raises(self):
        with pytest.raises(ValueError):
            pyzcash.create_payment_uri("bad_address", 100)

    def test_max_supply_amount(self):
        uri = pyzcash.create_payment_uri(TESTNET_TRANSPARENT, 21_000_000 * 100_000_000)
        assert "amount=21000000" in uri

    def test_amount_above_max_supply_raises(self):
        with pytest.raises(ValueError, match="maximum ZEC supply"):
            pyzcash.create_payment_uri(TESTNET_TRANSPARENT, 21_000_000 * 100_000_000 + 1)


# ---- Key derivation ----


class TestDeriveAddress:
    def test_derive_mainnet(self):
        seed = bytes(32)
        result = pyzcash.derive_address(seed, network="main", account=0)
        assert result.unified_address.startswith("u1")
        assert result.network == "main"
        assert result.account == 0

    def test_derive_testnet(self):
        seed = bytes(32)
        result = pyzcash.derive_address(seed, network="test", account=0)
        assert result.unified_address.startswith("utest1")
        assert result.network == "test"

    def test_different_seeds_different_addresses(self):
        seed_a = bytes(32)
        seed_b = bytes([1] + [0] * 31)
        addr_a = pyzcash.derive_address(seed_a, network="main", account=0)
        addr_b = pyzcash.derive_address(seed_b, network="main", account=0)
        assert addr_a.unified_address != addr_b.unified_address

    def test_different_accounts_different_addresses(self):
        seed = bytes(32)
        addr_0 = pyzcash.derive_address(seed, network="main", account=0)
        addr_1 = pyzcash.derive_address(seed, network="main", account=1)
        assert addr_0.unified_address != addr_1.unified_address

    def test_invalid_network_raises(self):
        with pytest.raises(ValueError, match="network"):
            pyzcash.derive_address(bytes(32), network="invalid", account=0)

    def test_short_seed_raises(self):
        with pytest.raises(ValueError, match="at least 32 bytes"):
            pyzcash.derive_address(bytes(31), network="main", account=0)

    def test_nonstandard_seed_length_is_allowed(self):
        result = pyzcash.derive_address(bytes(33), network="main", account=0)
        assert result.unified_address.startswith("u1")

    def test_deterministic(self):
        seed = bytes(range(32))
        a = pyzcash.derive_address(seed, network="main", account=0)
        b = pyzcash.derive_address(seed, network="main", account=0)
        assert a.unified_address == b.unified_address

    def test_repr(self):
        seed = bytes(32)
        result = pyzcash.derive_address(seed, network="main", account=0)
        r = repr(result)
        assert "DerivedAddress" in r
        assert "main" in r

    def test_derived_address_is_valid(self):
        """Addresses generated by derive_address should pass parse_address."""
        seed = bytes(range(32))
        derived = pyzcash.derive_address(seed, network="main", account=0)
        info = pyzcash.parse_address(derived.unified_address)
        assert info.address_type == "unified"
        assert info.network == "main"
        assert info.is_shielded is True

    def test_max_account_index(self):
        result = pyzcash.derive_address(bytes(32), network="main", account=2**31 - 1)
        assert result.account == 2**31 - 1

    def test_account_above_zip32_range_raises(self):
        with pytest.raises(ValueError, match="invalid account index"):
            pyzcash.derive_address(bytes(32), network="main", account=2**31)
