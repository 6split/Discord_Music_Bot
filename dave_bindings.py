"""ctypes bindings for Discord DAVE (libdave) reference implementation.

This module wraps a minimal set of libdave APIs for:
- session initialization
- persistent public key generation/export
- MLS key exchange
- RTP payload encryption/decryption

Because libdave ABI names can vary between versions, this wrapper supports
multiple candidate symbol names and optional caller-provided overrides.
"""

from __future__ import annotations

import ctypes
import ctypes.util
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence

# Common C aliases
c_size_t_p = ctypes.POINTER(ctypes.c_size_t)


class DaveBindingError(RuntimeError):
    """Raised for wrapper-level binding/load errors."""


class DaveOperationError(RuntimeError):
    """Raised when libdave returns a non-success code."""

    def __init__(self, operation: str, error_code: int) -> None:
        super().__init__(f"{operation} failed with libdave error code {error_code}")
        self.operation = operation
        self.error_code = error_code


@dataclass(frozen=True)
class DaveConfig:
    """Session config passed to libdave.

    This mirrors a minimal C config shape with fixed-width integer fields often
    used by media crypto libraries. Adjust this struct to your concrete libdave
    build if required.
    """

    user_id: int
    device_id: int
    epoch: int = 0


class _CDaveConfig(ctypes.Structure):
    _fields_ = [
        ("user_id", ctypes.c_uint64),
        ("device_id", ctypes.c_uint64),
        ("epoch", ctypes.c_uint64),
    ]


class DaveSessionHandle(ctypes.Structure):
    """Opaque C handle."""


DaveSessionHandlePtr = ctypes.POINTER(DaveSessionHandle)


class _Symbols:
    SESSION_INIT = "session_init"
    SESSION_FREE = "session_free"
    GEN_PERSISTENT_PUBKEY = "generate_persistent_public_key"
    EXPORT_PERSISTENT_PUBKEY = "export_persistent_public_key"
    MLS_KEY_EXCHANGE = "mls_key_exchange"
    RTP_ENCRYPT = "encrypt_rtp_payload"
    RTP_DECRYPT = "decrypt_rtp_payload"


DEFAULT_SYMBOL_CANDIDATES: Mapping[str, Sequence[str]] = {
    _Symbols.SESSION_INIT: (
        "dave_session_init",
        "dave_init_session",
    ),
    _Symbols.SESSION_FREE: (
        "dave_session_free",
        "dave_free_session",
    ),
    _Symbols.GEN_PERSISTENT_PUBKEY: (
        "dave_generate_persistent_public_key",
        "dave_persistent_public_key_generate",
    ),
    _Symbols.EXPORT_PERSISTENT_PUBKEY: (
        "dave_export_persistent_public_key",
        "dave_persistent_public_key_export",
    ),
    _Symbols.MLS_KEY_EXCHANGE: (
        "dave_mls_key_exchange",
        "dave_mls_handle_message",
    ),
    _Symbols.RTP_ENCRYPT: (
        "dave_encrypt_rtp_payload",
        "dave_rtp_encrypt",
    ),
    _Symbols.RTP_DECRYPT: (
        "dave_decrypt_rtp_payload",
        "dave_rtp_decrypt",
    ),
}


