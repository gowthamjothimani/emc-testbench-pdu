import os
import time
from typing import Optional


class CANCommError(Exception):
    """Raised when the CAN transport cannot be used."""


class CANCommunication:
    def __init__(self, channel: str, bitrate: int, tx_id: int, rx_id: int,
                 default_timeout: float = 1.0, retry_count: int = 3,
                 is_extended_id: Optional[bool] = None, **kwargs):
        self.channel = channel
        self.bitrate = bitrate
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.default_timeout = default_timeout
        self.retry_count = retry_count
        self.is_extended_id = True if is_extended_id is None else is_extended_id
        self.last_error: Optional[str] = None
        self.bus = None

    def interface_exists(self) -> bool:
        return os.path.isdir(f"/sys/class/net/{self.channel}")

    def connect(self) -> bool:
        self.last_error = None
        if not self.interface_exists():
            self.last_error = f"CAN interface '{self.channel}' not found"
            return False

        try:
            import can  # type: ignore
        except ImportError as exc:
            self.last_error = f"python-can is not installed: {exc}"
            return False

        try:
            bus_factory = getattr(can, "Bus", None)
            if bus_factory is None:
                interface_mod = getattr(can, "interface", None)
                if interface_mod is not None:
                    bus_factory = getattr(interface_mod, "Bus", None)
            if bus_factory is None:
                bus_mod = getattr(can, "bus", None)
                if bus_mod is not None:
                    bus_factory = getattr(bus_mod, "Bus", None)
            if bus_factory is None:
                raise AttributeError("python-can installation does not expose a Bus factory")

            self.bus = bus_factory(channel=self.channel, interface="socketcan")
            return True
        except Exception as exc:
            self.last_error = str(exc)
            self.bus = None
            return False

    def disconnect(self) -> None:
        if self.bus is not None:
            try:
                self.bus.shutdown()
            except Exception:
                pass
        self.bus = None

    def read_command(self, address: int, length: int) -> Optional[bytes]:
        if self.bus is None:
            raise CANCommError(self.last_error or "CAN bus not connected")

        try:
            import can  # type: ignore
        except ImportError as exc:
            raise CANCommError(f"python-can is not installed: {exc}") from exc

        try:
            request_id = getattr(self, "tx_id", None)
            response_id = getattr(self, "rx_id", None)
            if request_id is None or response_id is None:
                request_id = address
                response_id = address

            msg = can.Message(
                arbitration_id=request_id,
                data=[0x00] * length,
                is_extended_id=getattr(self, "is_extended_id", True),
            )
            self.bus.send(msg)

            deadline = time.time() + self.default_timeout
            while time.time() < deadline:
                response = self.bus.recv(timeout=0.2)
                if response is None:
                    continue
                if getattr(response, "arbitration_id", None) != response_id:
                    continue
                return bytes(response.data[:length])
            return None
        except Exception as exc:
            try:
                msg = can.Message(
                    arbitration_id=request_id,
                    data=[0x00] * length,
                    is_extended_id=False,
                )
                self.bus.send(msg)
                deadline = time.time() + self.default_timeout
                while time.time() < deadline:
                    response = self.bus.recv(timeout=0.2)
                    if response is None:
                        continue
                    if getattr(response, "arbitration_id", None) != response_id:
                        continue
                    return bytes(response.data[:length])
                return None
            except Exception:
                raise CANCommError(str(exc)) from exc

    def write_command(self, address: int, value: int, length: int) -> bool:
        if self.bus is None:
            self.last_error = "CAN bus not connected"
            return False

        try:
            import can  # type: ignore
        except ImportError as exc:
            self.last_error = f"python-can is not installed: {exc}"
            return False

        try:
            data = value.to_bytes(length, byteorder="little", signed=False)
            msg = can.Message(
                arbitration_id=getattr(self, "tx_id", address),
                data=list(data),
                is_extended_id=getattr(self, "is_extended_id", True),
            )
            self.bus.send(msg)
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False
