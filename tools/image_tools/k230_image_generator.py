#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firmware Generation Tool for K230

This script generates firmware images with different encryption and signing options:
- AES-GCM + RSA-2048
- SM4-CBC + SM2
- No encryption + SHA-256 hash

Refactored for better structure and maintainability.
"""

import os
import sys
import struct
import codecs
import argparse
import logging
import json
import secrets
from pathlib import Path
from typing import Tuple, Optional, Union, Dict, Any
from dataclasses import dataclass, field

# Cryptography libraries
import hashlib
import binascii
from Crypto.Cipher import AES
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from Crypto.Cipher import PKCS1_OAEP
from base64 import b64encode

# Chinese cryptographic libraries
from gmssl.sm4 import CryptSM4, SM4_ENCRYPT, SM4_DECRYPT
from gmssl import sm2, func
from gmssl import sm3


# ============================================================================
# Configuration Loading
# ============================================================================

def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """Load configuration from JSON file
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Dictionary containing configuration data
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        json.JSONDecodeError: If config file is not valid JSON
    """
    config_file = validate_file_exists(config_path)
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    logging.info(f"Loaded configuration from: {config_path}")
    return config_data


STAGE_SECTION_NAMES = ("spl", "firmware")


def get_top_level_config_section(
    config_data: Dict[str, Any],
    config_path: str,
    section_name: str,
) -> Optional[Dict[str, Any]]:
    section = config_data.get(section_name)
    if section is None:
        return None

    if not isinstance(section, dict):
        raise ValueError(f"Section '{section_name}' in {config_path} must be an object")

    return section


def select_stage_config(config_data: Dict[str, Any], config_path: str, section_name: Optional[str]) -> Dict[str, Any]:
    if section_name is None:
        return config_data

    stage_config = get_top_level_config_section(config_data, config_path, section_name)
    if stage_config is not None:
        return stage_config

    if any(section in config_data for section in STAGE_SECTION_NAMES):
        raise ValueError(f"Missing '{section_name}' section in {config_path}")

    return config_data


def hex_string_to_bytes(hex_str: str) -> bytes:
    """Convert hex string to bytes
    
    Args:
        hex_str: Hex string (with or without 0x prefix)
        
    Returns:
        Bytes object
    """
    # Remove 0x prefix if present
    if hex_str.startswith('0x'):
        hex_str = hex_str[2:]
    
    # Handle escaped hex format like \x00\x01...
    if '\\x' in hex_str:
        # Parse escaped hex format
        parts = hex_str.split('\\x')
        if parts[0] == '':
            parts = parts[1:]  # Remove empty first element
        return bytes(int(part, 16) for part in parts if part)
    
    # Handle regular hex string
    return bytes.fromhex(hex_str)


def bytes_to_hex_string(data: bytes) -> str:
    """Convert bytes to hex string for JSON serialization
    
    Args:
        data: Bytes to convert
        
    Returns:
        Hex string representation
    """
    return data.hex()


def optional_bytes_to_hex_string(data: Optional[bytes]) -> str:
    if data is None:
        return ""

    return bytes_to_hex_string(data)


def validate_exact_length(field_name: str, value: bytes, expected_length: int) -> None:
    if len(value) != expected_length:
        raise ValueError(
            f"{field_name} must be exactly {expected_length} bytes, got {len(value)} bytes"
        )


def validate_max_length(field_name: str, value: bytes, max_length: int) -> None:
    if len(value) > max_length:
        raise ValueError(
            f"{field_name} must be at most {max_length} bytes, got {len(value)} bytes"
        )


def require_dict(config_data: Dict[str, Any], section_name: str) -> Dict[str, Any]:
    section = config_data.get(section_name)
    if not isinstance(section, dict):
        raise ValueError(f"Missing required '{section_name}' section")

    return section


def parse_required_bytes(section: Dict[str, Any], section_name: str, key: str) -> bytes:
    if key not in section:
        raise ValueError(f"Missing required field '{section_name}.{key}'")

    value = section[key]
    if not isinstance(value, str):
        raise ValueError(f"Field '{section_name}.{key}' must be a string")

    if value == "":
        raise ValueError(f"Field '{section_name}.{key}' must not be empty")

    try:
        return hex_string_to_bytes(value)
    except Exception as exc:
        raise ValueError(f"Field '{section_name}.{key}' is not valid hex data") from exc


def parse_optional_bytes(section: Dict[str, Any], section_name: str, key: str, default: bytes = b"") -> bytes:
    if key not in section:
        return default

    value = section[key]
    if not isinstance(value, str):
        raise ValueError(f"Field '{section_name}.{key}' must be a string")

    try:
        return hex_string_to_bytes(value)
    except Exception as exc:
        raise ValueError(f"Field '{section_name}.{key}' is not valid hex data") from exc


def resolve_stage_iv_with_rom_policy(
    section: Dict[str, Any],
    section_name: str,
    key: str,
    rom_iv: bytes,
    use_rom_iv: bool,
    stage_name: Optional[str],
) -> bytes:
    if not use_rom_iv:
        return parse_required_bytes(section, section_name, key)

    if key not in section:
        return rom_iv

    stage_label = stage_name if stage_name is not None else "default"
    value = section[key]
    if not isinstance(value, str):
        logging.warning(
            "Ignoring %s.%s for stage '%s' and using the fixed BROM IV",
            section_name,
            key,
            stage_label,
        )
        return rom_iv

    try:
        configured_iv = hex_string_to_bytes(value)
    except Exception:
        logging.warning(
            "Ignoring invalid %s.%s for stage '%s' and using the fixed BROM IV",
            section_name,
            key,
            stage_label,
        )
        return rom_iv

    if configured_iv != rom_iv:
        logging.warning(
            "Overriding %s.%s for stage '%s' with the fixed BROM IV",
            section_name,
            key,
            stage_label,
        )

    return rom_iv


def parse_required_string_or_hex(section: Dict[str, Any], section_name: str, key: str) -> bytes:
    if key not in section:
        raise ValueError(f"Missing required field '{section_name}.{key}'")

    value = section[key]
    if isinstance(value, str):
        if value == "":
            raise ValueError(f"Field '{section_name}.{key}' must not be empty")
        return value.encode("utf-8")

    raise ValueError(f"Field '{section_name}.{key}' must be a string")


def parse_required_int(section: Dict[str, Any], section_name: str, key: str) -> int:
    if key not in section:
        raise ValueError(f"Missing required field '{section_name}.{key}'")

    value = section[key]
    if isinstance(value, int):
        return value

    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError as exc:
            raise ValueError(f"Field '{section_name}.{key}' is not a valid integer") from exc

    raise ValueError(f"Field '{section_name}.{key}' must be an integer or integer string")


def parse_optional_int(section: Dict[str, Any], section_name: str, key: str) -> Optional[int]:
    if key not in section:
        return None

    return parse_required_int(section, section_name, key)


def parse_optional_reference(section: Dict[str, Any], section_name: str, key: str) -> Optional[str]:
    if key not in section:
        return None

    value = section[key]
    if not isinstance(value, str):
        raise ValueError(f"Field '{section_name}.{key}' must be a string")
    if value == "":
        raise ValueError(f"Field '{section_name}.{key}' must not be empty")

    return value


def resolve_config_reference_path(config_path: str, reference: str) -> Path:
    candidate = Path(reference).expanduser()
    if candidate.is_absolute():
        return validate_file_exists(str(candidate))

    search_roots = [Path(config_path).resolve().parent]

    for env_var in ("SDK_BOARD_DIR", "SDK_SRC_ROOT_DIR"):
        env_path = os.getenv(env_var)
        if env_path:
            root = Path(env_path).expanduser()
            if root.is_dir():
                search_roots.append(root)

    search_roots.append(Path.cwd())

    for root in search_roots:
        resolved = root / candidate
        if resolved.exists() and resolved.is_file():
            return resolved.resolve()

    raise ValueError(f"Referenced file not exists {reference}")


def import_rsa_key_from_file(config_path: str, reference: str, require_private: bool) -> RSA.RsaKey:
    key_bytes = resolve_config_reference_path(config_path, reference).read_bytes()
    imported_key = RSA.import_key(key_bytes)

    if require_private and not imported_key.has_private():
        raise ValueError(f"RSA key file '{reference}' does not contain a private key")

    return imported_key


def apply_rsa_key_material_from_file(
    config: 'FirmwareConfig',
    rsa_config: Dict[str, Any],
    config_path: str,
) -> None:
    public_key_ref = parse_optional_reference(rsa_config, 'rsa', 'public_key_file')
    private_key_ref = parse_optional_reference(rsa_config, 'rsa', 'private_key_file')

    public_key = import_rsa_key_from_file(config_path, public_key_ref, require_private=False) if public_key_ref else None
    private_key = import_rsa_key_from_file(config_path, private_key_ref, require_private=True) if private_key_ref else None

    if public_key is not None:
        file_modulus = public_key.n.to_bytes((public_key.n.bit_length() + 7) // 8, byteorder='big')
        file_exponent = hex(public_key.e)
        if config.RSA_MODULUS is None:
            config.RSA_MODULUS = file_modulus
        elif config.RSA_MODULUS != file_modulus:
            raise ValueError("Configured rsa.modulus does not match rsa.public_key_file")
        if config.RSA_EXPONENT is None:
            config.RSA_EXPONENT = file_exponent
        elif int(config.RSA_EXPONENT, 0) != public_key.e:
            raise ValueError("Configured rsa.exponent does not match rsa.public_key_file")
        if config.RSA_KEYSIZE is None:
            config.RSA_KEYSIZE = public_key.n.bit_length()

    if private_key is not None:
        file_modulus = private_key.n.to_bytes((private_key.n.bit_length() + 7) // 8, byteorder='big')
        file_exponent = hex(private_key.e)
        file_private_exponent = private_key.d.to_bytes((private_key.n.bit_length() + 7) // 8, byteorder='big')
        if config.RSA_MODULUS is None:
            config.RSA_MODULUS = file_modulus
        elif config.RSA_MODULUS != file_modulus:
            raise ValueError("Configured rsa.modulus does not match rsa.private_key_file")
        if config.RSA_EXPONENT is None:
            config.RSA_EXPONENT = file_exponent
        elif int(config.RSA_EXPONENT, 0) != private_key.e:
            raise ValueError("Configured rsa.exponent does not match rsa.private_key_file")
        if config.RSA_PRIVATE_EXPONENT is None:
            config.RSA_PRIVATE_EXPONENT = file_private_exponent
        elif config.RSA_PRIVATE_EXPONENT != file_private_exponent:
            raise ValueError("Configured rsa.private_exponent does not match rsa.private_key_file")
        if config.RSA_KEYSIZE is None:
            config.RSA_KEYSIZE = private_key.n.bit_length()


# ============================================================================
# Configuration Constants
# ============================================================================

ROM_AES_IV = b'\x9f\xf1\x85\x63\xb9\x78\xec\x28\x1b\x3f\x27\x94'
ROM_SM4_IV = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
AES_GCM_IV_LEN = 12
SM4_CBC_IV_LEN = 16

@dataclass
class FirmwareConfig:
    """Configuration constants for firmware generation"""

    # Firmware format constants
    MAGIC_BYTES: bytes = b'\x4b\x32\x33\x30'  # "K230"
    HEADER_SIZE: int = 516
    
    # Encryption type constants
    ENCRYPTION_NONE: int = 0
    ENCRYPTION_SM4: int = 1
    ENCRYPTION_AES: int = 2

    # Firmware Version
    VERSION_BYTES: bytes = b'\x00\x00\x00\x00'
    
    # AES-GCM parameters
    AES_IV: Optional[bytes] = None
    AES_USE_EMBEDDED_IV: bool = False
    AES_KEY: Optional[bytes] = None
    AES_AUTH_DATA: bytes = b''
    
    # RSA-2048 parameters
    RSA_KEYSIZE: Optional[int] = None
    RSA_MODULUS: Optional[bytes] = None
    RSA_EXPONENT: Optional[str] = None
    RSA_PRIVATE_EXPONENT: Optional[bytes] = None
    
    # SM4 parameters
    SM4_KEY: Optional[bytes] = None
    SM4_IV: Optional[bytes] = None
    SM4_USE_EMBEDDED_IV: bool = False
    
    # SM2 parameters
    SM2_PRIVATE_KEY: Optional[bytes] = None
    SM2_PUBLIC_KEY_X: Optional[bytes] = None
    SM2_PUBLIC_KEY_Y: Optional[bytes] = None
    SM2_RANDOM_K: Optional[bytes] = None
    SM2_ID: Optional[bytes] = None
    
    @classmethod
    def from_file(cls, config_path: str, section_name: Optional[str] = None) -> 'FirmwareConfig':
        """Create FirmwareConfig from JSON file
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            FirmwareConfig instance with values from file
        """
        config_data = select_stage_config(load_config_from_file(config_path), config_path, section_name)
        
        config = cls()

        if 'firmware' in config_data:
            firmware_config = config_data['firmware']
            if 'version_bytes' in firmware_config:
                config.VERSION_BYTES = hex_string_to_bytes(firmware_config['version_bytes'])
        
        if 'aes' in config_data:
            aes_config = config_data['aes']
            config.AES_IV = parse_optional_bytes(aes_config, 'aes', 'iv', default=None)
            config.AES_KEY = parse_optional_bytes(aes_config, 'aes', 'key', default=None)
            auth_data = parse_optional_bytes(aes_config, 'aes', 'auth_data', default=b'')
            config.AES_AUTH_DATA = auth_data if auth_data is not None else b''
        
        if 'rsa' in config_data:
            rsa_config = config_data['rsa']
            config.RSA_KEYSIZE = parse_optional_int(rsa_config, 'rsa', 'key_size')
            config.RSA_MODULUS = parse_optional_bytes(rsa_config, 'rsa', 'modulus', default=None)
            if 'exponent' in rsa_config:
                config.RSA_EXPONENT = str(rsa_config['exponent'])
            config.RSA_PRIVATE_EXPONENT = parse_optional_bytes(rsa_config, 'rsa', 'private_exponent', default=None)
            apply_rsa_key_material_from_file(config, rsa_config, config_path)
        
        if 'sm4' in config_data:
            sm4_config = config_data['sm4']
            config.SM4_KEY = parse_optional_bytes(sm4_config, 'sm4', 'key', default=None)
            config.SM4_IV = parse_optional_bytes(sm4_config, 'sm4', 'iv', default=None)
        
        if 'sm2' in config_data:
            sm2_config = config_data['sm2']
            config.SM2_PRIVATE_KEY = parse_optional_bytes(sm2_config, 'sm2', 'private_key', default=None)
            config.SM2_PUBLIC_KEY_X = parse_optional_bytes(sm2_config, 'sm2', 'public_key_x', default=None)
            config.SM2_PUBLIC_KEY_Y = parse_optional_bytes(sm2_config, 'sm2', 'public_key_y', default=None)
            config.SM2_RANDOM_K = parse_optional_bytes(sm2_config, 'sm2', 'random_k', default=None)
            if 'id' in sm2_config:
                config.SM2_ID = parse_required_string_or_hex(sm2_config, 'sm2', 'id')
        
        logging.info("Configuration loaded and applied successfully")
        return config

    @classmethod
    def from_file_for_encryption(
        cls,
        config_path: str,
        encryption_type: int,
        section_name: Optional[str] = None,
    ) -> 'FirmwareConfig':
        return cls.from_file_for_encryption_with_iv_policy(
            config_path,
            encryption_type,
            use_rom_iv=False,
            section_name=section_name,
        )

    @classmethod
    def from_file_for_encryption_with_iv_policy(
        cls,
        config_path: str,
        encryption_type: int,
        use_rom_iv: bool,
        section_name: Optional[str] = None,
    ) -> 'FirmwareConfig':
        config_data = select_stage_config(load_config_from_file(config_path), config_path, section_name)
        config = cls()

        if 'firmware' in config_data:
            firmware_config = require_dict(config_data, 'firmware')
            if 'version_bytes' in firmware_config:
                config.VERSION_BYTES = parse_optional_bytes(firmware_config, 'firmware', 'version_bytes')

        if encryption_type == cls.ENCRYPTION_AES:
            aes_config = require_dict(config_data, 'aes')
            rsa_config = require_dict(config_data, 'rsa')
            config.AES_USE_EMBEDDED_IV = not use_rom_iv

            if use_rom_iv:
                config.AES_IV = resolve_stage_iv_with_rom_policy(
                    aes_config,
                    'aes',
                    'iv',
                    ROM_AES_IV,
                    use_rom_iv,
                    section_name,
                )
            else:
                config.AES_IV = parse_optional_bytes(aes_config, 'aes', 'iv', default=None)
            config.AES_KEY = parse_required_bytes(aes_config, 'aes', 'key')
            auth_data = parse_optional_bytes(aes_config, 'aes', 'auth_data', default=b'')
            config.AES_AUTH_DATA = auth_data if auth_data is not None else b''

            config.RSA_KEYSIZE = parse_optional_int(rsa_config, 'rsa', 'key_size')
            config.RSA_MODULUS = parse_optional_bytes(rsa_config, 'rsa', 'modulus', default=None)
            rsa_exponent_value = parse_optional_int(rsa_config, 'rsa', 'exponent')
            if rsa_exponent_value is not None:
                if rsa_exponent_value <= 0 or rsa_exponent_value > 0xffffffff:
                    raise ValueError("Field 'rsa.exponent' must be in range 1..0xffffffff")
                config.RSA_EXPONENT = hex(rsa_exponent_value)
            config.RSA_PRIVATE_EXPONENT = parse_optional_bytes(rsa_config, 'rsa', 'private_exponent', default=None)
            apply_rsa_key_material_from_file(config, rsa_config, config_path)

        elif encryption_type == cls.ENCRYPTION_SM4:
            sm4_config = require_dict(config_data, 'sm4')
            sm2_config = require_dict(config_data, 'sm2')
            config.SM4_USE_EMBEDDED_IV = not use_rom_iv

            config.SM4_KEY = parse_required_bytes(sm4_config, 'sm4', 'key')
            if use_rom_iv:
                config.SM4_IV = resolve_stage_iv_with_rom_policy(
                    sm4_config,
                    'sm4',
                    'iv',
                    ROM_SM4_IV,
                    use_rom_iv,
                    section_name,
                )
            else:
                config.SM4_IV = parse_optional_bytes(sm4_config, 'sm4', 'iv', default=None)

            config.SM2_PRIVATE_KEY = parse_required_bytes(sm2_config, 'sm2', 'private_key')
            config.SM2_PUBLIC_KEY_X = parse_required_bytes(sm2_config, 'sm2', 'public_key_x')
            config.SM2_PUBLIC_KEY_Y = parse_required_bytes(sm2_config, 'sm2', 'public_key_y')
            config.SM2_RANDOM_K = parse_optional_bytes(sm2_config, 'sm2', 'random_k', default=None)
            config.SM2_ID = parse_required_string_or_hex(sm2_config, 'sm2', 'id')

        config.validate_for_encryption(encryption_type)
        logging.info("Configuration loaded and validated successfully")
        return config

    def validate_for_encryption(self, encryption_type: int) -> None:
        validate_exact_length('firmware.version_bytes', self.VERSION_BYTES, 4)

        if encryption_type == self.ENCRYPTION_NONE:
            return

        if encryption_type == self.ENCRYPTION_AES:
            if self.AES_IV is None and not self.AES_USE_EMBEDDED_IV:
                raise ValueError("Missing required field 'aes.iv'")
            if self.AES_KEY is None:
                raise ValueError("Missing required field 'aes.key'")
            if self.RSA_KEYSIZE is None:
                raise ValueError("Missing required field 'rsa.key_size'")
            if self.RSA_MODULUS is None:
                raise ValueError("Missing required field 'rsa.modulus'")
            if self.RSA_EXPONENT is None:
                raise ValueError("Missing required field 'rsa.exponent'")
            if self.RSA_PRIVATE_EXPONENT is None:
                raise ValueError("Missing required field 'rsa.private_exponent'")

            if self.AES_IV is not None:
                validate_exact_length('aes.iv', self.AES_IV, AES_GCM_IV_LEN)
            validate_exact_length('aes.key', self.AES_KEY, 32)
            validate_exact_length('rsa.modulus', self.RSA_MODULUS, 256)
            validate_exact_length('rsa.private_exponent', self.RSA_PRIVATE_EXPONENT, 256)

            rsa_exponent = int(self.RSA_EXPONENT, 0)
            if rsa_exponent <= 0 or rsa_exponent > 0xffffffff:
                raise ValueError("Field 'rsa.exponent' must be in range 1..0xffffffff")

        elif encryption_type == self.ENCRYPTION_SM4:
            if self.SM4_KEY is None:
                raise ValueError("Missing required field 'sm4.key'")
            if self.SM4_IV is None and not self.SM4_USE_EMBEDDED_IV:
                raise ValueError("Missing required field 'sm4.iv'")
            if self.SM2_PRIVATE_KEY is None:
                raise ValueError("Missing required field 'sm2.private_key'")
            if self.SM2_PUBLIC_KEY_X is None:
                raise ValueError("Missing required field 'sm2.public_key_x'")
            if self.SM2_PUBLIC_KEY_Y is None:
                raise ValueError("Missing required field 'sm2.public_key_y'")
            if self.SM2_ID is None:
                raise ValueError("Missing required field 'sm2.id'")

            validate_exact_length('sm4.key', self.SM4_KEY, 16)
            if self.SM4_IV is not None:
                validate_exact_length('sm4.iv', self.SM4_IV, SM4_CBC_IV_LEN)
            validate_exact_length('sm2.private_key', self.SM2_PRIVATE_KEY, 32)
            validate_exact_length('sm2.public_key_x', self.SM2_PUBLIC_KEY_X, 32)
            validate_exact_length('sm2.public_key_y', self.SM2_PUBLIC_KEY_Y, 32)
            if self.SM2_RANDOM_K is not None:
                validate_exact_length('sm2.random_k', self.SM2_RANDOM_K, 32)
            validate_max_length('sm2.id', self.SM2_ID, 512 - 32 * 4)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for JSON serialization
        
        Returns:
            Dictionary representation of configuration
        """
        return {
            'firmware': {
                'version_bytes': bytes_to_hex_string(self.VERSION_BYTES),
            },
            'aes': {
                'iv': optional_bytes_to_hex_string(self.AES_IV),
                'key': optional_bytes_to_hex_string(self.AES_KEY),
                'auth_data': bytes_to_hex_string(self.AES_AUTH_DATA)
            },
            'rsa': {
                'key_size': self.RSA_KEYSIZE if self.RSA_KEYSIZE is not None else 2048,
                'modulus': optional_bytes_to_hex_string(self.RSA_MODULUS),
                'exponent': self.RSA_EXPONENT if self.RSA_EXPONENT is not None else '',
                'private_exponent': optional_bytes_to_hex_string(self.RSA_PRIVATE_EXPONENT)
            },
            'sm4': {
                'key': optional_bytes_to_hex_string(self.SM4_KEY),
                'iv': optional_bytes_to_hex_string(self.SM4_IV)
            },
            'sm2': {
                'private_key': optional_bytes_to_hex_string(self.SM2_PRIVATE_KEY),
                'public_key_x': optional_bytes_to_hex_string(self.SM2_PUBLIC_KEY_X),
                'public_key_y': optional_bytes_to_hex_string(self.SM2_PUBLIC_KEY_Y),
                'id': self.SM2_ID.decode('utf-8', errors='ignore') if self.SM2_ID is not None else ''
            }
        }


