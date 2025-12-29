"""Service layer for bitmap image processing and printing.

This service handles all server-side bitmap processing including:
- QR code generation
- Image loading and resizing
- Dithering for print quality
- Conversion to packed 1-bit bitmap format
- Validation and error handling
"""

from __future__ import annotations

import base64
from io import BytesIO

import qrcode
from PIL import Image

from src.utils.bitmap import (
    STANDARD_WIDTH_58MM,
    validate_bitmap_dimensions,
    validate_bitmap_size,
)


class BitmapService:
    """Service for processing and preparing bitmap images for thermal printing."""

    @staticmethod
    def generate_qr_code(url: str, size: int = 128) -> Image.Image:
        """Generate a QR code as a PIL image.

        Args:
            url: URL to encode in the QR code
            size: Size of the QR code image in pixels (must be multiple of 8)

        Returns:
            Grayscale PIL Image

        Raises:
            ValueError: If size is invalid
        """
        if size % 8 != 0:
            raise ValueError(f"QR code size must be multiple of 8, got {size}")

        # Create QR code - ERROR_CORRECT_M = 0 (15% error correction)
        qr = qrcode.QRCode(
            version=None,  # Auto-select version
            error_correction=0,  # ERROR_CORRECT_M
            box_size=max(1, size // 25),
            border=2,
        )
        qr.add_data(url)
        qr.make(fit=True)

        # Generate image
        try:
            img = qr.make_image(fill_color="black", back_color="white")
        except Exception as e:
            raise ValueError(f"Failed to generate QR code image: {e}") from e

        # The qrcode library returns a PilImage wrapper
        # Call get_image() to extract the actual PIL Image
        if hasattr(img, 'get_image'):
            img = img.get_image()
        elif not isinstance(img, Image.Image):
            # Fallback for older qrcode versions that might return PIL Image directly
            raise ValueError(
                f"Cannot extract PIL Image from qrcode type {type(img)}. "
                f"Available attributes: {[a for a in dir(img) if not a.startswith('_')]}"
            )

        # Verify we have a PIL Image
        if not isinstance(img, Image.Image):
            raise ValueError(f"QR code generation returned unexpected type: {type(img)}")

        # Convert to grayscale if needed
        if img.mode != "L":
            img = img.convert("L")

        # Resize to exact size
        img = img.resize((size, size), Image.Resampling.LANCZOS)

        return img

    @staticmethod
    def load_image(image_data: bytes) -> Image.Image:
        """Load an image from bytes.

        Args:
            image_data: Raw image data (PNG, JPEG, etc.)

        Returns:
            Grayscale PIL Image

        Raises:
            ValueError: If image cannot be loaded
        """
        try:
            img = Image.open(BytesIO(image_data))
            # Convert to grayscale
            img = img.convert("L")
            return img
        except Exception as e:
            raise ValueError(f"Failed to load image: {e}") from e

    @staticmethod
    def resize_for_printer(
        img: Image.Image, target_width: int | None = None
    ) -> Image.Image:
        """Resize an image for thermal printer.

        Args:
            img: PIL Image to resize
            target_width: Target width in pixels (must be multiple of 8).
                        If None, uses standard 58mm width (384px).

        Returns:
            Resized PIL Image

        Raises:
            ValueError: If target_width is invalid
        """
        if target_width is None:
            target_width = STANDARD_WIDTH_58MM

        # Ensure width is multiple of 8
        target_width = (target_width // 8) * 8

        if target_width <= 0:
            raise ValueError(f"Target width must be positive, got {target_width}")

        # Calculate height to maintain aspect ratio
        aspect_ratio = img.height / img.width
        target_height = int(target_width * aspect_ratio)

        if target_height <= 0:
            raise ValueError("Calculated height is not positive")

        # Resize using high-quality resampling
        img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

        return img

    @staticmethod
    def apply_dithering(img: Image.Image) -> Image.Image:
        """Apply Floyd-Steinberg dithering to convert grayscale to 1-bit.

        Args:
            img: Grayscale PIL Image

        Returns:
            1-bit (black/white) PIL Image
        """
        # Convert to grayscale if not already
        if img.mode != "L":
            img = img.convert("L")

        # Make a copy to avoid modifying the original
        img = img.copy()

        pixels = img.load()
        width, height = img.size

        for y in range(height):
            for x in range(width):
                old_pixel = pixels[x, y]
                new_pixel = 0 if old_pixel < 128 else 255
                pixels[x, y] = new_pixel

                quant_error = old_pixel - new_pixel

                # Distribute error to neighboring pixels
                # Use int() to ensure we store integer values
                if x + 1 < width:
                    new_val = int(pixels[x + 1, y] + quant_error * 7 / 16)
                    pixels[x + 1, y] = max(0, min(255, new_val))

                if x - 1 >= 0 and y + 1 < height:
                    new_val = int(pixels[x - 1, y + 1] + quant_error * 3 / 16)
                    pixels[x - 1, y + 1] = max(0, min(255, new_val))

                if y + 1 < height:
                    new_val = int(pixels[x, y + 1] + quant_error * 5 / 16)
                    pixels[x, y + 1] = max(0, min(255, new_val))

                if x + 1 < width and y + 1 < height:
                    new_val = int(pixels[x + 1, y + 1] + quant_error * 1 / 16)
                    pixels[x + 1, y + 1] = max(0, min(255, new_val))

        # Convert to 1-bit mode
        return img.convert("1")

    @staticmethod
    def image_to_packed_bitmap(img: Image.Image) -> bytes:
        """Convert PIL image to packed 1-bit bitmap format.

        Args:
            img: PIL Image (will be converted to 1-bit if needed)

        Returns:
            Raw bitmap bytes in packed format

        Raises:
            ValueError: If image dimensions are invalid
        """
        # Ensure image is in 1-bit mode
        if img.mode != "1":
            img = img.convert("1")

        width, height = img.size

        # Validate dimensions
        validate_bitmap_dimensions(width, height)

        # Calculate bytes per line
        bytes_per_line = width // 8

        # Allocate output buffer
        output = bytearray(bytes_per_line * height)

        for y in range(height):
            for x in range(0, width, 8):
                byte_index = (y * bytes_per_line) + (x // 8)

                # Pack 8 pixels into one byte
                packed_byte = 0
                for bit in range(8):
                    pixel_x = x + bit
                    if pixel_x < width:
                        # Get pixel value (0=black, 255=white in PIL '1' mode)
                        pixel = img.getpixel((pixel_x, y))

                        # Invert: 1=black (print), 0=white (no print)
                        if pixel == 0:  # Black pixel
                            packed_byte |= 1 << (7 - bit)

                output[byte_index] = packed_byte

        return bytes(output)

    @staticmethod
    def create_bitmap_message(
        img: Image.Image, caption: str | None = None
    ) -> dict[str, object]:
        """Create a bitmap WebSocket message from a PIL image.

        This method processes the image through the full pipeline:
        1. Resize for printer (if needed)
        2. Apply dithering
        3. Convert to packed bitmap
        4. Encode as base64
        5. Create message dict

        Args:
            img: PIL Image to process
            caption: Optional caption text

        Returns:
            Dictionary suitable for sending as WebSocket message

        Raises:
            ValueError: If image processing fails
        """
        # Resize for printer (ensure width is multiple of 8)
        img = BitmapService.resize_for_printer(img)

        # Apply dithering
        img = BitmapService.apply_dithering(img)

        # Convert to packed bitmap
        bitmap_data = BitmapService.image_to_packed_bitmap(img)

        # Validate size
        validate_bitmap_size(len(bitmap_data))

        # Encode as base64
        data_base64 = base64.b64encode(bitmap_data).decode("utf-8")

        # Create message
        message = {
            "kind": "print_bitmap",
            "width": img.width,
            "height": img.height,
            "data": data_base64,
        }

        if caption:
            message["caption"] = caption

        return message

    @staticmethod
    def create_test_pattern(size: int = 128) -> Image.Image:
        """Create a test pattern image for debugging.

        Args:
            size: Size of the test pattern (must be multiple of 8)

        Returns:
            PIL Image with test pattern

        Raises:
            ValueError: If size is invalid
        """
        if size % 8 != 0:
            raise ValueError(f"Test pattern size must be multiple of 8, got {size}")

        # Create grayscale image (white background)
        img = Image.new("L", (size, size), color=255)

        # Create pixel access object
        pixels = img.load()

        # Draw checkerboard pattern using direct pixel access
        square_size = 16
        for y in range(size):
            for x in range(size):
                # Determine which square this pixel is in
                square_x = x // square_size
                square_y = y // square_size

                # Alternate between black (0) and white (255)
                if (square_x + square_y) % 2 == 0:
                    pixels[x, y] = 0  # Black
                else:
                    pixels[x, y] = 255  # White

        return img
