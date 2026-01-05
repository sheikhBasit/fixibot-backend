import asyncio
import io
import base64
import faiss
from pathlib import Path
from typing import Tuple
import fitz
import numpy as np
from PIL import Image
from uuid import uuid4
from langchain_core.documents import Document
from langchain_community.vectorstores import FAISS
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_text_splitters import RecursiveCharacterTextSplitter
# Ensure these are imported from your actual service file
from services.multimodal_embeddings import embed_text, embed_image
from services.vector_cache import CacheLoadError, VectorCache

async def process_pdf_with_images(pdf_path: str, cache_dir: str = ".vector_cache", force_reprocess: bool = False) -> Tuple[FAISS, dict]:
    cache = VectorCache(cache_dir)
    cache_key = cache.get_cache_key(pdf_path)

    if not force_reprocess and cache.cache_exists(cache_key):
        try:
            return cache.load_from_cache(cache_key)
        except CacheLoadError:
            pass

    doc = fitz.open(pdf_path)
    all_docs = []
    embedding_tasks = []
    image_data_store = {}
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=300)

    try:
        for i, page in enumerate(doc):
            # Process Text
            text = page.get_text()
            if text.strip():
                pdf_name = Path(pdf_path).stem
                temp_doc = Document(page_content=text, metadata={"page": i, "type": "text", "source": pdf_name})
                for chunk in text_splitter.split_documents([temp_doc]):
                    all_docs.append(chunk)
                    embedding_tasks.append(embed_text(chunk.page_content))

            # Process Images
            for img_index, img in enumerate(page.get_images(full=True)):
                try:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    pil_image = Image.open(io.BytesIO(base_image["image"])).convert("RGB")
                    image_id = f"page_{i}_img_{img_index}"

                    buffered = io.BytesIO()
                    pil_image.save(buffered, format="PNG")
                    image_data_store[image_id] = base64.b64encode(buffered.getvalue()).decode()

                    all_docs.append(Document(
                        page_content=f"[Image: {image_id}]",
                        metadata={"page": i, "type": "image", "image_id": image_id, "source": pdf_name}
                    ))
                    embedding_tasks.append(embed_image(pil_image))
                except Exception as e:
                    print(f"Error processing image {img_index} on page {i}: {e}")

        if not all_docs:
            raise ValueError("No content found in PDF.")

        # Execute embeddings in parallel
        all_embeddings = await asyncio.gather(*embedding_tasks)

        # Build HNSW Index
        dim = 512 
        index = faiss.IndexHNSWFlat(dim, 32)
        index.add(np.array(all_embeddings).astype('float32'))

        # Build Docstore and ID mapping
        docstore = InMemoryDocstore({})
        index_to_docstore_id = {}
        for idx, d in enumerate(all_docs):
            uid = str(uuid4())
            docstore.add({uid: d})
            index_to_docstore_id[idx] = uid

        vector_store = FAISS(
            embedding_function=embed_text,
            index=index,
            docstore=docstore,
            index_to_docstore_id=index_to_docstore_id
        )
     
        cache.save_to_cache(cache_key, vector_store, image_data_store)
        return vector_store, image_data_store
    finally:
        doc.close()


# import io
# import base64
# from pathlib import Path
# from typing import Tuple
# import fitz
# import numpy as np
# from PIL import Image
# from langchain_core.documents import Document
# from langchain_community.vectorstores import FAISS
# from langchain_text_splitters import RecursiveCharacterTextSplitter
# from services.multimodal_embeddings import embed_text, embed_image
# from services.vector_cache import CacheLoadError, VectorCache

# def process_pdf_with_images(pdf_path: str, cache_dir: str = ".vector_cache", force_reprocess: bool = False) -> Tuple[FAISS, dict]:
#     """
#     Process a PDF (text + images) and create a FAISS vectorstore with proper embedding function.
#     Returns: vector_store, image_data_store
#     """
#     cache = VectorCache(cache_dir)
#     cache_key = cache.get_cache_key(pdf_path)

#     # Load from cache if exists
#     if not force_reprocess and cache.cache_exists(cache_key):
#         try:
#             print("Loading vectorstore from cache...")
#             return cache.load_from_cache(cache_key)
#         except CacheLoadError:
#             print("Cache load failed, reprocessing PDF.")

#     print(f"Processing PDF: {pdf_path}")
#     doc = fitz.open(pdf_path)
#     all_docs = []
#     all_embeddings = []
#     image_data_store = {}
#     text_splitter = RecursiveCharacterTextSplitter(chunk_size=1200, chunk_overlap=300, separators=["\n\n", "Query", "\n", " ", ""])

#     try:
#         for i, page in enumerate(doc):
#             # --- Text processing ---
#             text = page.get_text()
#             if text.strip():
#                 pdf_name = Path(pdf_path).stem
#                 temp_doc = Document(
#                     page_content=text,
#                     metadata={"page": i, "type": "text", "source": pdf_name}
#                 )
#                 text_chunks = text_splitter.split_documents([temp_doc])

#                 for chunk in text_chunks:
#                     try:
#                         emb = embed_text(chunk.page_content)  # must return np.array
#                         all_embeddings.append(emb)
#                         all_docs.append(chunk)
#                     except Exception as e:
#                         print(f"Error embedding text chunk: {e}")

#             # --- Image processing ---
#             images = page.get_images(full=True)
#             for img_index, img in enumerate(images):
#                 try:
#                     xref = img[0]
#                     base_image = doc.extract_image(xref)
#                     image_bytes = base_image["image"]

#                     pil_image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
#                     image_id = f"page_{i}_img_{img_index}"

#                     # store as base64 for later use
#                     buffered = io.BytesIO()
#                     pil_image.save(buffered, format="PNG")
#                     img_base64 = base64.b64encode(buffered.getvalue()).decode()
#                     image_data_store[image_id] = img_base64

#                     emb = embed_image(pil_image)
#                     all_embeddings.append(emb)

#                     image_doc = Document(
#                         page_content=f"[Image: {image_id}]",
#                         metadata={"page": i, "type": "image", "image_id": image_id, "source": pdf_name}
#                     )
#                     all_docs.append(image_doc)

#                 except Exception as e:
#                     print(f"Error processing image {img_index} on page {i}: {e}")

#         if not all_docs:
#             raise ValueError("No content found in PDF.")

#         # --- Create FAISS vectorstore ---
#         vector_store = FAISS.from_embeddings(
#             text_embeddings=[(doc.page_content, emb) for doc, emb in zip(all_docs, all_embeddings)],
#             embedding=embed_text,  # ⚡ MUST assign embedding function
#             metadatas=[doc.metadata for doc in all_docs]
#         )

#         # Save to cache
#         cache.save_to_cache(cache_key, vector_store, image_data_store)
#         return vector_store, image_data_store

#     finally:
#         doc.close()