# ============================================================================
# Utility Functions
# ============================================================================

def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration"""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def format_hex_bytes(data: bytes, prefix: str = "") -> str:
    """Format bytes as hex string with proper formatting"""
    hex_str = ''.join(f'\\x{byte:02x}' for byte in data)
    return f"{prefix}{hex_str}" if prefix else hex_str


def validate_file_exists(filepath: str) -> Path:
    """Validate that input file exists and return Path object"""
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {filepath}")
    if not path.is_file():
        raise ValueError(f"Input path is not a file: {filepath}")
    return path


def zeros(count: int) -> bytes:
    """Generate zero-filled bytes"""
    return b'\x00' * count


def generate_sm2_nonce_hex(sm2_crypt: sm2.CryptSM2) -> str:
    curve_order = int(sm2_crypt.ecc_table['n'], 16)
    nonce = secrets.randbelow(curve_order - 1) + 1

    return f"{nonce:0{sm2_crypt.para_len}x}"


def generate_aes_gcm_iv() -> bytes:
    return secrets.token_bytes(AES_GCM_IV_LEN)


def generate_sm4_cbc_iv() -> bytes:
    return secrets.token_bytes(SM4_CBC_IV_LEN)


# ============================================================================
# Encryption Classes
# ============================================================================

class AESEncryption:
    """AES-GCM-256 encryption implementation"""
    
    def __init__(self, config: FirmwareConfig):
        self.config = config
        self.key = config.AES_KEY
        self.auth_data = config.AES_AUTH_DATA

    def _resolve_iv(self) -> bytes:
        if self.config.AES_USE_EMBEDDED_IV:
            if self.config.AES_IV is not None:
                logging.warning("Ignoring configured aes.iv and generating a fresh AES-GCM IV per image")
            return generate_aes_gcm_iv()

        if self.config.AES_IV is None:
            raise ValueError("AES IV is not configured")

        return self.config.AES_IV
        
    def encrypt(self, data: bytes) -> Tuple[bytes, bytes, bytes]:
        """Encrypt data using AES-GCM-256
        
        Args:
            data: Data to encrypt
            
        Returns:
            Tuple of (iv, ciphertext, authentication_tag)
        """
        iv = self._resolve_iv()
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=iv)
        cipher.update(self.auth_data)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        
        logging.debug(f"AES-GCM encrypted {len(data)} bytes")
        logging.debug(f"Ciphertext: {format_hex_bytes(ciphertext, 'ciphertext: ')}")
        logging.debug(f"Tag: {format_hex_bytes(tag, 'tag: ')}")
        
        return iv, ciphertext, tag
    
    def decrypt(self, ciphertext: bytes, tag: bytes) -> bytes:
        """Decrypt data using AES-GCM-256
        
        Args:
            ciphertext: Encrypted data
            tag: Authentication tag
            
        Returns:
            Decrypted plaintext
        """
        if self.config.AES_IV is None:
            raise ValueError("AES IV is not configured")

        cipher = AES.new(self.key, AES.MODE_GCM, nonce=self.config.AES_IV)
        cipher.update(self.auth_data)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        
        logging.debug(f"AES-GCM decrypted {len(plaintext)} bytes")
        return plaintext


class SM4Encryption:
    """SM4-CBC encryption implementation"""
    
    def __init__(self, config: FirmwareConfig):
        self.config = config
        self.key = config.SM4_KEY
        self.crypt_sm4 = CryptSM4()

    def _resolve_iv(self) -> bytes:
        if self.config.SM4_USE_EMBEDDED_IV:
            if self.config.SM4_IV is not None:
                logging.warning("Ignoring configured sm4.iv and generating a fresh SM4-CBC IV per image")
            return generate_sm4_cbc_iv()

        if self.config.SM4_IV is None:
            raise ValueError("SM4 IV is not configured")

        return self.config.SM4_IV
        
    def encrypt(self, data: bytes) -> Tuple[bytes, bytes]:
        """Encrypt data using SM4-CBC
        
        Args:
            data: Data to encrypt
            
        Returns:
            Tuple of (iv, encrypted_data)
        """
        iv = self._resolve_iv()
        self.crypt_sm4.set_key(self.key, SM4_ENCRYPT)
        encrypted = self.crypt_sm4.crypt_cbc(iv, data)
        
        logging.debug(f"SM4-CBC encrypted {len(data)} bytes")
        logging.debug(f"Encrypted: {format_hex_bytes(encrypted, 'encryption: ')}")
        
        return iv, encrypted
    
    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data using SM4-CBC
        
        Args:
            data: Data to decrypt
            
        Returns:
            Decrypted data
        """
        if self.config.SM4_IV is None:
            raise ValueError("SM4 IV is not configured")

        self.crypt_sm4.set_key(self.key, SM4_DECRYPT)
        decrypted = self.crypt_sm4.crypt_cbc(self.config.SM4_IV, data)
        
        logging.debug(f"SM4-CBC decrypted {len(decrypted)} bytes")
        return decrypted


