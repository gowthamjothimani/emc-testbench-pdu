import os
import time
import queue
import threading
from typing import Optional
import can


class CANCommError(Exception):
    """Raised for CAN communication failures (send error, bus error, etc.)."""


class _QueueListener(can.Listener):

    def __init__(self, rx_queue: "queue.Queue[can.Message]", rx_id: int):
        super().__init__()
        self._queue = rx_queue
        self._rx_id = rx_id

    def on_message_received(self, msg: can.Message):
        if msg.arbitration_id == self._rx_id:
            self._queue.put(msg)


class CANCommunication:
    def __init__(self, channel: str = "can1", bitrate: int = 250000,
                 tx_id: int = 0x000C0100, rx_id: int = 0x000C0000,
                 default_timeout: float = 1.0, retry_count: int = 3):
        self.channel = channel
        self.bitrate = bitrate
        self.tx_id = tx_id
        self.rx_id = rx_id
        self.default_timeout = default_timeout
        self.retry_count = retry_count

        self.bus: Optional["can.BusABC"] = None
        self.notifier: Optional[can.Notifier] = None
        self._rx_queue: "queue.Queue[can.Message]" = queue.Queue()
        self._send_lock = threading.Lock()

        self.connected: bool = False
        self.last_error: Optional[str] = None

    def interface_exists(self) -> bool:
        return os.path.exists(f"/sys/class/net/{self.channel}")

    def interface_is_up(self) -> bool:
        try:
            with open(f"/sys/class/net/{self.channel}/operstate") as fh:
                state = fh.read().strip()
            # CAN interfaces frequently report 'unknown' even when up.
            return state in ("up", "unknown")
        except OSError:
            return False

    def connect(self) -> bool:
        if not self.interface_exists():
            self.last_error = f"CAN interface '{self.channel}' does not exist"
            print(self.last_error)
            self.connected = False
            return False

        if not self.interface_is_up():
            print(
                "CAN interface '%s' does not report 'up' -- attempting to "
                "open it anyway", self.channel,
            )

        try:
            self.bus = can.interface.Bus(channel=self.channel, interface="socketcan")
        except Exception as exc:
            self.last_error = f"Failed to open {self.channel}: {exc}"
            print(self.last_error)
            self.connected = False
            return False

        self._start_receiver()
        self.connected = True
        self.last_error = None
        return True

    def disconnect(self):
        if self.notifier is not None:
            self.notifier.stop()
            self.notifier = None
        if self.bus is not None:
            try:
                self.bus.shutdown()
            except Exception as exc:
                print("Error shutting down CAN bus: %s", exc)
            self.bus = None
        self.connected = False

    def _start_receiver(self):
        if self.notifier is not None or self.bus is None:
            return
        listener = _QueueListener(self._rx_queue, self.rx_id)
        self.notifier = can.Notifier(self.bus, [listener])
        print(
            "CAN receiver started on %s (rx_id=0x%X, tx_id=0x%X)",
            self.channel, self.rx_id, self.tx_id,
        )

    def send_request(self, command_code: int, data: bytes = None, is_write: bool = False):
        if self.bus is None:
            raise CANCommError("CAN bus not connected (device removed / never opened)")

        code_lo = command_code & 0xFF
        code_hi = (command_code >> 8) & 0xFF
        payload = [code_lo, code_hi]
        if is_write:
            payload += list(data if data is not None else b"\x00\x00")

        msg = can.Message(arbitration_id=self.tx_id, data=payload, is_extended_id=True)

        try:
            self.bus.send(msg)
        except can.CanError as exc:
            self.last_error = f"CAN bus error sending 0x{command_code:04X}: {exc}"
            print(self.last_error)
            raise CANCommError(self.last_error) from exc
        except Exception as exc:
            self.last_error = f"CAN send failed (0x{command_code:04X}): {exc}"
            print(self.last_error)
            raise CANCommError(self.last_error) from exc

    def receive_response(self, command_code: int, timeout: float = None) -> Optional[bytes]:
        timeout = timeout if timeout is not None else self.default_timeout
        deadline = time.time() + timeout

        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            try:
                msg = self._rx_queue.get(timeout=remaining)
            except queue.Empty:
                return None

            data = bytes(msg.data)
            if len(data) < 2:
                continue  
            reply_code = data[0] | (data[1] << 8)
            if reply_code == command_code:
                return data[2:]

    def read_command(self, command_code: int, num_bytes: int = 2,
                      timeout: float = None) -> Optional[bytes]:
        last_exc = None
        for attempt in range(1, self.retry_count + 1):
            try:
                with self._send_lock:
                    self.send_request(command_code, is_write=False)
                    data = self.receive_response(command_code, timeout=timeout)
                if data is not None:
                    return data[:num_bytes]
                print(
                    "No response for read 0x%04X (attempt %d/%d)",
                    command_code, attempt, self.retry_count,
                )
            except CANCommError as exc:
                last_exc = exc
                print(
                    "Read 0x%04X failed (attempt %d/%d): %s",
                    command_code, attempt, self.retry_count, exc,
                )
        if last_exc:
            self.last_error = str(last_exc)
        return None

    def write_command(self, command_code: int, value: int, num_bytes: int = 2) -> bool:
        data = value.to_bytes(num_bytes, byteorder="little")
        last_exc = None
        for attempt in range(1, self.retry_count + 1):
            try:
                with self._send_lock:
                    self.send_request(command_code, data=data, is_write=True)
                return True
            except CANCommError as exc:
                last_exc = exc
                print(
                    "Write 0x%04X failed (attempt %d/%d): %s",
                    command_code, attempt, self.retry_count, exc,
                )
        if last_exc:
            self.last_error = str(last_exc)
        return False