"""Phone-to-phone mesh: offline chat and distress relay over Bluetooth.

The network is the first thing a landslide takes. Everything in this package is designed
to work without one.
"""
from .node import MeshNode, NodeStats
from .protocol import DEFAULT_TTL, MeshMessage, make_sos
from .transport import BleTransport, LoopbackRadio, LossyRadio, MeshRunner, Transport

__all__ = [
    "MeshMessage", "make_sos", "DEFAULT_TTL",
    "MeshNode", "NodeStats",
    "Transport", "LoopbackRadio", "LossyRadio", "BleTransport", "MeshRunner",
]