# ============================================================================
# Signature Classes
# ============================================================================

class RSASignature:
    """RSA-2048 signature implementation"""
    
    def __init__(self, config: FirmwareConfig):
        self.config = config
        self._setup_keys()
        
    def _setup_keys(self) -> None:
        """Setup RSA keys from configuration"""
        if self.config.RSA_MODULUS is None or self.config.RSA_EXPONENT is None or self.config.RSA_PRIVATE_EXPONENT is None:
            raise ValueError("RSA configuration is incomplete")

        modulus_hex = bytes.hex(self.config.RSA_MODULUS)
        self.modulus = int(modulus_hex, 16)
        self.exponent = int(self.config.RSA_EXPONENT, 16)
        
        private_hex = bytes.hex(self.config.RSA_PRIVATE_EXPONENT)
        self.private_exponent = int(private_hex, 16)
        
        # Create RSA key objects
        self.public_key = RSA.construct((self.modulus, self.exponent))
        self.private_key = RSA.construct((self.modulus, self.exponent, self.private_exponent))
        
    def sign(self, data: bytes) -> bytes:
        """Sign data using RSA-2048 with SHA256
        
        Args:
            data: Data to sign
            
        Returns:
            Signature bytes
        """
        digest = SHA256.new(data)
        signature = pkcs1_15.new(self.private_key).sign(digest)
        
        logging.debug(f"RSA signed {len(data)} bytes")
        logging.debug(f"Signature: {format_hex_bytes(signature, 'signature: ')}")
        
        return signature
    
    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify RSA signature
        
        Args:
            data: Original data
            signature: Signature to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        try:
            digest = SHA256.new(data)
            pkcs1_15.new(self.public_key).verify(digest, signature)
            logging.debug("RSA signature verification: valid")
            return True
        except (ValueError, TypeError):
            logging.debug("RSA signature verification: invalid")
            return False


