use std::collections::BTreeSet;

use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

use zcash_address::unified;
use zcash_address::{ConversionError, TryFromAddress, ZcashAddress};
use zcash_keys::keys::{UnifiedAddressRequest, UnifiedSpendingKey};
use zcash_protocol::consensus::{Network, NetworkType};
use zip321::{Payment, TransactionRequest};

// ---- Internal: address classification via TryFromAddress ----

struct AddressClassification {
    address_type: String,
    network: String,
    is_shielded: bool,
}

impl TryFromAddress for AddressClassification {
    type Error = ();

    fn try_from_sprout(net: NetworkType, _data: [u8; 64]) -> Result<Self, ConversionError<()>> {
        Ok(Self {
            address_type: "sprout".into(),
            network: net_str(net),
            is_shielded: true,
        })
    }

    fn try_from_sapling(net: NetworkType, _data: [u8; 43]) -> Result<Self, ConversionError<()>> {
        Ok(Self {
            address_type: "sapling".into(),
            network: net_str(net),
            is_shielded: true,
        })
    }

    fn try_from_unified(
        net: NetworkType,
        _data: unified::Address,
    ) -> Result<Self, ConversionError<()>> {
        Ok(Self {
            address_type: "unified".into(),
            network: net_str(net),
            is_shielded: true,
        })
    }

    fn try_from_transparent_p2pkh(
        net: NetworkType,
        _data: [u8; 20],
    ) -> Result<Self, ConversionError<()>> {
        Ok(Self {
            address_type: "p2pkh".into(),
            network: net_str(net),
            is_shielded: false,
        })
    }

    fn try_from_transparent_p2sh(
        net: NetworkType,
        _data: [u8; 20],
    ) -> Result<Self, ConversionError<()>> {
        Ok(Self {
            address_type: "p2sh".into(),
            network: net_str(net),
            is_shielded: false,
        })
    }

    fn try_from_tex(net: NetworkType, _data: [u8; 20]) -> Result<Self, ConversionError<()>> {
        Ok(Self {
            address_type: "tex".into(),
            network: net_str(net),
            is_shielded: false,
        })
    }
}

fn net_str(net: NetworkType) -> String {
    match net {
        NetworkType::Main => "main".into(),
        NetworkType::Test => "test".into(),
        NetworkType::Regtest => "regtest".into(),
    }
}

fn resolve_network(name: &str) -> PyResult<Network> {
    match name {
        "main" => Ok(Network::MainNetwork),
        "test" => Ok(Network::TestNetwork),
        _ => Err(PyValueError::new_err("network must be 'main' or 'test'")),
    }
}

fn amount_param_indices(uri: &str) -> BTreeSet<usize> {
    let mut indices = BTreeSet::new();

    let Some((_, query)) = uri.split_once('?') else {
        return indices;
    };

    for pair in query.split('&') {
        let key = pair.split_once('=').map(|(key, _)| key).unwrap_or(pair);

        if key == "amount" {
            indices.insert(0);
        } else if let Some(index) = key.strip_prefix("amount.") {
            if let Ok(index) = index.parse::<usize>() {
                indices.insert(index);
            }
        }
    }

    indices
}

// ---- Python-facing types ----

/// Parsed information about a Zcash address.
#[pyclass(frozen, get_all, skip_from_py_object)]
#[derive(Clone)]
struct AddressInfo {
    /// Re-encoded canonical form of the address.
    encoded: String,
    /// Address type: "p2pkh", "p2sh", "sapling", "unified", "sprout", or "tex".
    address_type: String,
    /// Network: "main", "test", or "regtest".
    network: String,
    /// Whether the address supports shielded transactions.
    is_shielded: bool,
}

#[pymethods]
impl AddressInfo {
    fn __repr__(&self) -> String {
        format!(
            "AddressInfo(type='{}', network='{}', shielded={})",
            self.address_type, self.network, self.is_shielded
        )
    }
}

/// A single payment parsed from a ZIP-321 URI.
#[pyclass(frozen, get_all, skip_from_py_object)]
#[derive(Clone)]
struct PaymentInfo {
    /// Recipient address string.
    address: String,
    /// Amount in zatoshis (1 ZEC = 100_000_000 zatoshi). None if not specified.
    amount_zatoshis: Option<u64>,
    /// Raw memo bytes, if present.
    memo: Option<Vec<u8>>,
    /// Human-readable label, if present.
    label: Option<String>,
    /// Human-readable message, if present.
    message: Option<String>,
}

#[pymethods]
impl PaymentInfo {
    fn __repr__(&self) -> String {
        let addr_preview = if self.address.len() > 16 {
            format!("{}...", &self.address[..16])
        } else {
            self.address.clone()
        };
        format!(
            "PaymentInfo(address='{}', amount_zatoshis={:?})",
            addr_preview, self.amount_zatoshis
        )
    }

    /// Amount in ZEC as a float. Use amount_zatoshis for precise calculations.
    #[getter]
    fn amount_zec(&self) -> Option<f64> {
        self.amount_zatoshis.map(|z| z as f64 / 100_000_000.0)
    }
}

/// Derived key material and address.
#[pyclass(frozen, get_all, skip_from_py_object)]
#[derive(Clone)]
struct DerivedAddress {
    /// Unified address string.
    unified_address: String,
    /// Network this address belongs to.
    network: String,
    /// Account index used for derivation.
    account: u32,
}

