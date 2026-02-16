"""Cloud platform detection and instance metadata retrieval."""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

TIMEOUT = 2  # seconds

GCP_BASE = "http://metadata.google.internal/computeMetadata/v1"
GCP_HEADERS = {"Metadata-Flavor": "Google"}

AWS_BASE = "http://169.254.169.254"
AWS_TOKEN_URL = f"{AWS_BASE}/latest/api/token"
AWS_META_BASE = f"{AWS_BASE}/latest/meta-data"

_cached_platform: Optional[str] = None


def _probe_gcp() -> bool:
    try:
        r = httpx.get(f"{GCP_BASE}/", headers=GCP_HEADERS, timeout=TIMEOUT)
        return r.status_code == 200
    except Exception:
        return False


def _probe_aws() -> bool:
    try:
        r = httpx.put(
            AWS_TOKEN_URL,
            headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
            timeout=TIMEOUT,
        )
        return r.status_code == 200
    except Exception:
        return False


def detect_platform() -> Optional[str]:
    """Detect cloud platform by probing metadata endpoints. Result is cached."""
    global _cached_platform
    if _cached_platform is not None:
        return _cached_platform

    if _probe_gcp():
        _cached_platform = "gcp"
    elif _probe_aws():
        _cached_platform = "aws"

    return _cached_platform


def _extract_last_segment(path: str) -> str:
    """Extract last segment from a fully qualified GCP resource path."""
    return path.strip().rsplit("/", 1)[-1]


def _gcp_get(path: str) -> str:
    r = httpx.get(f"{GCP_BASE}{path}", headers=GCP_HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text.strip()


def get_gcp_metadata() -> dict:
    instance_id = _gcp_get("/instance/id")
    zone = _extract_last_segment(_gcp_get("/instance/zone"))
    machine_type = _extract_last_segment(_gcp_get("/instance/machine-type"))

    # Enumerate network interfaces
    iface_list = _gcp_get("/instance/network-interfaces/")
    interfaces = []
    for index in iface_list.strip().splitlines():
        index = index.strip().rstrip("/")
        if not index:
            continue
        base = f"/instance/network-interfaces/{index}"
        private_ip = _gcp_get(f"{base}/ip")
        network = _extract_last_segment(_gcp_get(f"{base}/network"))
        try:
            public_ip = _gcp_get(f"{base}/access-configs/0/external-ip")
        except Exception:
            public_ip = None

        interfaces.append({
            "private_ip": private_ip,
            "public_ip": public_ip,
            "network": network,
        })

    return {
        "cloud_platform": "gcp",
        "instance_id": instance_id,
        "region": zone,
        "machine_type": machine_type,
        "network_interfaces": interfaces,
    }


def _aws_token() -> str:
    r = httpx.put(
        AWS_TOKEN_URL,
        headers={"X-aws-ec2-metadata-token-ttl-seconds": "21600"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.text.strip()


def _aws_get(path: str, token: str) -> str:
    r = httpx.get(
        f"{AWS_META_BASE}{path}",
        headers={"X-aws-ec2-metadata-token": token},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.text.strip()


def get_aws_metadata() -> dict:
    token = _aws_token()
    instance_id = _aws_get("/instance-id", token)
    region = _aws_get("/placement/availability-zone", token)
    machine_type = _aws_get("/instance-type", token)

    # Enumerate network interfaces by MAC
    macs_raw = _aws_get("/network/interfaces/macs/", token)
    interfaces = []
    for mac in macs_raw.strip().splitlines():
        mac = mac.strip().rstrip("/")
        if not mac:
            continue
        base = f"/network/interfaces/macs/{mac}"
        private_ip = _aws_get(f"{base}/local-ipv4s", token)
        vpc_id = _aws_get(f"{base}/vpc-id", token)
        try:
            public_ip = _aws_get(f"{base}/public-ipv4s", token)
        except Exception:
            public_ip = None

        interfaces.append({
            "private_ip": private_ip,
            "public_ip": public_ip,
            "network": vpc_id,
        })

    return {
        "cloud_platform": "aws",
        "instance_id": instance_id,
        "region": region,
        "machine_type": machine_type,
        "network_interfaces": interfaces,
    }


def get_metadata() -> Optional[dict]:
    """Return instance metadata for the detected platform, or None."""
    platform = detect_platform()
    if platform == "gcp":
        return get_gcp_metadata()
    elif platform == "aws":
        return get_aws_metadata()
    return None
