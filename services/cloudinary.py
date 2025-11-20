import numpy as np
from PIL import Image, ImageStat, UnidentifiedImageError, ImageFilter
import io
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile, HTTPException
from uuid import uuid4
from typing import Any, Tuple, Optional
from config import settings
import asyncio
import threading
import re

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

class ImageValidator:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        # Document type configuration
        self.document_config = {
            'cnic': {
                'min_aspect': 1.4,
                'max_aspect': 1.7,
                'color_check': True,
                'max_size': (1200, 800),
                'text_pattern': re.compile(r'\d{5}-\d{7}-\d{1}'),
                'date_pattern': re.compile(r'(January|February|March|April|May|June|July|August|September|October|November|December)\s\d{1,2},\s\d{4}')
            },
            'license': {
                'min_aspect': 1.2,
                'max_aspect': 2.0,
                'max_size': (1000, 800)
            },
            'vehicle': {
                'min_aspect': 1.2,
                'max_aspect': 3.0,
                'max_size': (800, 600),
                'min_vehicle_confidence': 0.3  # Lowered threshold for vehicles
            },
            'user': {
                'min_aspect': 0.5,  # Relaxed for various portraits
                'max_aspect': 2.0,
                'max_size': (600, 600),
                'min_face_confidence': 0.4
            }
        }

        # Corrected Person/face detection classes (ImageNet classes)
        self.PERSON_CLASSES = {
            # Classes explicitly related to people
            574: ('face_mask', 0.3), # A common item worn by people
            278: ('sunglasses', 0.3), # Strong indicator of a face
            
            # Common clothing and accessory classes that imply a person
            281: ('t-shirt', 0.2),
            282: ('jean', 0.2),
            283: ('sweatshirt', 0.2),
            284: ('dress', 0.2),
            285: ('hat', 0.2),
            243: ('maillot', 0.2),     # Swimsuit - often indicates people
            245: ('jersey', 0.2),
            246: ('academic_gown', 0.2),
            247: ('poncho', 0.2),
            248: ('bulletproof_vest', 0.2),
            
            # A more generic human-like class if available
            701: ('man_in_suit', 0.3),
            793: ('ski_mask', 0.3), # implies a person wearing it
            
            # Add more person-related classes
            859: ('suit', 0.2),         # Common in profile photos
            481: ('neck_brace', 0.2),   # Could be detected in close-up portraits
            732: ('hair_slide', 0.2),   # Often present in portraits
            804: ('necklace', 0.2),     # Jewelry common in portraits
            571: ('glasses', 0.2),      # Common in portraits
            
            # This is the most reliable class for a person, but can be low confidence
            922: ('person', 0.4) # Lowered threshold for person detection
        }
        
        # Enhanced Vehicle classes mapping with lower thresholds
        self.VEHICLE_CLASSES = {
            # Cars
            436: ('ambulance', 0.2),
            479: ('cabriolet', 0.3), 
            511: ('convertible', 0.2),
            609: ('hatchback', 0.25), 
            627: ('limousine', 0.25),
            656: ('Model T', 0.2),
            705: ('passenger car', 0.2),
            751: ('racer', 0.25),
            817: ('sports car', 0.25),
            818: ('sedan', 0.25), 
            
            # Additional generic car classes for better coverage
            581: ('grille', 0.2),       # Car part that indicates vehicle presence
            407: ('airliner', 0.2),     # Any vehicle detection is valid
            675: ('minibus', 0.2),
            717: ('police car', 0.25),
            
            # Bikes and Motorcycles
            444: ('bicycle', 0.3),
            557: ('motorcycle', 0.3),
            670: ('moped', 0.25),        # Added moped class
            671: ('motor scooter', 0.25), # Added scooter class
            
            # Trucks and vans
            569: ('dump truck', 0.2),
            573: ('pickup truck', 0.2),
            654: ('minivan', 0.2),
            786: ('snowplow', 0.2),
            864: ('tow truck', 0.25),
            867: ('trailer truck', 0.2), # Added trailer truck
            555: ('fire truck', 0.2),    # Added fire truck
            
            # Buses and public transport
            779: ('school bus', 0.25),
            450: ('bus', 0.25),
            
            # Additional vehicle-related classes
            518: ('crane', 0.2),         # Construction vehicle
            661: ('military vehicle', 0.2),
            468: ('auto mirror', 0.2),   # Car part
            479: ('car mirror', 0.2),    # Car part
            627: ('car wheel', 0.2),     # Car part
            732: ('steering wheel', 0.2), # Car part
            920: ('vehicle hood', 0.2),   # Car part
            725: ('bumper', 0.2),        # Car part
            
            # Generic vehicle indicators
            757: ('car interior', 0.2),  # Inside of a vehicle
            895: ('windshield', 0.2),    # Vehicle part
            920: ('hood', 0.2),          # Vehicle part
            468: ('mirror', 0.2)         # Vehicle part
        }

        # Defer ONNX model initialization
        self.ml_enabled = False
        self.session = None
        self.input_name = None
        self.input_shape = None
        self._model_lock = threading.Lock()

    def _initialize_model(self):
        """Initializes the ONNX model if it hasn't been already."""
        if settings.USE_ML_VALIDATION:
            with self._model_lock:
                if self.session is None:
                    print("[INFO] Initializing ONNX model for the first time...")
                    import onnxruntime
                    try:
                        self.session = onnxruntime.InferenceSession(
                            "mobilenetv2-7.onnx",
                            providers=['CPUExecutionProvider']
                        )
                        self.input_name = self.session.get_inputs()[0].name
                        self.input_shape = self.session.get_inputs()[0].shape
                        self.ml_enabled = True
                    except Exception as e:
                        print(f"ONNX model initialization failed: {e}")
                        self.ml_enabled = False

    def resize_image(self, image: Image.Image, max_size: Tuple[int, int]) -> Image.Image:
        """Optimized image resizing with aspect ratio preservation"""
        if image.size[0] > max_size[0] or image.size[1] > max_size[1]:
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
        return image

    async def validate(self, file: UploadFile, expected_type: str) -> bool:
        """Comprehensive image validation with timeout handling"""
        try:
            # Read with timeout
            contents = await asyncio.wait_for(file.read(), timeout=5.0)
            await file.seek(0)
            
            with Image.open(io.BytesIO(contents)) as img:
                # Basic format check
                if img.format not in ('JPEG', 'PNG'):
                    return False
                
                # Special handling for documents
                if expected_type in ('cnic', 'license'):
                    return await self._validate_document(img, expected_type)
                
                # For other types, use hybrid validation
                return await self._validate_general(img, expected_type)
                
        except asyncio.TimeoutError:
            print("Validation timed out")
            return False
        except UnidentifiedImageError:
            return False
        except Exception as e:
            print(f"Validation error: {e}")
            return False

    async def _validate_document(self, img: Image.Image, doc_type: str) -> bool:
        """Specialized document validation"""
        config = self.document_config[doc_type]
        w, h = img.size
        aspect_ratio = w / h
        
        # Aspect ratio check
        if not (config['min_aspect'] <= aspect_ratio <= config['max_aspect']):
            return False
        
        # CNIC-specific checks
        if doc_type == 'cnic':
            # Color check
            dominant_color = ImageStat.Stat(img).mean[:3]
            if not (dominant_color[0] > 200 and dominant_color[1] > 180):
                return False
            
            # Text pattern check (simulated - replace with actual OCR in production)
            if not self._simulate_text_check(img, config):
                return False
        
        return True

    def _simulate_text_check(self, img: Image.Image, config: dict) -> bool:
        """Simulate text pattern matching (replace with actual OCR)"""
        # In production, use:
        # text = pytesseract.image_to_string(img)
        mock_text = "Dawn\nالوظيفة للسكان\nالأغاثة لها\n32103-9963008-2"
        return (config['text_pattern'].search(mock_text) is not None and \
               config['date_pattern'].search(mock_text) is not None)

    async def _validate_general(self, img: Image.Image, expected_type: str) -> bool:
        """Hybrid validation using ML and heuristics"""
        # First apply heuristic checks
        if expected_type == 'other':
            return True
        w, h = img.size
        aspect_ratio = w / h
        
        # Vehicle-specific checks
        if expected_type == 'vehicle':
            # Aspect ratio check (vehicles are typically wider than tall)
            if not 1.2 <= aspect_ratio <= 3.0:
                print(f"Failed aspect ratio check: {aspect_ratio:.2f}")
                return False
            
            # Additional vehicle checks (color, edges, etc)
            if not self._is_likely_vehicle(img):
                print("Failed secondary vehicle checks")
                return False
        
        # Person-specific checks - relax aspect ratio constraints
        elif expected_type == 'user':
            if not 0.5 <= aspect_ratio <= 2.0:  # More flexible for portraits
                print(f"Failed user aspect ratio: {aspect_ratio:.2f}")
                return False
        
        # Then apply ML validation if enabled
        if settings.USE_ML_VALIDATION:
            self._initialize_model()
            if not self.ml_enabled:
                return True  # Fallback to heuristics if ML failed to load
            try:
                ml_result = await asyncio.wait_for(
                    self._ml_analysis(img, expected_type),
                    timeout=2.0
                )
                if not ml_result:
                    print("ML validation failed")
                return ml_result
            except (asyncio.TimeoutError, Exception) as e:
                print(f"ML analysis failed: {e}")
                # For user images, be more permissive if ML fails
                if expected_type == 'user':
                    return True  # Accept based on heuristics alone
                return False
        
        # If ML not enabled, accept based on heuristics alone
        return True

    def _is_likely_vehicle(self, img: Image.Image) -> bool:
        """Additional vehicle verification checks"""
        try:
            # Check for vehicle-like colors (grayscale or common car colors)
            dominant_color = ImageStat.Stat(img).mean[:3]
            r, g, b = dominant_color
            
            # Common vehicle color checks
            is_grayscale = abs(r - g) < 30 and abs(g - b) < 30  # White, black, silver
            is_red = r > g*1.5 and r > b*1.5
            is_blue = b > r*1.2 and b > g*1.2
            is_green = g > r*1.2 and g > b*1.2
            
            if not (is_grayscale or is_red or is_blue or is_green):
                print(f"Unusual vehicle color: {dominant_color}")
                return False
            
            return True
        except Exception as e:
            print(f"Vehicle check error: {e}")
            return False

    async def _ml_analysis(self, img: Image.Image, expected_type: str) -> bool:
        """Run ML prediction with proper validation"""
        try:
            if not self.session:
                print("[WARNING] ML analysis called but session is not initialized.")
                return True  # Default to passing if model isn't ready

            # Convert to RGB if needed
            if img.mode != 'RGB':
                img = img.convert('RGB')
                
            # Resize to model's expected input size (224x224)
            img = img.resize((224, 224))
            
            # Convert to numpy array with explicit float32 type
            img_array = np.array(img, dtype=np.float32)
            
            # Normalize (ImageNet normalization)
            img_array = img_array / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            img_array = (img_array - mean) / std
            
            # Change array shape from HWC to CHW and add batch dimension
            img_array = np.transpose(img_array, (2, 0, 1))  # HWC to CHW
            img_array = np.expand_dims(img_array, axis=0)   # Add batch dimension
            
            # Run inference
            results = self.session.run(None, {self.input_name: img_array})
            logits = results[0][0]  # Get raw output logits
            
            # Apply softmax to convert logits to probabilities
            exp_logits = np.exp(logits - np.max(logits))
            probabilities = exp_logits / np.sum(exp_logits)
            
            # Debug: show top 5 classes
            top_classes = np.argsort(probabilities)[-5:][::-1]
            print(f"Top 5 detected classes: {top_classes}")
            print(f"Top probabilities: {[probabilities[i] for i in top_classes]}")
            
            # Person detection logic
            if expected_type == 'user':
                detected_persons = []
                # Check top 5 classes for any match with our PERSON_CLASSES
                for class_idx in top_classes:
                    if class_idx in self.PERSON_CLASSES:
                        person_type, min_confidence = self.PERSON_CLASSES[class_idx]
                        confidence = probabilities[class_idx]
                        if confidence > min_confidence:
                            detected_persons.append((person_type, confidence))
                            print(f"Detected {person_type} (class {class_idx}) with probability {confidence:.4f}")
                
                if detected_persons:
                    print(f"Accepted person detection with types: {detected_persons}")
                    return True
                else:
                    print("No person detected with sufficient confidence")
                    # Fallback: check if it might be a person based on other features
                    return self._is_likely_person(img)
            
            # Vehicle detection logic
            elif expected_type == 'vehicle':
                detected_vehicles = []
                # Check top 5 classes for any match with our VEHICLE_CLASSES
                for class_idx in top_classes:
                    if class_idx in self.VEHICLE_CLASSES:
                        vehicle_type, min_confidence = self.VEHICLE_CLASSES[class_idx]
                        confidence = probabilities[class_idx]
                        if confidence > min_confidence:
                            detected_vehicles.append((vehicle_type, confidence))
                            print(f"Detected {vehicle_type} (class {class_idx}) with probability {confidence:.4f}")
                
                if detected_vehicles:
                    print(f"Accepted vehicle detection with types: {detected_vehicles}")
                    return True
                else:
                    print("No vehicle detected with sufficient confidence")
                    return False
            
            return False
                
        except Exception as e:
            print(f"ML analysis error: {e}")
            return False

    def _is_likely_person(self, img: Image.Image) -> bool:
        """Fallback person detection using heuristics"""
        try:
            # Check for skin tone colors in a downsampled image for speed
            img_small = img.resize((100, 100))
            
            # Convert to HSV for better skin tone detection
            img_hsv = img_small.convert('HSV')
            hsv_pixels = np.array(img_hsv)
            
            # Skin tone ranges in HSV
            h, s, v = hsv_pixels[:,:,0], hsv_pixels[:,:,1], hsv_pixels[:,:,2]
            
            # More refined skin mask
            skin_mask = (
                (h > 0) & (h < 35) &    # Hue range for skin tones (yellow-red)
                (s > 20) & (s < 150) &  # Saturation range (avoids pure white/grey/black)
                (v > 40) & (v < 255)    # Value range (avoids shadows and overexposure)
            )
            
            skin_percentage = np.mean(skin_mask)
            print(f"Skin tone percentage: {skin_percentage:.2f}")
            
            # If a significant amount of the image is skin tone, it's likely a person
            return skin_percentage > 0.02  # Lowered threshold for skin tone detection
            
        except Exception as e:
            print(f"Person check error: {e}")
            return False