class SM2Signature:
    """SM2 signature implementation"""
    
    def __init__(self, config: FirmwareConfig):
        self.config = config
        self._setup_keys()
        
    def _setup_keys(self) -> None:
        """Setup SM2 keys from configuration"""
        self.private_key_hex = codecs.encode(self.config.SM2_PRIVATE_KEY, 'hex').decode('ascii')
        self.public_key = self.config.SM2_PUBLIC_KEY_X + self.config.SM2_PUBLIC_KEY_Y
        self.public_key_hex = codecs.encode(self.public_key, 'hex').decode('ascii')
        self.id_hex = codecs.encode(self.config.SM2_ID, 'hex').decode('ascii')
        
    def sign(self, data: bytes) -> Tuple[bytes, bytes, bytes]:
        """Sign data using SM2
        
        Args:
            data: Data to sign
            
        Returns:
            Tuple of (signature, r_component, s_component)
        """
        sm2_crypt = sm2.CryptSM2(
            public_key=self.public_key_hex, 
            private_key=self.private_key_hex
        )

        if self.config.SM2_RANDOM_K is not None:
            logging.warning("Ignoring configured sm2.random_k and generating a fresh SM2 nonce from a CSPRNG")
        
        # Calculate Z value for SM2
        z = ('0080' + self.id_hex + sm2_crypt.ecc_table['a'] + 
             sm2_crypt.ecc_table['b'] + sm2_crypt.ecc_table['g'] + 
             sm2_crypt.public_key)
        z_bytes = binascii.a2b_hex(z)
        za = sm3.sm3_hash(func.bytes_to_list(z_bytes))
        
        # Calculate message hash
        m_prime = (za + data.hex()).encode('utf-8')
        e = sm3.sm3_hash(func.bytes_to_list(binascii.a2b_hex(m_prime)))
        sign_data = binascii.a2b_hex(e.encode('utf-8'))
        
        # Generate signature
        sign = sm2_crypt.sign(sign_data, generate_sm2_nonce_hex(sm2_crypt))
        r = sign[0:sm2_crypt.para_len]
        s = sign[sm2_crypt.para_len:]
        
        sign_bytes = binascii.a2b_hex(sign)
        r_bytes = binascii.a2b_hex(r)
        s_bytes = binascii.a2b_hex(s)
        
        logging.debug(f"SM2 signed {len(data)} bytes")
        logging.debug(f"Signature: {format_hex_bytes(sign_bytes, 'sign: ')}")
        logging.debug(f"R component: {format_hex_bytes(r_bytes, 'r: ')}")
        logging.debug(f"S component: {format_hex_bytes(s_bytes, 's: ')}")
        
        return sign_bytes, r_bytes, s_bytes
    
    def verify(self, data: bytes, signature: bytes) -> bool:
        """Verify SM2 signature
        
        Args:
            data: Original data
            signature: Signature to verify
            
        Returns:
            True if signature is valid, False otherwise
        """
        sm2_crypt = sm2.CryptSM2(
            public_key=self.public_key_hex, 
            private_key=self.private_key_hex
        )
        
        # Calculate Z value for SM2
        z = ('0080' + self.id_hex + sm2_crypt.ecc_table['a'] + 
             sm2_crypt.ecc_table['b'] + sm2_crypt.ecc_table['g'] + 
             sm2_crypt.public_key)
        z_bytes = binascii.a2b_hex(z)
        za = sm3.sm3_hash(func.bytes_to_list(z_bytes))
        
        # Calculate message hash
        m_prime = (za + data.hex()).encode('utf-8')
        e = sm3.sm3_hash(func.bytes_to_list(binascii.a2b_hex(m_prime)))
        sign_data = binascii.a2b_hex(e.encode('utf-8'))
        
        verify = sm2_crypt.verify(signature, sign_data)
        logging.debug(f"SM2 signature verification: {verify}")
        return verify


