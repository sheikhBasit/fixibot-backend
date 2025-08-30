# from transformers import CLIPProcessor, CLIPModel
# import torch
# from PIL import Image
# import numpy as np

# clip_model = CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
# clip_processor = CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

# def embed_image(image_data):
#     """Embed image using CLIP"""
#     if isinstance(image_data, str):  # If path
#         image = Image.open(image_data).convert("RGB")
#     else:  # If PIL Image
#         image = image_data

#     inputs = clip_processor(images=image, return_tensors="pt")
#     with torch.no_grad():
#         features = clip_model.get_image_features(**inputs)
#         features = features / features.norm(dim=-1, keepdim=True)
#         return features.squeeze().numpy()

# def embed_text(text):
#     """Embed text using CLIP."""
#     inputs = clip_processor(
#         text=text,
#         return_tensors="pt",
#         padding=True,
#         truncation=True,
#         max_length=77  # CLIP's max token length
#     )
#     with torch.no_grad():
#         features = clip_model.get_text_features(**inputs)
#         features = features / features.norm(dim=-1, keepdim=True)
#         return features.squeeze().numpy()