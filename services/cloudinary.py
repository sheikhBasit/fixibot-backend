import onnxruntime
import numpy as np
from PIL import Image, ImageStat, UnidentifiedImageError, ImageFilter
import io
import os
import shutil
import cloudinary
import cloudinary.uploader
from fastapi import UploadFile, HTTPException
from uuid import uuid4
from typing import Any, Tuple, Optional
from config import settings
import asyncio
import re

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET,
    secure=True
)

class ImageValidator:
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
                'min_vehicle_confidence': 0.65  # Higher threshold for vehicles
            },
            'user': {
                'min_aspect': 0.7,  # More flexible for portraits
                'max_aspect': 1.5,
                'max_size': (600, 600),
                'min_face_confidence': 0.4
            }
        }

        # Person/face detection classes (ImageNet classes)
        self.PERSON_CLASSES = {
            0: ('person', 0.3),       # General person
            1: ('face', 0.4),         # Face
            2: ('portrait', 0.3),     # Portrait
            3: ('head', 0.3),         # Head
            4: ('human', 0.3),        # Human
            # Common person-related ImageNet classes
            151: ('chihuahua', 0.1),   # Sometimes misclassified as small faces
            152: ('japanese_spaniel', 0.1),
            153: ('maltese_dog', 0.1),
            154: ('pekinese', 0.1),
            155: ('shih-tzu', 0.1),
            156: ('blenheim_spaniel', 0.1),
            157: ('papillon', 0.1),
            158: ('toy_terrier', 0.1),
            159: ('rhodesian_ridgeback', 0.1),
            160: ('afghan_hound', 0.1),
            218: ('standard_poodle', 0.1),
            219: ('miniature_poodle', 0.1),
            220: ('toy_poodle', 0.1),
            221: ('mexican_hairless', 0.1),
            # Actual person classes
            243: ('maillot', 0.3),     # Swimsuit - often indicates people
            244: ('sweatshirt', 0.3),
            245: ('jersey', 0.3),
            246: ('academic_gown', 0.3),
            247: ('poncho', 0.3),
            248: ('bulletproof_vest', 0.3),
            249: ('red_wine', 0.1),    # Sometimes in portraits
            278: ('sunglasses', 0.4),  # Strong indicator of face
            
        }

        # Vehicle classes mapping
        self.VEHICLE_CLASSES = {
            # Cars
            656: ('car', 0.4),   # Model T
            817: ('car', 0.5),   # Sports car
            511: ('car', 0.4),   # Convertible
            705: ('car', 0.4),   # Passenger car
            627: ('car', 0.5),   # Limousine
            436: ('car', 0.3),   # Ambulance
            
            # Bikes
            444: ('bike', 0.6),  # Bicycle
            557: ('bike', 0.7),  # Motorcycle
            
            # Trucks
            864: ('truck', 0.5), # Tow truck
            569: ('truck', 0.4), # Dump truck
            573: ('truck', 0.4), # Pickup truck
            
            # Vans/SUVs
            654: ('van', 0.4),   # Minivan
            757: ('suv', 0.4),   # RV
            
            # Buses
            779: ('bus', 0.5),   # School bus
            450: ('bus', 0.5)    # Regular bus
        }

        # Initialize ONNX model if available
        self.ml_enabled = False
        if settings.USE_ML_VALIDATION:
            try:
                self.session = onnxruntime.InferenceSession(
                    "mobilenetv2-7.onnx",
                    providers=['CPUExecutionProvider']
                )
                self.input_name = self.session.get_inputs()[0].name
                self.input_shape = self.session.get_inputs()[0].shape
                self.ml_enabled = True
                print(f"ML model loaded. Expected input shape: {self.input_shape}")
            except Exception as e:
                print(f"ONNX model initialization failed: {e}")

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
            if not 0.7 <= aspect_ratio <= 1.5:  # More flexible for portraits
                print(f"Failed user aspect ratio: {aspect_ratio:.2f}")
                return False
        
        # Then apply ML validation if enabled
        if self.ml_enabled:
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
                for class_idx, (person_type, min_confidence) in self.PERSON_CLASSES.items():
                    if class_idx < len(probabilities):
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
                for class_idx, (vehicle_type, min_confidence) in self.VEHICLE_CLASSES.items():
                    if class_idx < len(probabilities):
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
            # Check for skin tone colors
            img_small = img.resize((100, 100))  # Downsample for speed
            pixels = np.array(img_small)
            
            # Convert to HSV for better skin detection
            img_hsv = Image.fromarray(pixels).convert('HSV')
            hsv_pixels = np.array(img_hsv)
            
            # Skin tone ranges in HSV
            h, s, v = hsv_pixels[:,:,0], hsv_pixels[:,:,1], hsv_pixels[:,:,2]
            skin_mask = ((h > 0) & (h < 35)) & ((s > 20) & (s < 255)) & ((v > 40) & (v < 255))
            
            skin_percentage = np.mean(skin_mask)
            print(f"Skin tone percentage: {skin_percentage:.2f}")
            
            # If significant skin tones detected, likely a person
            return skin_percentage > 0.15
            
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
    validator = ImageValidator()
    
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