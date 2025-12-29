# Bitmap Printing Implementation Guide

This document provides complete specifications for implementing bitmap printing support on the PaperMinder server.

## Overview

The PaperMinder printer firmware now supports printing bitmap images (QR codes, logos, icons) via WebSocket messages. The server is responsible for all image processing including QR encoding, scaling, dithering, and conversion to 1-bit monochrome format.

## WebSocket Message Protocol

### Print Bitmap Message (Server → Printer)

To print a bitmap, send a WebSocket message with type `print_bitmap`:

```json
{
  "kind": "print_bitmap",
  "width": 128,
  "height": 128,
  "data": "<base64 encoded raw bitmap bytes>",
  "caption": "Optional caption text"
}
```

**Fields:**
- `kind` (string): Must be `"print_bitmap"`
- `width` (integer): Image width in pixels (**must be multiple of 8**)
- `height` (integer): Image height in pixels
- `data` (string): Base64-encoded raw bitmap data (see format below)
- `caption` (string, optional): Text to print below the image

### Printer Responses

**Success Response:**
```json
{
  "kind": "bitmap_printing",
  "width": 128,
  "height": 128
}
```

**Error Response:**
```json
{
  "kind": "bitmap_error",
  "error": "Error description"
}
```

Possible error messages:
- `"Invalid parameters"` - Missing or invalid required fields
- `"Width must be multiple of 8"` - Width not divisible by 8
- `"Image too large"` - Image exceeds 50KB limit
- `"Memory allocation failed"` - Printer out of memory
- `"Decode size mismatch"` - Base64 decode size doesn't match expected size

## Bitmap Data Format

The bitmap data must be **raw 1-bit monochrome** in **packed pixel format**:

### Format Specification

```
- Width: pixels (must be multiple of 8)
- Height: pixels
- Data size: (width × height) ÷ 8 bytes
- Pixel order: Row-major, top to bottom, left to right
- Byte packing: Each byte = 8 horizontal pixels
  - Bit 7 (MSB) = leftmost pixel
  - Bit 0 (LSB) = rightmost pixel
  - 1 = black (printed)
  - 0 = white (not printed)
```

### Example: 16×8 Image

```
Pixels:  W W W W W W W W  B B B B B B B B  (W=white, B=black)
         B B B B B B B B  W W W W W W W W

Data bytes:  0x00  0xFF  0xFF  0x00
            ^^^^  ^^^^  (first row)
                        ^^^^  ^^^^  (second row)
```

## Server-Side Image Processing

### Step 1: Load or Generate Image

**For QR Codes:**
```python
import qrcode

def generate_qr_code(url, size=128):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=size // 25,  # Adjust based on version
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Get PIL image
    img = qr.make_image(fill_color="black", back_color="white")

    # Convert to grayscale if needed
    img = img.convert('L')

    return img
```

**For Logos/Icons:**
```python
from PIL import Image

def load_image(path, max_width=384):
    img = Image.open(path)
    img = img.convert('L')  # Convert to grayscale
    return img
```

### Step 2: Resize for Printer

```python
def resize_for_printer(img, target_width=None):
    """
    Resize image for thermal printer.

    Standard printer widths:
    - 58mm paper: 384 pixels
    - 80mm paper: 576 pixels

    Width must be multiple of 8!
    """
    if target_width is None:
        target_width = 384  # Default for 58mm paper

    # Ensure width is multiple of 8
    target_width = (target_width // 8) * 8

    # Calculate height to maintain aspect ratio
    aspect_ratio = img.height / img.width
    target_height = int(target_width * aspect_ratio)

    # Resize using high-quality resampling
    img = img.resize((target_width, target_height), Image.Resampling.LANCZOS)

    return img
```

### Step 3: Apply Dithering (Optional but Recommended)

```python
def floyd_steinberg_dither(img):
    """
    Apply Floyd-Steinberg dithering for better quality.
    Converts grayscale image to 1-bit black/white.
    """
    pixels = img.load()
    width, height = img.size

    for y in range(height):
        for x in range(width):
            old_pixel = pixels[x, y]
            new_pixel = 0 if old_pixel < 128 else 255
            pixels[x, y] = new_pixel

            quant_error = old_pixel - new_pixel

            # Distribute error to neighboring pixels
            if x + 1 < width:
                pixels[x + 1, y] = min(255, max(0, pixels[x + 1, y] + quant_error * 7 / 16))
            if x - 1 >= 0 and y + 1 < height:
                pixels[x - 1, y + 1] = min(255, max(0, pixels[x - 1, y + 1] + quant_error * 3 / 16))
            if y + 1 < height:
                pixels[x, y + 1] = min(255, max(0, pixels[x, y + 1] + quant_error * 5 / 16))
            if x + 1 < width and y + 1 < height:
                pixels[x + 1, y + 1] = min(255, max(0, pixels[x + 1, y + 1] + quant_error * 1 / 16))

    return img
```

### Step 4: Convert to Packed Bitmap Format