#[pymethods]
impl DerivedAddress {
    fn __repr__(&self) -> String {
        let addr_preview = if self.unified_address.len() > 16 {
            format!("{}...", &self.unified_address[..16])
        } else {
            self.unified_address.clone()
        };
        format!(
            "DerivedAddress(address='{}', network='{}', account={})",
            addr_preview, self.network, self.account
        )
    }
}

// ---- Exported functions ----

/// Parse and validate a Zcash address. Returns address type, network, and shielding info.
///
/// Supports transparent (p2pkh, p2sh), Sapling, Unified, TEX, and Sprout addresses.
/// Uses librustzcash for full cryptographic validation including checksum verification.
#[pyfunction]
fn parse_address(address: &str) -> PyResult<AddressInfo> {
    let parsed: ZcashAddress = address
        .parse()
        .map_err(|e| PyValueError::new_err(format!("invalid address: {e}")))?;

    let encoded = parsed.encode();
    let info: AddressClassification = parsed
        .convert()
        .map_err(|e| PyValueError::new_err(format!("unsupported address type: {e:?}")))?;

    Ok(AddressInfo {
        encoded,
        address_type: info.address_type,
        network: info.network,
        is_shielded: info.is_shielded,
    })
}

/// Parse a ZIP-321 payment request URI into a list of payments.
///
/// Handles both single-payment and multi-payment URIs per the ZIP-321 spec.
/// Uses librustzcash's zip321 crate for spec-compliant parsing.
#[pyfunction]
fn parse_payment_uri(uri: &str) -> PyResult<Vec<PaymentInfo>> {
    let req = TransactionRequest::from_uri(uri)
        .map_err(|e| PyValueError::new_err(format!("invalid payment URI: {e}")))?;
    let amount_indices = amount_param_indices(uri);

    let mut payments = Vec::new();
    for (idx, payment) in req.payments() {
        payments.push(PaymentInfo {
            address: payment.recipient_address().encode(),
            amount_zatoshis: amount_indices
                .contains(idx)
                .then(|| payment.amount().into()),
            memo: payment.memo().map(|m| m.as_slice().to_vec()),
            label: payment.label().cloned(),
            message: payment.message().cloned(),
        });
    }

    Ok(payments)
}

/// Generate a ZIP-321 payment URI for a single payment.
///
/// Amount is in zatoshis (1 ZEC = 100_000_000 zatoshi).
#[pyfunction]
fn create_payment_uri(address: &str, amount_zatoshis: u64) -> PyResult<String> {
    let addr: ZcashAddress = address
        .parse()
        .map_err(|e| PyValueError::new_err(format!("invalid address: {e}")))?;

    let amount = zcash_protocol::value::Zatoshis::from_u64(amount_zatoshis)
        .map_err(|_| PyValueError::new_err("amount exceeds maximum ZEC supply"))?;

    let payment = Payment::without_memo(addr, amount);
    let req = TransactionRequest::new(vec![payment])
        .map_err(|e| PyValueError::new_err(format!("cannot create request: {e}")))?;

    Ok(req.to_uri())
}

/// Derive a unified address from a wallet seed.
///
/// The seed must be at least 32 bytes. 32- and 64-byte seeds are common.
/// Network must be "main" or "test". Account is a ZIP-32 account index (usually 0).
///
/// Uses librustzcash key derivation with Orchard + Sapling receivers.
#[pyfunction]
fn derive_address(seed: Vec<u8>, network: &str, account: u32) -> PyResult<DerivedAddress> {
    if seed.len() < 32 {
        return Err(PyValueError::new_err("seed must be at least 32 bytes"));
    }

    let net = resolve_network(network)?;

    let account_id = zip32::AccountId::try_from(account)
        .map_err(|_| PyValueError::new_err("invalid account index"))?;

    let usk = UnifiedSpendingKey::from_seed(&net, &seed, account_id)
        .map_err(|e| PyValueError::new_err(format!("key derivation failed: {e}")))?;

    let ufvk = usk.to_unified_full_viewing_key();
    let (ua, _di) = ufvk
        .default_address(UnifiedAddressRequest::SHIELDED)
        .map_err(|e| PyValueError::new_err(format!("address generation failed: {e}")))?;

    let address_str = ua.encode(&net);

    Ok(DerivedAddress {
        unified_address: address_str,
        network: network.to_string(),
        account,
    })
}

// ---- Module ----

/// Python bindings for librustzcash. Provides address parsing, ZIP-321 URI handling,
/// and HD key derivation via Zcash's official Rust libraries.
#[pymodule]
fn pyzcash(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("__version__", env!("CARGO_PKG_VERSION"))?;
    m.add_class::<AddressInfo>()?;
    m.add_class::<PaymentInfo>()?;
    m.add_class::<DerivedAddress>()?;
    m.add_function(wrap_pyfunction!(parse_address, m)?)?;
    m.add_function(wrap_pyfunction!(parse_payment_uri, m)?)?;
    m.add_function(wrap_pyfunction!(create_payment_uri, m)?)?;
    m.add_function(wrap_pyfunction!(derive_address, m)?)?;
    Ok(())
}
