from threading import Lock
from transformers import LlavaForConditionalGeneration, LlavaProcessor
from transformers.utils.quantization_config import BitsAndBytesConfig
import torch
from PIL import Image
from pathlib import Path
import logging
from typing import Optional, Union
from os import PathLike, fspath
from io import BytesIO
import requests
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Module-level model and processor
_processor: Optional[LlavaProcessor] = None
_model: Optional[LlavaForConditionalGeneration] = None

_lock = Lock()

def initialize_llava_model() -> None:
    """Thread-safe initialization of the LLaVA model and processor."""
    global _processor, _model
    with _lock:
        if _processor is not None and _model is not None:
            return

        try:
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_use_double_quant=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16
            )

            _processor = LlavaProcessor.from_pretrained( # type: ignore
                "llava-hf/llava-1.5-7b-hf"
            )

            _model = LlavaForConditionalGeneration.from_pretrained( # type: ignore
                "llava-hf/llava-1.5-7b-hf",
                quantization_config=bnb_config,
                device_map="auto"
            )
        except Exception as e:
            logger.error(f"Error loading LLaVA model: {e}", exc_info=True)
            raise RuntimeError("Failed to load LLaVA model") from e

def is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL."""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def download_image(url: str) -> bytes:
    """Download image from URL and return as bytes."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        content_type = response.headers.get('content-type', '').lower()
        if not content_type.startswith('image/'):
            raise ValueError("URL does not point to an image")
        return response.content
    except Exception as e:
        logger.error(f"Failed to download image from URL: {e}", exc_info=True)
        raise

def analyze_image(
    image: Union[str, PathLike[str], Image.Image, bytes],
    question: str = "What's wrong in this image?"
) -> str:
    """Analyze an image using the LLaVA model.
    
    Args:
        image: URL, file path, PIL image, or raw bytes
        question: The question to ask about the image
        
    Returns:
        str: Analysis result or error message
    """
    if _processor is None or _model is None:
        return "Image analysis unavailable (model not loaded)"

    try:
        img: Image.Image

        if isinstance(image, str) and is_valid_url(image):
            image_bytes = download_image(image)
            img = Image.open(BytesIO(image_bytes)).convert("RGB")
        elif isinstance(image, (str, PathLike)):
            path = fspath(image)
            if not Path(path).exists():
                return "Image file not found"
            img = Image.open(path).convert("RGB")
        elif isinstance(image, bytes):
            img = Image.open(BytesIO(image)).convert("RGB")
        elif isinstance(image, Image.Image):
            img = image.convert("RGB")
        else:
            return "Unsupported image input type"

        # Resize image
        img = img.resize((336, 336))

        # Prepare inputs
        inputs = _processor(
            text=question,
            images=img,
            return_tensors="pt"
        ).to(_model.device) # type: ignore

        output = _model.generate( # type: ignore
            **inputs,
            max_new_tokens=200,
            do_sample=True,
            temperature=0.2
        )

        # Use processor.tokenizer.decode (not processor itself)
        return _processor.tokenizer.decode(output[0], skip_special_tokens=True) # type: ignore

    except Exception as e:
        logger.error(f"Image analysis error: {e}", exc_info=True)
        return f"Failed to analyze image: {str(e)}"