```python
def image_to_packed_bitmap(img):
    """
    Convert PIL image to packed 1-bit bitmap format.
    Returns bytes suitable for sending to printer.
    """
    # Ensure image is in 1-bit mode
    img = img.convert('1')

    width, height = img.size

    # Validate width
    if width % 8 != 0:
        raise ValueError(f"Width must be multiple of 8, got {width}")

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
                        packed_byte |= (1 << (7 - bit))

            output[byte_index] = packed_byte

    return bytes(output)
```

### Step 5: Encode and Send

```python
import base64
import json

def send_bitmap_to_printer(websocket, img, caption=None):
    """
    Convert image and send to printer via WebSocket.
    """
    # Process image
    img = resize_for_printer(img)
    img = floyd_steinberg_dither(img)
    bitmap_data = image_to_packed_bitmap(img)

    # Encode as base64
    data_base64 = base64.b64encode(bitmap_data).decode('utf-8')

    # Create WebSocket message
    message = {
        "kind": "print_bitmap",
        "width": img.width,
        "height": img.height,
        "data": data_base64
    }

    if caption:
        message["caption"] = caption

    # Send to printer
    websocket.send(json.dumps(message))

    print(f"Sent bitmap: {img.width}x{img.height}, {len(bitmap_data)} bytes")
```

## Complete Example: Print QR Code

```python
import asyncio
import websockets
import json
import base64
from PIL import Image
import qrcode

async def print_qr_code(printer_ws, url, caption=None):
    """
    Generate and print a QR code.

    Args:
        printer_ws: WebSocket connection to printer
        url: URL to encode in QR code
        caption: Optional caption text
    """
    # Generate QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=4,
        border=2,
    )
    qr.add_data(url)
    qr.make(fit=True)

    # Get PIL image
    img = qr.make_image(fill_color="black", back_color="white").convert('L')

    # Resize (ensure width is multiple of 8)
    img = img.resize((128, 128), Image.Resampling.LANCZOS)

    # Apply dithering
    img = floyd_steinberg_dither(img)

    # Convert to packed bitmap
    bitmap_data = image_to_packed_bitmap(img)

    # Create WebSocket message
    message = {
        "kind": "print_bitmap",
        "width": 128,
        "height": 128,
        "data": base64.b64encode(bitmap_data).decode('utf-8')
    }

    if caption:
        message["caption"] = caption

    # Send to printer
    await printer_ws.send(json.dumps(message))
    print(f"QR code sent: {len(bitmap_data)} bytes")

# Usage
async def main():
    uri = "wss://your-printer-ws-endpoint"
    async with websockets.connect(uri) as websocket:
        await print_qr_code(
            websocket,
            "https://example.com",
            caption="Scan me!"
        )

asyncio.run(main())
```

## Complete Example: Print Logo

```python
async def print_logo(printer_ws, logo_path):
    """
    Load, process, and print a logo image.
    """
    # Load and convert to grayscale
    img = Image.open(logo_path).convert('L')

    # Resize for printer (max width 384 for 58mm paper)
    img = resize_for_printer(img, target_width=200)

    # Apply dithering
    img = floyd_steinberg_dither(img)

    # Convert to packed bitmap
    bitmap_data = image_to_packed_bitmap(img)

    # Create and send message
    message = {
        "kind": "print_bitmap",
        "width": img.width,
        "height": img.height,
        "data": base64.b64encode(bitmap_data).decode('utf-8')
    }

    await printer_ws.send(json.dumps(message))
    print(f"Logo sent: {img.width}x{img.height}, {len(bitmap_data)} bytes")
```

## Node.js Implementation

### Generate QR Code

```javascript
const QRCode = require('qrcode');
const sharp = require('sharp');

async function generateQRCode(url, size = 128) {
    // Generate QR code as buffer
    const qrBuffer = await QRCode.toBuffer(url, {
        width: size,
        margin: 2,
        color: {
            dark: '#000000',
            light: '#FFFFFF'
        }
    });

    return qrBuffer;
}
```

### Process Image

```javascript
async function processImageForPrinter(imageBuffer, targetWidth = 384) {
    // Ensure width is multiple of 8
    targetWidth = Math.floor(targetWidth / 8) * 8;

    // Resize and convert to grayscale
    const processed = await sharp(imageBuffer)
        .resize(targetWidth, null, {
            fit: 'inside',
            withoutEnlargement: true
        })
        .grayscale()
        .normalize()
        .toBuffer();

    return processed;
}
```

### Convert to Packed Bitmap

```javascript
function imageToPackedBitmap(imageBuffer, width, height) {
    // Sharp provides raw pixel data
    const { data } = sharp(imageBuffer)
        .raw()
        .toBuffer();

    const bytesPerLine = Math.floor(width / 8);
    const output = Buffer.alloc(bytesPerLine * height);

    for (let y = 0; y < height; y++) {
        for (let x = 0; x < width; x += 8) {
            const byteIndex = (y * bytesPerLine) + Math.floor(x / 8);
            let packedByte = 0;

            for (let bit = 0; bit < 8; bit++) {
                const pixelX = x + bit;
                if (pixelX < width) {
                    const pixelIndex = (y * width + pixelX);
                    const pixel = data[pixelIndex]; // 0-255

                    // If pixel is dark (< 128), set bit
                    if (pixel < 128) {
                        packedByte |= (1 << (7 - bit));
                    }
                }
            }

            output[byteIndex] = packedByte;
        }
    }

    return output;
}
```