async def upload_image(file: UploadFile, expected_type: str = 'other') -> str:
    """
    Optimized image upload handler with:
    - In-memory processing
    - Comprehensive validation
    - Proper timeout handling
    """
    # Lazily initialize a singleton validator to avoid reloading the model
    with ImageValidator._lock:
        if ImageValidator._instance is None:
            print("[INFO] Creating ImageValidator singleton instance.")
            ImageValidator._instance = ImageValidator()
    
    validator = ImageValidator._instance
    
    # Validate with timeout
    try:
        is_valid = await asyncio.wait_for(
            validator.validate(file, expected_type),
            timeout=8.0
        )
        if not is_valid:
            error_msg = {
                'cnic': "Invalid CNIC image. Ensure the entire card is visible with clear text.",
                'license': "Invalid license image. Please provide a clear photo of the full document.",
                'vehicle': "Image doesn't appear to be a vehicle. Please provide a clear photo of the vehicle.",
                'user': "Image doesn't appear to be a person. Please provide a clear portrait."
            }.get(expected_type, "Image validation failed")
            
            raise HTTPException(400, detail=error_msg)
    except asyncio.TimeoutError:
        raise HTTPException(400, "Image validation timed out")

    # Reset and upload
    await file.seek(0)
    filename = f"{uuid4().hex}_{file.filename}"
    
    try:
        # Direct in-memory upload for all environments
        result = await asyncio.wait_for(
            asyncio.to_thread(
                cloudinary.uploader.upload,
                file.file,
                public_id=filename,
                quality="auto:good",
                timeout=10
            ),
            timeout=15.0
        )
        return result["secure_url"]
    
    except asyncio.TimeoutError:
        raise HTTPException(500, "Image upload timed out")
    except Exception as e:
        raise HTTPException(500, f"Upload failed: {str(e)}")