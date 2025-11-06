import os
import sys
import re
import io
import tempfile

from pathlib import Path
from typing import Dict, Any

from .k230_image_generator import FirmwareConfig, FirmwareGenerator

def safe_str_to_int(value_str: str) -> int:
    """
    Converts a string to an integer, supporting decimal (base 10) and 
    hexadecimal (base 16) with the '0x' prefix.

    Args:
        value_str: The string representation of the number (e.g., '123' or '0x80000000').

    Returns:
        The integer value.

    Raises:
        ValueError: If the string cannot be converted to a valid number.
    """
    # 1. Clean up the string (remove whitespace/quotes if necessary)
    value_str = value_str.strip().lower() 
    
    # 2. Check for the hexadecimal prefix
    if value_str.startswith('0x'):
        # If it starts with '0x', convert it using base 16
        return int(value_str, 16)
    
    # 3. If no '0x' prefix, attempt base 10 conversion
    else:
        # If the string contains any non-decimal characters (a-f), this will fail, 
        # which is the correct behavior for a decimal number.
        return int(value_str, 10)

def generate_temp_file_path(prefix, suffix) -> str:
    temp_dir = Path(tempfile.gettempdir())
    random_filename = prefix + os.urandom(8).hex() + suffix

    random_path = temp_dir / random_filename

    return str(random_path)

def generate_k230_image(input_file, output_file, encrypt_type = 0, encrypt_config = None) -> bool:
    if not Path(input_file).exists():
        print(f"File not exists {input_file}")
        return False

    if encrypt_type is None:
        encrypt_type = 0

    if encrypt_type != 0:
        if encrypt_config is None or not Path(encrypt_config).exists():
            print(f"Encrypt type ({encrypt_type}) need config file")
            return False

    if encrypt_type != 0 and encrypt_config is not None:
        img_config = FirmwareConfig.from_file(encrypt_config)
    else:
        img_config = FirmwareConfig()

    try:
        img_generator = FirmwareGenerator(img_config)
        img_generator.generate_firmware(input_file, output_file, encrypt_type)

        return True
    except Exception as e:
        print(f"An error occurred: {e}")
        return False


def get_validated_env_path(env_var_name: str) -> str:
    """
    Loads an environment variable, checks if it's set and if the path it 
    points to is a valid directory. Raises ValueError on failure.

    Args:
        env_var_name (str): The name of the environment variable to check.

    Returns:
        str: The absolute, validated directory path.

    Raises:
        ValueError: If the environment variable is not set or the path is invalid.
    """
    
    # 1. Check if the environment variable is found
    path_value = os.getenv(env_var_name)
    if path_value is None:
        raise ValueError(
            f"❌ Environment Variable Error: '{env_var_name}' is not set. "
            "Please set this variable to a valid directory path."
        )

    # 2. Convert to an absolute path for robustness
    abs_path = os.path.abspath(path_value)

    # 3. Check if the path exists and is a directory
    if not os.path.exists(abs_path):
        raise ValueError(
            f"❌ Path Error: The path specified by '{env_var_name}' "
            f"('{abs_path}') does not exist."
        )

    if not os.path.isdir(abs_path):
        raise ValueError(
            f"❌ Path Error: The path specified by '{env_var_name}' "
            f"('{abs_path}') is not a directory."
        )

    # Return the validated, absolute path
    return abs_path

