from dataclasses import dataclass, field
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any

import yaml

DEFAULT_UDP_PORT = 6000


def _validate_ipv4(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"'{field_name}' must be an IPv4 address string")
    try:
        return str(IPv4Address(value))
    except ValueError as exc:
        raise ValueError(f"'{field_name}' is not a valid IPv4 address: {value!r}") from exc


def _validate_port(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"'{field_name}' must be an integer")
    if not (1 <= value <= 65535):
        raise ValueError(f"'{field_name}' must be between 1 and 65535, got {value}")
    return value


def _validate_positive_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"'{field_name}' must be a positive integer")
    if value <= 0:
        raise ValueError(f"'{field_name}' must be > 0, got {value}")
    return value


@dataclass(frozen=True)
class Neighbor:
    ip: str
    udp_port: int
    cost: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "ip", _validate_ipv4(self.ip, "neighbor.ip"))
        object.__setattr__(self, "udp_port", _validate_port(self.udp_port, "neighbor.udp_port"))
        object.__setattr__(self, "cost", _validate_positive_int(self.cost, "neighbor.cost"))


@dataclass(frozen=True)
class Config:
    virtual_ip: str
    udp_port: int = DEFAULT_UDP_PORT
    neighbors: dict[str, Neighbor] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "virtual_ip", _validate_ipv4(self.virtual_ip, "virtual_ip"))
        object.__setattr__(self, "udp_port", _validate_port(self.udp_port, "udp_port"))


def _parse_neighbor(raw: Any, key: str) -> Neighbor:
    if not isinstance(raw, dict):
        raise TypeError(f"'neighbors[{key}]' must be a mapping")
    for required in ("ip", "port", "cost"):
        if required not in raw:
            raise ValueError(f"'neighbors[{key}]' is missing required field '{required}'")
    return Neighbor(
        ip=raw["ip"],
        udp_port=raw["port"],
        cost=raw["cost"],
    )


def load_config(path: str | Path) -> Config:
    config_path = Path(path)
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ValueError(f"Invalid YAML in config file: {exc}") from exc

    if not isinstance(data, dict):
        raise TypeError("Config file must contain a YAML mapping at the root")

    if "virtual_ip" not in data:
        raise ValueError("Config is missing required field 'virtual_ip'")

    udp_port = data.get("udp_port", DEFAULT_UDP_PORT)

    raw_neighbors = data.get("neighbors", {})
    if raw_neighbors is None:
        raw_neighbors = {}
    if not isinstance(raw_neighbors, dict):
        raise TypeError("'neighbors' must be a dict")

    neighbors = {key: _parse_neighbor(item, key) for key, item in raw_neighbors.items()}

    return Config(
        virtual_ip=data["virtual_ip"],
        udp_port=udp_port,
        neighbors=neighbors,
    )
