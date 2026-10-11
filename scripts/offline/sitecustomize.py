"""Deny Python network connections during explicitly offline validation."""

import os
import sys


def deny_network(event: str, _arguments: tuple[object, ...]) -> None:
    if event in {"socket.connect", "socket.getaddrinfo", "socket.gethostbyname"}:
        raise RuntimeError("Network access is disabled for fixture validation")


if os.environ.get("CAM_OFFLINE") == "1":
    sys.addaudithook(deny_network)