def parse_kconfig(config_file_path: str) -> Dict[str, Any]:
    """
    Parses a Kconfig .config file, expands environment variables in
    the format ${ENV_VAR} in the config values, and returns a dictionary.
    
    Converts 'y' to True and explicitly 'n' (or unset configs) to False.
    Numeric values and paths are kept as strings after env expansion.

    Args:
        config_file_path (str): The path to the .config file.

    Returns:
        dict: A dictionary of CONFIG_SYMBOL -> expanded_value (bool or str).
    """
    config_data = {}

    # Regex to match lines like: CONFIG_SYMBOL="value" or CONFIG_SYMBOL=y/n/hex/int
    # Group 1: CONFIG_SYMBOL
    # Group 2: The entire value part (e.g., "value" or y)
    CONFIG_LINE_RE = re.compile(r'^(CONFIG_[A-Z0-9_]+)=(.*)')

    # Regex to match lines that are explicitly NOT set (e.g., comments like "# CONFIG_XXX is not set")
    UNSET_LINE_RE = re.compile(r'^#\s*(CONFIG_[A-Z0-9_]+)\s+is\s+not\s+set')

    try:
        with open(config_file_path, 'r') as f:
            for line in f:
                line = line.strip()

                # --- 1. Handle Unset/Negative Configuration (Implicit 'n' or False) ---
                unset_match = UNSET_LINE_RE.match(line)
                if unset_match:
                    symbol = unset_match.group(1)
                    config_data[symbol] = False
                    continue

                # Ignore general comments and blank lines after unset check
                if not line or line.startswith('#'):
                    continue

                # --- 2. Handle Set Configuration ---
                match = CONFIG_LINE_RE.match(line)
                if match:
                    symbol = match.group(1)
                    value_raw = match.group(2)

                    # 2a. Strip quotes if present (Kconfig often quotes strings)
                    if value_raw.startswith('"') and value_raw.endswith('"'):
                        value_processed = value_raw.strip('"')
                    else:
                        value_processed = value_raw

                    # 2b. Expand environment variables (Handles ${VAR} and $VAR)
                    expanded_value = os.path.expandvars(value_processed)

                    # 2c. Apply Type Conversion Logic

                    # Convert 'y' to True (The most common Kconfig boolean true)
                    if expanded_value == 'y':
                        final_value: Any = True
                    # Keep all other values (hex, paths, strings, etc.) as the expanded string
                    else:
                        final_value = expanded_value

                    config_data[symbol] = final_value

    except FileNotFoundError:
        print(f"Error: Config file not found at {config_file_path}")
        return {} # Return empty dict instead of None for easier external use
    except Exception as e:
        print(f"An error occurred: {e}")
        return {}

    return config_data

def swap_chunk(chunk_orig):
    """Swap byte endianness of the given chunk in 4-byte (32-bit) words.

    It pads the end of the chunk with null bytes (0x00) if its length is not
    a multiple of 4, ensuring all data is swapped in 32-bit blocks.

    Args:
        chunk_orig (bytes or bytearray): The chunk of binary data to process.

    Returns:
        bytearray: The swapped and padded chunk.
    """
    chunk = bytearray(chunk_orig)

    # Align to 4 bytes and pad with 0x0
    chunk_len = len(chunk)
    pad_len = chunk_len % 4
    if pad_len > 0:
        chunk += b'\x00' * (4 - pad_len)

    # Perform the 32-bit (4-byte) endianness swap:
    # [0, 1, 2, 3] becomes [3, 2, 1, 0] for every 4-byte group.
    # [start:end:step] slicing is used for efficiency.
    chunk[0::4], chunk[1::4], chunk[2::4], chunk[3::4] = \
        chunk[3::4], chunk[2::4], chunk[1::4], chunk[0::4]

    return chunk

def swap_bytes_in_file(input_path, output_path, chunk_size=io.DEFAULT_BUFFER_SIZE):
    """
    Reads an input binary file, swaps the byte order (32-bit), 
    and writes the result to an output file.

    Args:
        input_path (str): Path to the source binary file.
        output_path (str): Path to the destination binary file.
        chunk_size (int): Size of the buffer to read at a time.
    """
    try:
        with open(input_path, "rb") as input_bin:
            with open(output_path, "wb") as output_bin:
                while True:
                    # Read up to chunk_size bytes
                    chunk = input_bin.read(chunk_size)
                    
                    # Stop if we hit EOF
                    if not chunk:
                        break

                    # Swap the chunk and write it out
                    output_bin.write(swap_chunk(chunk))

        # print(f"Successfully swapped bytes from {input_path} to {output_path}")

    except FileNotFoundError:
        print(f"Error: One of the files was not found. Input: {input_path}, Output: {output_path}", file=sys.stderr)
        raise
    except Exception as e:
        print(f"An unexpected error occurred during file processing: {e}", file=sys.stderr)
        raise