# ============================================================================
# Header Formatter Classes
# ============================================================================

class HeaderFormatter:
    """Base class for firmware header formatting"""
    
    def __init__(self, config: FirmwareConfig):
        self.config = config
        
    def write_header(self, output_file, **kwargs) -> None:
        """Write header to output file"""
        raise NotImplementedError("Subclasses must implement write_header")


class RSAHeaderFormatter(HeaderFormatter):
    """RSA firmware header formatter"""
    
    def write_header(self, output_file, modulus: int, exponent: int, signature: bytes) -> None:
        """Write RSA header to output file
        
        Args:
            output_file: Output file handle
            modulus: RSA modulus
            exponent: RSA exponent
            signature: RSA signature
        """
        # Write modulus (2048 bits)
        if self.config.RSA_MODULUS is None or self.config.RSA_EXPONENT is None:
            raise ValueError("RSA configuration is incomplete")

        modulus_bytes = self.config.RSA_MODULUS
        output_file.write(modulus_bytes)
        
        # Write exponent (4 bytes)
        exponent_bytes = int(self.config.RSA_EXPONENT, 0).to_bytes(4, byteorder=sys.byteorder, signed=True)
        output_file.write(exponent_bytes)
        
        # Write signature
        output_file.write(signature)
        
        # Calculate and log public key hash
        pubkey = modulus_bytes + exponent_bytes
        pub_hash = hashlib.sha256(pubkey).digest()
        logging.debug(f"RSA public key hash: {format_hex_bytes(pub_hash)}")


