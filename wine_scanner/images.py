import base64
import io
import warnings

from PIL import Image, ImageOps, UnidentifiedImageError

try:
    import pillow_heif

    pillow_heif.register_heif_opener()
    HEIC = True
except ImportError:
    HEIC = False

FORMATS = {"JPEG", "PNG", "WEBP", "BMP", "TIFF", "MPO"} | ({"HEIF"} if HEIC else set())


class ImageError(ValueError):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def decode(data: bytes, max_bytes: int, max_pixels: int) -> Image.Image:
    if not data:
        raise ImageError(400, "empty image")
    if len(data) > max_bytes:
        raise ImageError(413, "image exceeds byte limit")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            im = Image.open(io.BytesIO(data))
            if im.format not in FORMATS:
                raise ImageError(415, f"unsupported image format: {im.format}")
            if im.width * im.height > max_pixels:
                raise ImageError(413, "image exceeds pixel limit")
            im.load()
    except ImageError:
        raise
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError, Image.DecompressionBombWarning) as e:
        raise ImageError(422, f"cannot decode image: {type(e).__name__}") from e
    return to_rgb(im)


def to_rgb(im: Image.Image) -> Image.Image:
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        return bg
    return im.convert("RGB")


def jpeg_data_uri(im: Image.Image, side: int, quality: int = 90) -> str:
    s = side / max(im.size)
    if s < 1:
        im = im.resize((int(im.width * s), int(im.height * s)), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=quality)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