class DaveLib:
    """High-level Python wrapper over libdave."""

    def __init__(
        self,
        library_path: Optional[str] = None,
        symbol_overrides: Optional[Mapping[str, str]] = None,
    ) -> None:
        self._lib = self._load_library(library_path)
        self._funcs = self._bind_functions(symbol_overrides or {})

    @staticmethod
    def _load_library(library_path: Optional[str]) -> ctypes.CDLL:
        if library_path:
            lib_path = Path(library_path)
            if not lib_path.exists():
                raise DaveBindingError(f"libdave not found at: {library_path}")
            return ctypes.CDLL(str(lib_path))

        discovered = ctypes.util.find_library("dave")
        if not discovered:
            raise DaveBindingError(
                "Unable to find libdave via system lookup. "
                "Pass `library_path` explicitly."
            )
        return ctypes.CDLL(discovered)

    def _resolve_symbol(
        self,
        logical_name: str,
        overrides: Mapping[str, str],
    ) -> ctypes._CFuncPtr:
        candidates: Iterable[str]
        if logical_name in overrides:
            candidates = (overrides[logical_name],)
        else:
            candidates = DEFAULT_SYMBOL_CANDIDATES[logical_name]

        for symbol_name in candidates:
            func = getattr(self._lib, symbol_name, None)
            if func is not None:
                return func

        candidate_text = ", ".join(candidates)
        raise DaveBindingError(
            f"Could not resolve libdave symbol for '{logical_name}'. "
            f"Tried: {candidate_text}"
        )

    def _bind_functions(self, overrides: Mapping[str, str]) -> Dict[str, ctypes._CFuncPtr]:
        funcs: Dict[str, ctypes._CFuncPtr] = {}

        init_fn = self._resolve_symbol(_Symbols.SESSION_INIT, overrides)
        init_fn.argtypes = [ctypes.POINTER(DaveSessionHandlePtr), ctypes.POINTER(_CDaveConfig)]
        init_fn.restype = ctypes.c_int
        funcs[_Symbols.SESSION_INIT] = init_fn

        free_fn = self._resolve_symbol(_Symbols.SESSION_FREE, overrides)
        free_fn.argtypes = [DaveSessionHandlePtr]
        free_fn.restype = ctypes.c_int
        funcs[_Symbols.SESSION_FREE] = free_fn

        gen_pub_fn = self._resolve_symbol(_Symbols.GEN_PERSISTENT_PUBKEY, overrides)
        gen_pub_fn.argtypes = [DaveSessionHandlePtr]
        gen_pub_fn.restype = ctypes.c_int
        funcs[_Symbols.GEN_PERSISTENT_PUBKEY] = gen_pub_fn

        export_pub_fn = self._resolve_symbol(_Symbols.EXPORT_PERSISTENT_PUBKEY, overrides)
        export_pub_fn.argtypes = [
            DaveSessionHandlePtr,
            ctypes.POINTER(ctypes.c_uint8),
            c_size_t_p,
        ]
        export_pub_fn.restype = ctypes.c_int
        funcs[_Symbols.EXPORT_PERSISTENT_PUBKEY] = export_pub_fn

        mls_kex_fn = self._resolve_symbol(_Symbols.MLS_KEY_EXCHANGE, overrides)
        mls_kex_fn.argtypes = [
            DaveSessionHandlePtr,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            c_size_t_p,
        ]
        mls_kex_fn.restype = ctypes.c_int
        funcs[_Symbols.MLS_KEY_EXCHANGE] = mls_kex_fn

        encrypt_fn = self._resolve_symbol(_Symbols.RTP_ENCRYPT, overrides)
        encrypt_fn.argtypes = [
            DaveSessionHandlePtr,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            c_size_t_p,
        ]
        encrypt_fn.restype = ctypes.c_int
        funcs[_Symbols.RTP_ENCRYPT] = encrypt_fn

        decrypt_fn = self._resolve_symbol(_Symbols.RTP_DECRYPT, overrides)
        decrypt_fn.argtypes = [
            DaveSessionHandlePtr,
            ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_uint8),
            ctypes.c_size_t,
            ctypes.POINTER(ctypes.c_uint8),
            c_size_t_p,
        ]
        decrypt_fn.restype = ctypes.c_int
        funcs[_Symbols.RTP_DECRYPT] = decrypt_fn

        return funcs

    def create_session(self, config: DaveConfig) -> "DaveSession":
        c_config = _CDaveConfig(
            user_id=ctypes.c_uint64(config.user_id),
            device_id=ctypes.c_uint64(config.device_id),
            epoch=ctypes.c_uint64(config.epoch),
        )
        handle = DaveSessionHandlePtr()
        result = self._funcs[_Symbols.SESSION_INIT](ctypes.byref(handle), ctypes.byref(c_config))
        if result != 0 or not handle:
            raise DaveOperationError("session_init", int(result))
        return DaveSession(self, handle)