class SM2HeaderFormatter(HeaderFormatter):
    """SM2 firmware header formatter"""
    
    def write_header(self, output_file, r_component: bytes, s_component: bytes) -> None:
        """Write SM2 header to output file
        
        Args:
            output_file: Output file handle
            r_component: SM2 R component
            s_component: SM2 S component
        """
        # Write ID length
        if self.config.SM2_ID is None or self.config.SM2_PUBLIC_KEY_X is None or self.config.SM2_PUBLIC_KEY_Y is None:
            raise ValueError("SM2 configuration is incomplete")

        id_len = len(self.config.SM2_ID)
        id_len_bytes = id_len.to_bytes(4, byteorder=sys.byteorder, signed=True)
        output_file.write(id_len_bytes)
        
        # Write ID (padded to required size)
        id_padded = self.config.SM2_ID + zeros(512 - 32 * 4 - id_len)
        output_file.write(id_padded)
        
        # Write public key components
        output_file.write(self.config.SM2_PUBLIC_KEY_X)
        output_file.write(self.config.SM2_PUBLIC_KEY_Y)
        
        # Write signature components
        output_file.write(r_component)
        output_file.write(s_component)
        
        # Calculate and log public key hash
        pubkey = id_len_bytes + id_padded + self.config.SM2_PUBLIC_KEY_X + self.config.SM2_PUBLIC_KEY_Y
        pub_hash = sm3.sm3_hash(func.bytes_to_list(pubkey))
        pub_hash_bytes = binascii.a2b_hex(pub_hash)
        logging.debug(f"SM2 public key hash: {format_hex_bytes(pub_hash_bytes)}")


