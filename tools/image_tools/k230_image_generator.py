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


# ============================================================================
# Configuration Constants
# ============================================================================

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
    AES_IV: bytes = b'\x9f\xf1\x85\x63\xb9\x78\xec\x28\x1b\x3f\x27\x94'
    AES_KEY: bytes = b'\x24\x50\x1a\xd3\x84\xe4\x73\x96\x3d\x47\x6e\xdc\xfe\x08\x20\x52\x37\xac\xfd\x49\xb5\xb8\xf3\x38\x57\xf8\x11\x4e\x86\x3f\xec\x7f'
    AES_AUTH_DATA: bytes = b''
    
    # RSA-2048 parameters
    RSA_KEYSIZE: int = 2048
    RSA_MODULUS: bytes = b'\xce\xa8\x04\x75\x32\x4c\x1d\xc8\x34\x78\x27\x81\x8d\xa5\x8b\xac\x06\x9d\x34\x19\xc6\x14\xa6\xea\x1a\xc6\xa3\xb5\x10\xdc\xd7\x2c\xc5\x16\x95\x49\x05\xe9\xfe\xf9\x08\xd4\x5e\x13\x00\x6a\xdf\x27\xd4\x67\xa7\xd8\x3c\x11\x1d\x1a\x5d\xf1\x5e\xf2\x93\x77\x1a\xef\xb9\x20\x03\x2a\x5b\xb9\x89\xf8\xe4\xf5\xe1\xb0\x50\x93\xd3\xf1\x30\xf9\x84\xc0\x7a\x77\x2a\x36\x83\xf4\xdc\x6f\xb2\x8a\x96\x81\x5b\x32\x12\x3c\xcd\xd1\x39\x54\xf1\x9d\x5b\x8b\x24\xa1\x03\xe7\x71\xa3\x4c\x32\x87\x55\xc6\x5e\xd6\x4e\x19\x24\xff\xd0\x4d\x30\xb2\x14\x2c\xc2\x62\xf6\xe0\x04\x8f\xef\x6d\xbc\x65\x2f\x21\x47\x9e\xa1\xc4\xb1\xd6\x6d\x28\xf4\xd4\x6e\xf7\x18\x5e\x39\x0c\xbf\xa2\xe0\x23\x80\x58\x2f\x31\x88\xbb\x94\xeb\xbf\x05\xd3\x14\x87\xa0\x9a\xff\x01\xfc\xbb\x4c\xd4\xbf\xd1\xf0\xa8\x33\xb3\x8c\x11\x81\x3c\x84\x36\x0b\xb5\x3c\x7d\x44\x81\x03\x1c\x40\xba\xd8\x71\x3b\xb6\xb8\x35\xcb\x08\x09\x8e\xd1\x5b\xa3\x1e\xe4\xba\x72\x8a\x8c\x8e\x10\xf7\x29\x4e\x1b\x41\x63\xb7\xae\xe5\x72\x77\xbf\xd8\x81\xa6\xf9\xd4\x3e\x02\xc6\x92\x5a\xa3\xa0\x43\xfb\x7f\xb7\x8d'
    RSA_EXPONENT: str = '0x260445'
    RSA_PRIVATE_EXPONENT: bytes = b'\x09\x97\x63\x4c\x47\x7c\x1a\x03\x9d\x44\xc8\x10\xb2\xaa\xa3\xc7\x86\x2b\x0b\x88\xd3\x70\x82\x72\xe1\xe1\x5f\x66\xfc\x93\x89\x70\x9f\x8a\x11\xf3\xea\x6a\x5a\xf7\xef\xfa\x2d\x01\xc1\x89\xc5\x0f\x0d\x5b\xcb\xe3\xfa\x27\x2e\x56\xcf\xc4\xa4\xe1\xd3\x88\xa9\xdc\xd6\x5d\xf8\x62\x89\x02\x55\x6c\x8b\x6b\xb6\xa6\x41\x70\x9b\x5a\x35\xdd\x26\x22\xc7\x3d\x46\x40\xbf\xa1\x35\x9d\x0e\x76\xe1\xf2\x19\xf8\xe3\x3e\xb9\xbd\x0b\x59\xec\x19\x8e\xb2\xfc\xca\xae\x03\x46\xbd\x8b\x40\x1e\x12\xe3\xc6\x7c\xb6\x29\x56\x9c\x18\x5a\x2e\x0f\x35\xa2\xf7\x41\x64\x4c\x1c\xca\x5e\xbb\x13\x9d\x77\xa8\x9a\x29\x53\xfc\x5e\x30\x04\x8c\x0e\x61\x9f\x07\xc8\xd2\x1d\x1e\x56\xb8\xaf\x07\x19\x3d\x0f\xdf\x3f\x49\xcd\x49\xf2\xef\x31\x38\xb5\x13\x88\x62\xf1\x47\x0b\xd2\xd1\x6e\x34\xa2\xb9\xe7\x77\x7a\x6c\x8c\x8d\x4c\xb9\x4b\x4e\x8b\x5d\x61\x6c\xd5\x39\x37\x53\xe7\xb0\xf3\x1c\xc7\xda\x55\x9b\xa8\xe9\x8d\x88\x89\x14\xe3\x34\x77\x3b\xaf\x49\x8a\xd8\x8d\x96\x31\xeb\x5f\xe3\x2e\x53\xa4\x14\x5b\xf0\xba\x54\x8b\xf2\xb0\xa5\x0c\x63\xf6\x7b\x14\xe3\x98\xa3\x4b\x0d'
    
    # SM4 parameters
    SM4_KEY: bytes = b'\x01\x23\x45\x67\x89\xab\xcd\xef\xfe\xdc\xba\x98\x76\x54\x32\x10'
    SM4_IV: bytes = b'\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b\x0c\x0d\x0e\x0f'
    
    # SM2 parameters
    SM2_PRIVATE_KEY: bytes = b'\x39\x45\x20\x8f\x7b\x21\x44\xb1\x3f\x36\xe3\x8a\xc6\xd3\x9f\x95\x88\x93\x93\x69\x28\x60\xb5\x1a\x42\xfb\x81\xef\x4d\xf7\xc5\xb8'
    SM2_PUBLIC_KEY_X: bytes = b'\x09\xf9\xdf\x31\x1e\x54\x21\xa1\x50\xdd\x7d\x16\x1e\x4b\xc5\xc6\x72\x17\x9f\xad\x18\x33\xfc\x07\x6b\xb0\x8f\xf3\x56\xf3\x50\x20'
    SM2_PUBLIC_KEY_Y: bytes = b'\xcc\xea\x49\x0c\xe2\x67\x75\xa5\x2d\xc6\xea\x71\x8c\xc1\xaa\x60\x0a\xed\x05\xfb\xf3\x5e\x08\x4a\x66\x32\xf6\x07\x2d\xa9\xad\x13'
    SM2_RANDOM_K: bytes = b'\x59\x27\x6e\x27\xd5\x06\x86\x1a\x16\x68\x0f\x3a\xd9\xc0\x2d\xcc\xef\x3c\xc1\xfa\x3c\xdb\xe4\xce\x6d\x54\xb8\x0d\xea\xc1\xbc\x21'
    SM2_ID: bytes = b'1234567812345678'
    
    @classmethod
    def from_file(cls, config_path: str) -> 'FirmwareConfig':
        """Create FirmwareConfig from JSON file
        
        Args:
            config_path: Path to configuration file
            
        Returns:
            FirmwareConfig instance with values from file
        """
        config_data = load_config_from_file(config_path)
        
        # Create default config first
        config = cls()
        
        # Override with values from file
        if 'firmware' in config_data:
            firmware_config = config_data['firmware']
            if 'version_bytes' in firmware_config:
                config.VERSION_BYTES = hex_string_to_bytes(firmware_config['version_bytes'])
        
        if 'aes' in config_data:
            aes_config = config_data['aes']
            if 'iv' in aes_config:
                config.AES_IV = hex_string_to_bytes(aes_config['iv'])
            if 'key' in aes_config:
                config.AES_KEY = hex_string_to_bytes(aes_config['key'])
            if 'auth_data' in aes_config:
                config.AES_AUTH_DATA = hex_string_to_bytes(aes_config['auth_data'])
        
        if 'rsa' in config_data:
            rsa_config = config_data['rsa']
            if 'key_size' in rsa_config:
                config.RSA_KEYSIZE = int(rsa_config['key_size'])
            if 'modulus' in rsa_config:
                config.RSA_MODULUS = hex_string_to_bytes(rsa_config['modulus'])
            if 'exponent' in rsa_config:
                config.RSA_EXPONENT = str(rsa_config['exponent'])
            if 'private_exponent' in rsa_config:
                config.RSA_PRIVATE_EXPONENT = hex_string_to_bytes(rsa_config['private_exponent'])
        
        if 'sm4' in config_data:
            sm4_config = config_data['sm4']
            if 'key' in sm4_config:
                config.SM4_KEY = hex_string_to_bytes(sm4_config['key'])
            if 'iv' in sm4_config:
                config.SM4_IV = hex_string_to_bytes(sm4_config['iv'])
        
        if 'sm2' in config_data:
            sm2_config = config_data['sm2']
            if 'private_key' in sm2_config:
                config.SM2_PRIVATE_KEY = hex_string_to_bytes(sm2_config['private_key'])
            if 'public_key_x' in sm2_config:
                config.SM2_PUBLIC_KEY_X = hex_string_to_bytes(sm2_config['public_key_x'])
            if 'public_key_y' in sm2_config:
                config.SM2_PUBLIC_KEY_Y = hex_string_to_bytes(sm2_config['public_key_y'])
            if 'random_k' in sm2_config:
                config.SM2_RANDOM_K = hex_string_to_bytes(sm2_config['random_k'])
            if 'id' in sm2_config:
                config.SM2_ID = sm2_config['id'].encode('utf-8') if isinstance(sm2_config['id'], str) else hex_string_to_bytes(sm2_config['id'])
        
        logging.info("Configuration loaded and applied successfully")
        return config
    
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
                'iv': bytes_to_hex_string(self.AES_IV),
                'key': bytes_to_hex_string(self.AES_KEY),
                'auth_data': bytes_to_hex_string(self.AES_AUTH_DATA)
            },
            'rsa': {
                'key_size': self.RSA_KEYSIZE,
                'modulus': bytes_to_hex_string(self.RSA_MODULUS),
                'exponent': self.RSA_EXPONENT,
                'private_exponent': bytes_to_hex_string(self.RSA_PRIVATE_EXPONENT)
            },
            'sm4': {
                'key': bytes_to_hex_string(self.SM4_KEY),
                'iv': bytes_to_hex_string(self.SM4_IV)
            },
            'sm2': {
                'private_key': bytes_to_hex_string(self.SM2_PRIVATE_KEY),
                'public_key_x': bytes_to_hex_string(self.SM2_PUBLIC_KEY_X),
                'public_key_y': bytes_to_hex_string(self.SM2_PUBLIC_KEY_Y),
                'random_k': bytes_to_hex_string(self.SM2_RANDOM_K),
                'id': self.SM2_ID.decode('utf-8', errors='ignore')
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


# ============================================================================
# Encryption Classes
# ============================================================================

class AESEncryption:
    """AES-GCM-256 encryption implementation"""
    
    def __init__(self, config: FirmwareConfig):
        self.config = config
        self.key = config.AES_KEY
        self.iv = config.AES_IV
        self.auth_data = config.AES_AUTH_DATA
        
    def encrypt(self, data: bytes) -> Tuple[bytes, bytes]:
        """Encrypt data using AES-GCM-256
        
        Args:
            data: Data to encrypt
            
        Returns:
            Tuple of (ciphertext, authentication_tag)
        """
        cipher = AES.new(self.key, AES.MODE_GCM, self.iv)
        cipher.update(self.auth_data)
        ciphertext, tag = cipher.encrypt_and_digest(data)
        
        logging.debug(f"AES-GCM encrypted {len(data)} bytes")
        logging.debug(f"Ciphertext: {format_hex_bytes(ciphertext, 'ciphertext: ')}")
        logging.debug(f"Tag: {format_hex_bytes(tag, 'tag: ')}")
        
        return ciphertext, tag
    
    def decrypt(self, ciphertext: bytes, tag: bytes) -> bytes:
        """Decrypt data using AES-GCM-256
        
        Args:
            ciphertext: Encrypted data
            tag: Authentication tag
            
        Returns:
            Decrypted plaintext
        """
        cipher = AES.new(self.key, AES.MODE_GCM, self.iv)
        cipher.update(self.auth_data)
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        
        logging.debug(f"AES-GCM decrypted {len(plaintext)} bytes")
        return plaintext


class SM4Encryption:
    """SM4-CBC encryption implementation"""
    
    def __init__(self, config: FirmwareConfig):
        self.config = config
        self.key = config.SM4_KEY
        self.iv = config.SM4_IV
        self.crypt_sm4 = CryptSM4()
        
    def encrypt(self, data: bytes) -> bytes:
        """Encrypt data using SM4-CBC
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted data
        """
        self.crypt_sm4.set_key(self.key, SM4_ENCRYPT)
        encrypted = self.crypt_sm4.crypt_cbc(self.iv, data)
        
        logging.debug(f"SM4-CBC encrypted {len(data)} bytes")
        logging.debug(f"Encrypted: {format_hex_bytes(encrypted, 'encryption: ')}")
        
        return encrypted
    
    def decrypt(self, data: bytes) -> bytes:
        """Decrypt data using SM4-CBC
        
        Args:
            data: Data to decrypt
            
        Returns:
            Decrypted data
        """
        self.crypt_sm4.set_key(self.key, SM4_DECRYPT)
        decrypted = self.crypt_sm4.crypt_cbc(self.iv, data)
        
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
        self.random_k_hex = codecs.encode(self.config.SM2_RANDOM_K, 'hex').decode('ascii')
        
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
        sign = sm2_crypt.sign(sign_data, self.random_k_hex)
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
        modulus_hex = f'{modulus:x}'
        modulus_bytes = bytes.fromhex(modulus_hex)
        output_file.write(modulus_bytes)
        
        # Write exponent (4 bytes)
        exponent_bytes = exponent.to_bytes(4, byteorder=sys.byteorder, signed=True)
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
        encrypted_data = sm4.encrypt(data)
        
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
        ciphertext, tag = aes.encrypt(data)
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
        help='Path to configuration JSON file (optional, uses defaults if not provided)'
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
        
        # Load configuration from file if provided
        if args.config:
            config = FirmwareConfig.from_file(args.config)
        else:
            config = FirmwareConfig()
            logging.info("Using default configuration")
        
        # Determine encryption type
        if args.aes:
            encryption_type = config.ENCRYPTION_AES
        elif args.sm4:
            encryption_type = config.ENCRYPTION_SM4
        elif args.no_encryption:
            encryption_type = config.ENCRYPTION_NONE
        else:
            # Default to no encryption if none specified
            encryption_type = config.ENCRYPTION_NONE
            logging.info("No encryption type specified, using no encryption")

        # Generate firmware
        generator = FirmwareGenerator(config)
        generator.generate_firmware(args.input, args.output, encryption_type)

    except Exception as e:
        logging.error(f"Firmware generation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