class DaveSession:
    """Owns an opaque libdave session pointer."""

    def __init__(self, dave: DaveLib, handle: DaveSessionHandlePtr) -> None:
        self._dave = dave
        self._handle = handle
        self._closed = False

    def close(self) -> None:
        if self._closed:
            return
        result = self._dave._funcs[_Symbols.SESSION_FREE](self._handle)
        self._closed = True
        if result != 0:
            raise DaveOperationError("session_free", int(result))

    def __enter__(self) -> "DaveSession":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def generate_persistent_public_key(self) -> bytes:
        result = self._dave._funcs[_Symbols.GEN_PERSISTENT_PUBKEY](self._handle)
        if result != 0:
            raise DaveOperationError("generate_persistent_public_key", int(result))
        return self.export_persistent_public_key()

    def export_persistent_public_key(self, initial_capacity: int = 64) -> bytes:
        return self._call_bytes_out(
            _Symbols.EXPORT_PERSISTENT_PUBKEY,
            (),
            operation_name="export_persistent_public_key",
            initial_capacity=initial_capacity,
        )

    def mls_key_exchange(self, peer_message: bytes, initial_capacity: int = 1024) -> bytes:
        return self._call_bytes_out(
            _Symbols.MLS_KEY_EXCHANGE,
            (peer_message,),
            operation_name="mls_key_exchange",
            initial_capacity=initial_capacity,
        )

    def encrypt_rtp_payload(self, ssrc: int, payload: bytes, initial_capacity: Optional[int] = None) -> bytes:
        capacity = initial_capacity if initial_capacity is not None else len(payload) + 64
        return self._call_bytes_out(
            _Symbols.RTP_ENCRYPT,
            (ssrc, payload),
            operation_name="encrypt_rtp_payload",
            initial_capacity=capacity,
        )

    def decrypt_rtp_payload(self, ssrc: int, payload: bytes, initial_capacity: Optional[int] = None) -> bytes:
        capacity = initial_capacity if initial_capacity is not None else len(payload)
        return self._call_bytes_out(
            _Symbols.RTP_DECRYPT,
            (ssrc, payload),
            operation_name="decrypt_rtp_payload",
            initial_capacity=max(1, capacity),
        )

    def _call_bytes_out(
        self,
        symbol: str,
        positional_inputs: Sequence[object],
        operation_name: str,
        initial_capacity: int,
        max_attempts: int = 4,
    ) -> bytes:
        if self._closed:
            raise DaveBindingError("Session is closed")

        if initial_capacity <= 0:
            raise ValueError("initial_capacity must be > 0")

        fn = self._dave._funcs[symbol]
        capacity = initial_capacity

        for _ in range(max_attempts):
            out_buf = (ctypes.c_uint8 * capacity)()
            out_len = ctypes.c_size_t(capacity)

            marshaled_args = []
            for item in positional_inputs:
                if isinstance(item, bytes):
                    in_arr = (ctypes.c_uint8 * len(item)).from_buffer_copy(item)
                    marshaled_args.extend([in_arr, ctypes.c_size_t(len(item))])
                elif isinstance(item, int):
                    marshaled_args.append(ctypes.c_uint32(item))
                else:
                    raise TypeError(f"Unsupported input type for C marshaling: {type(item)!r}")

            result = fn(self._handle, *marshaled_args, out_buf, ctypes.byref(out_len))

            if result == 0:
                return bytes(out_buf[: out_len.value])

            if out_len.value > capacity:
                capacity = int(out_len.value)
                continue

            raise DaveOperationError(operation_name, int(result))

        raise DaveBindingError(
            f"{operation_name} exceeded buffer resize attempts; last capacity={capacity}"
        )


__all__ = [
    "DaveBindingError",
    "DaveConfig",
    "DaveLib",
    "DaveOperationError",
    "DaveSession",
]