class HashHeaderFormatter(HeaderFormatter):
    """Hash-only firmware header formatter"""
    
    def write_header(self, output_file, hash_data: bytes) -> None:
        """Write hash header to output file
        
        Args:
            output_file: Output file handle
            hash_data: SHA-256 hash data
        """
        # Write hash data (32 bytes)
        output_file.write(hash_data)
        
        # Write padding (516 - 32 bytes)
        padding = zeros(self.config.HEADER_SIZE - 32)
        output_file.write(padding)


# ============================================================================
# Main Firmware Generator Class
# ============================================================================

class FirmwareGenerator:
    """Main firmware generation class"""

    def __init__(self, config: Optional[FirmwareConfig] = None):
        self.config = config or FirmwareConfig()
        self.encryption_handlers = {
            self.config.ENCRYPTION_NONE: self._handle_no_encryption,
            self.config.ENCRYPTION_SM4: self._handle_sm4_encryption,
            self.config.ENCRYPTION_AES: self._handle_aes_encryption
        }

    def generate_firmware(self, input_path: str, output_path: str, 
                         encryption_type: int) -> None:
        """Generate firmware with specified encryption type

        Args:
            input_path: Path to input firmware file
            output_path: Path to output firmware file
            encryption_type: Type of encryption to apply
        """
        # Validate input file
        input_file = validate_file_exists(input_path)

        # Read input data
        with open(input_file, 'rb') as f:
            input_data = f.read()

        input_data = self._add_version_to_data(input_data)

        # Process firmware
        processed_data, header_info = self.encryption_handlers[encryption_type](input_data)

        # Write output file
        self._write_firmware(output_path, processed_data, header_info)

        logging.info(f"Firmware generated successfully: {output_path}")
        logging.info(f"Encryption type: {encryption_type}")
        logging.info(f"Output size: {len(processed_data)} bytes")

    def _add_version_to_data(self, input_data: bytes) -> bytes:
        try:
            version_header = self.config.VERSION_BYTES
        except AttributeError:
            raise AttributeError("self.config.VERSION_BYTES must be defined to add version header.")

        modified_data = version_header + input_data
        return modified_data

    def _handle_no_encryption(self, data: bytes) -> Tuple[bytes, dict]:
        """Handle no encryption case"""
        logging.info("Processing with NO ENCRYPTION + SHA-256")

        # Calculate hash
        hash_data = hashlib.sha256(data).digest()
        logging.debug(f"SHA-256 hash: {format_hex_bytes(hash_data, 'mesg_hash: ')}")
        
        header_info = {
            'type': 'hash',
            'hash_data': hash_data,
            'data_length': len(data),
            'encryption_type': self.config.ENCRYPTION_NONE
        }
        
        return data, header_info
    
    def _handle_sm4_encryption(self, data: bytes) -> Tuple[bytes, dict]:
        """Handle SM4-CBC + SM2 encryption"""
        logging.info("Processing with SM4-CBC + SM2")
        
        # Encrypt with SM4
        sm4 = SM4Encryption(self.config)
        iv, encrypted_payload = sm4.encrypt(data)
        if self.config.SM4_USE_EMBEDDED_IV:
            encrypted_data = iv + encrypted_payload
        else:
            encrypted_data = encrypted_payload
        
        # Sign with SM2
        sm2 = SM2Signature(self.config)
        signature, r_component, s_component = sm2.sign(encrypted_data)
        
        header_info = {
            'type': 'sm2',
            'r_component': r_component,
            's_component': s_component,
            'data_length': len(encrypted_data),
            'encryption_type': self.config.ENCRYPTION_SM4
        }
        
        return encrypted_data, header_info
    
    def _handle_aes_encryption(self, data: bytes) -> Tuple[bytes, dict]:
        """Handle AES-GCM + RSA encryption"""
        logging.info("Processing with AES-GCM + RSA-2048")
        
        # Encrypt with AES-GCM
        aes = AESEncryption(self.config)
        iv, ciphertext, tag = aes.encrypt(data)
        if self.config.AES_USE_EMBEDDED_IV:
            encrypted_data = iv + ciphertext + tag
        else:
            encrypted_data = ciphertext + tag
        
        # Sign tag with RSA
        rsa = RSASignature(self.config)
        signature = rsa.sign(tag)
        
        header_info = {
            'type': 'rsa',
            'modulus': rsa.modulus,
            'exponent': rsa.exponent,
            'signature': signature,
            'data_length': len(encrypted_data),
            'encryption_type': self.config.ENCRYPTION_AES
        }
        
        return encrypted_data, header_info
    
    def _write_firmware(self, output_path: str, data: bytes, header_info: dict) -> None:
        """Write firmware file with proper header"""
        with open(output_path, 'wb') as f:
            # Write magic bytes
            f.write(self.config.MAGIC_BYTES)
            logging.debug(f"Magic bytes: {format_hex_bytes(self.config.MAGIC_BYTES, 'the magic is: ')}")
            
            # Write data length
            length_bytes = header_info['data_length'].to_bytes(4, byteorder=sys.byteorder, signed=True)
            f.write(length_bytes)
            
            # Write encryption type
            enc_type_bytes = header_info['encryption_type'].to_bytes(4, byteorder=sys.byteorder, signed=True)
            f.write(enc_type_bytes)
            logging.debug(f"Encryption type: {header_info['encryption_type']}")
            
            # Write appropriate header
            self._write_specific_header(f, header_info)
            
            # Write firmware data
            f.write(data)
    
    def _write_specific_header(self, output_file, header_info: dict) -> None:
        """Write specific header based on type"""
        if header_info['type'] == 'rsa':
            formatter = RSAHeaderFormatter(self.config)
            formatter.write_header(
                output_file,
                header_info['modulus'],
                header_info['exponent'],
                header_info['signature']
            )
        elif header_info['type'] == 'sm2':
            formatter = SM2HeaderFormatter(self.config)
            formatter.write_header(
                output_file,
                header_info['r_component'],
                header_info['s_component']
            )
        elif header_info['type'] == 'hash':
            formatter = HashHeaderFormatter(self.config)
            formatter.write_header(output_file, header_info['hash_data'])


