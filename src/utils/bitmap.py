"""Bitmap processing utilities for thermal printer support.

This module provides helper functions for bitmap validation, constants for
printer specifications, and utilities for working with thermal printer bitmaps.
"""

from __future__ import annotations


# Printer specifications
MAX_BITMAP_SIZE_BYTES = 50 * 1024  # 50KB max bitmap data size
STANDARD_WIDTH_58MM = 384  # Standard width for 58mm thermal paper
STANDARD_WIDTH_80MM = 576  # Standard width for 80mm thermal paper


def validate_bitmap_dimensions(width: int, height: int) -> bool:
    """Validate that bitmap dimensions are acceptable.

    Args:
        width: Image width in pixels
        height: Image height in pixels

    Returns:
        True if dimensions are valid

    Raises:
        ValueError: If dimensions are invalid
    """
    if width <= 0:
        raise ValueError(f"Width must be positive, got {width}")

    if height <= 0:
        raise ValueError(f"Height must be positive, got {height}")

    if width % 8 != 0:
        raise ValueError(f"Width must be multiple of 8, got {width}")

    # Validate against standard printer widths
    if width > STANDARD_WIDTH_80MM:
        raise ValueError(
            f"Width {width} exceeds maximum printer width {STANDARD_WIDTH_80MM}"
        )

    return True


def validate_bitmap_size(data_size: int) -> bool:
    """Validate that bitmap data size is within limits.

    Args:
        data_size: Size of bitmap data in bytes

    Returns:
        True if size is valid

    Raises:
        ValueError: If size exceeds limits
    """
    if data_size > MAX_BITMAP_SIZE_BYTES:
        raise ValueError(
            f"Bitmap data size {data_size} bytes exceeds maximum {MAX_BITMAP_SIZE_BYTES} bytes"
        )

    if data_size <= 0:
        raise ValueError(f"Bitmap data size must be positive, got {data_size}")

    return True


def calculate_bitmap_data_size(width: int, height: int) -> int:
    """Calculate the expected size of packed bitmap data.

    Args:
        width: Image width in pixels (must be multiple of 8)
        height: Image height in pixels

    Returns:
        Expected data size in bytes

    Raises:
        ValueError: If width is not multiple of 8
    """
    if width % 8 != 0:
        raise ValueError(f"Width must be multiple of 8, got {width}")

    return (width * height) // 8


def get_target_width_for_paper(paper_width_mm: int = 58) -> int:
    """Get the target pixel width for a given paper size.

    Args:
        paper_width_mm: Paper width in mm (default 58)

    Returns:
        Target width in pixels (multiple of 8)
    """
    if paper_width_mm == 58:
        return STANDARD_WIDTH_58MM
    elif paper_width_mm == 80:
        return STANDARD_WIDTH_80MM
    else:
        # Default to 58mm for unknown paper sizes
        return STANDARD_WIDTH_58MM