### Send to Printer

```javascript
const WebSocket = require('ws');

async function sendBitmapToPrinter(wsUrl, imageBuffer, caption) {
    const metadata = await sharp(imageBuffer).metadata();
    const { width, height } = metadata;

    const bitmapData = imageToPackedBitmap(imageBuffer, width, height);
    const base64Data = bitmapData.toString('base64');

    const message = JSON.stringify({
        kind: 'print_bitmap',
        width: width,
        height: height,
        data: base64Data,
        caption: caption || ''
    });

    const ws = new WebSocket(wsUrl);

    return new Promise((resolve, reject) => {
        ws.on('open', () => {
            ws.send(message);
            console.log(`Bitmap sent: ${width}x${height}, ${bitmapData.length} bytes`);
        });

        ws.on('message', (data) => {
            const response = JSON.parse(data);
            if (response.kind === 'bitmap_printing') {
                console.log('Bitmap printed successfully');
                ws.close();
                resolve();
            } else if (response.kind === 'bitmap_error') {
                console.error('Error:', response.error);
                ws.close();
                reject(new Error(response.error));
            }
        });

        ws.on('error', reject);
    });
}
```

## Testing

### Test Image

Create a simple test bitmap (128×128 checkerboard):

```python
def create_test_bitmap():
    """Create a simple test pattern."""
    from PIL import Image, ImageDraw

    size = 128
    img = Image.new('L', (size, size), color=255)
    draw = ImageDraw.Draw(img)

    # Draw checkerboard
    square_size = 16
    for y in range(0, size, square_size):
        for x in range(0, size, square_size):
            if ((x // square_size) + (y // square_size)) % 2 == 0:
                draw.rectangle([x, y, x + square_size - 1, y + square_size - 1], fill=0)

    # Draw text
    draw.text((10, 56), "TEST", fill=0)

    return img
```

### Expected Output

```
Serial monitor should show:
  [Bitmap print message received]
  Bitmap: Decoded 2048 bytes
  Printing bitmap:
    Width: 128 px, Height: 128 px
    Data size: 2048 bytes
  Bitmap printed successfully
```

## Troubleshooting

### Image prints garbled or distorted
- **Check width multiple of 8**: Ensure width is divisible by 8
- **Verify bit order**: MSB (bit 7) should be leftmost pixel
- **Check byte order**: Ensure row-major order (top to bottom)

### Image prints inverted (colors swapped)
- **Check pixel values**: 1 = black (print), 0 = white (no print)
- PIL mode '1' uses 0=black, 255=white, so invert if needed

### Out of memory errors
- **Reduce image size**: Limit to ≤10KB (approx 200×200)
- **Process in chunks**: Don't load full image into RAM

### Printer buffer overflow
- The firmware chunks data in 256-byte blocks
- Ensure proper delays between chunks
- Check CTS pin is connected to GND

## Performance Considerations

### Image Size Guidelines

| Use Case | Recommended Size | Data Size |
|----------|------------------|-----------|
| QR Code | 128×128 - 144×144 | 2KB - 2.6KB |
| Small Icon | 32×32 - 64×64 | 128B - 512B |
| Medium Logo | 100×100 - 150×150 | 1.25KB - 2.8KB |
| Full Width | 384×200 | 9.6KB |

### Optimization Tips

1. **Pre-process images on server**: Do all heavy lifting server-side
2. **Use appropriate error correction**: For QR codes, use level M (15%)
3. **Limit dithering for small images**: < 64×64 may not need dithering
4. **Cache processed images**: Reuse common logos/QR codes
5. **Compress WebSocket data**: Use per-message compression if available

## Security Considerations

1. **Validate image dimensions**: Don't allow arbitrary large images
2. **Rate limiting**: Limit bitmap printing frequency per printer
3. **Sanitize captions**: Validate caption text to avoid printer exploits
4. **Memory limits**: Enforce strict size limits (50KB max)
5. **Authentication**: Ensure WebSocket connection is authenticated

## Additional Resources

- **ESC/POS Specification**: https://reference.epson-biz.com/modules/ref_escpos/index.html
- **QR Code Library**: https://github.com/lincolnloop/python-qrcode
- **PIL Documentation**: https://pillow.readthedocs.io/
- **Sharp (Node.js)**: https://sharp.pixelplumbing.com/

## Changelog

### Version 1.4.4
- Initial bitmap printing support
- Base64 encoded bitmap data via WebSocket
- Support for QR codes, logos, and icons
- Optional caption text
- 50KB image size limit
- Width must be multiple of 8