# ============================================================================
# Command Line Interface
# ============================================================================

def create_argument_parser() -> argparse.ArgumentParser:
    """Create command line argument parser"""
    parser = argparse.ArgumentParser(
        description='Generate firmware images with different encryption and signing options',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -i input.bin -o output.bin --aes
  %(prog)s -i input.bin -o output.bin --sm4
  %(prog)s -i input.bin -o output.bin --no-encryption
  %(prog)s -i input.bin -o output.bin --aes -c config.json
  %(prog)s --generate-config template.json
        """
    )
    
    parser.add_argument(
        '-i', '--input',
        required=False,
        help='Input firmware file path'
    )
    
    parser.add_argument(
        '-o', '--output',
        required=False,
        help='Output firmware file path'
    )
    
    parser.add_argument(
        '-c', '--config',
        help='Path to configuration JSON file; required for encrypted modes and optional for no-encryption mode'
    )
    
    encryption_group = parser.add_mutually_exclusive_group()
    encryption_group.add_argument(
        '--aes',
        action='store_true',
        help='Use AES-GCM + RSA-2048 encryption'
    )
    encryption_group.add_argument(
        '--sm4',
        action='store_true',
        help='Use SM4-CBC + SM2 encryption'
    )
    encryption_group.add_argument(
        '--no-encryption',
        action='store_true',
        help='No encryption, only SHA-256 hash'
    )
    
    parser.add_argument(
        '--generate-config',
        metavar='FILE',
        help='Generate a template configuration file and exit'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )
    
    return parser

def main() -> None:
    """Main entry point"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    try:
        # Handle config generation
        if args.generate_config:
            config = FirmwareConfig()
            config_dict = config.to_dict()
            
            with open(args.generate_config, 'w', encoding='utf-8') as f:
                json.dump(config_dict, f, indent=2, ensure_ascii=False)
            
            print(f"Configuration template generated: {args.generate_config}")
            return
        
        # Validate required arguments for firmware generation
        if not args.input or not args.output:
            parser.error("Input and output files are required for firmware generation")
        
        # Determine encryption type
        if args.aes:
            encryption_type = FirmwareConfig.ENCRYPTION_AES
        elif args.sm4:
            encryption_type = FirmwareConfig.ENCRYPTION_SM4
        elif args.no_encryption:
            encryption_type = FirmwareConfig.ENCRYPTION_NONE
        else:
            # Default to no encryption if none specified
            encryption_type = FirmwareConfig.ENCRYPTION_NONE
            logging.info("No encryption type specified, using no encryption")

        # Load configuration from file if provided
        if args.config:
            if encryption_type == FirmwareConfig.ENCRYPTION_NONE:
                config = FirmwareConfig.from_file(args.config)
                config.validate_for_encryption(encryption_type)
            else:
                config = FirmwareConfig.from_file_for_encryption(args.config, encryption_type)
        else:
            if encryption_type != FirmwareConfig.ENCRYPTION_NONE:
                parser.error("Encrypted modes require --config with user-provided key and IV material")

            config = FirmwareConfig()
            config.validate_for_encryption(encryption_type)
            logging.info("Using default no-encryption configuration")

        # Generate firmware
        generator = FirmwareGenerator(config)
        generator.generate_firmware(args.input, args.output, encryption_type)

    except Exception as e:
        logging.error(f"Firmware generation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
