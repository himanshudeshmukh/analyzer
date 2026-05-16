# Fashion Image Analyzer API
 
 A production-oriented FastAPI service for batch clothing-image analysis.
 
 It accepts a list of images and performs this workflow:
 
 1. Removes the background with `rembg`.
 2. Detects the garment region.
 3. Predicts garment metadata such as category, sleeve length, neckline, waist rise, length, fit, style, pattern, material, closure, viewpoint, and color family.
 4. Returns the processed image plus structured metadata.
 
 The code is intentionally **heavily commented** so each important line and block is easy to understand.
 
 ## Architecture
 
 This project uses a layered design instead of a single script.
 
 - **API layer**: `app/main.py`
   - Owns HTTP concerns, request validation, file reading, and OpenAPI docs.
 - **Application layer**: `app/pipeline.py`
   - Orchestrates the end-to-end workflow.
 - **Domain / contract layer**: `app/models.py`
   - Defines strongly typed request and response models.
 - **Infrastructure layer**: `app/services.py`
   - Implements background removal, detection, CLIP attribute inference, color extraction, and artifact storage.
 - **Configuration layer**: `app/settings.py`
   - Centralizes runtime settings.
 
 ## SOLID and design principles used
 
 - **Single Responsibility Principle**
   - The API only handles HTTP.
   - The pipeline only orchestrates.
   - The services module owns model integrations.
   - The models module owns schema definitions.
 - **Open/Closed Principle**
   - You can swap the detector, background remover, or artifact store without rewriting the pipeline.
 - **Liskov Substitution Principle**
   - The pipeline depends on abstractions, so any compatible detector or background remover can be substituted.
 - **Interface Segregation Principle**
   - Small protocols are used for `BackgroundRemover`, `GarmentDetector`, and `ArtifactStore`.
 - **Dependency Inversion Principle**
   - The application layer depends on abstractions, not directly on `rembg` or CLIP internals.
 
 ## Detection strategy
 
 The service supports two detector modes:
 
 ### 1. Preferred mode: DeepFashion2 TorchScript detector
 
 If you provide a path through `DEEPFASHION2_TORCHSCRIPT_PATH`, the service loads that detector and uses it as the primary detector.
 
 Expected output shape is compatible with common torchvision-style detection models:
 
 ```python
 {
     "boxes": Tensor[N, 4],
     "labels": Tensor[N],
     "scores": Tensor[N],
 }
 ```
 
 The label ids are mapped to the 13 DeepFashion2 categories.
 
 ### 2. Built-in fallback mode: alpha mask + CLIP
 
 If no DeepFashion2 checkpoint is configured, or if the primary detector returns no boxes, the service:
 
 - uses the transparent foreground extent from the background-removed image as the garment box,
 - classifies the crop into a DeepFashion2 category using CLIP zero-shot prompts.
 
 This makes the API runnable out of the box, especially for single-item or catalog-style images.
 
 ## Why CLIP is used for attributes
 
 You asked for broad clothing metadata such as sleeve, waist, fit, pattern, material, and style.
 
 Instead of training a separate classifier head for every attribute, this design uses CLIP-style zero-shot prompts. That keeps the system flexible and easier to extend.
 
 You can add new attributes by adding new prompt sets in `GarmentMetadataBuilder`.
 
 ## Practical limitation
 
 A single image cannot always reveal hidden or ambiguous details.
 
 Examples:
 
 - exact fiber composition,
 - back-side construction,
 - interior lining,
 - hidden closures,
 - attributes obscured by pose or folds.
 
 For that reason, the API returns `null` for any attribute that does not meet the configured confidence threshold.
 
 ## Project structure
 
 ```text
 fashion_analyzer/
 ├── README.md
 ├── requirements.txt
 ├── .env.example
 └── app/
     ├── __init__.py
     ├── main.py
     ├── models.py
     ├── pipeline.py
     ├── services.py
     └── settings.py
 ```
 
 ## Installation
 
 ```bash
 python -m venv .venv
 source .venv/bin/activate
 pip install -r requirements.txt
 cp .env.example .env
 ```
 
 ## Run the API
 
 ```bash
 uvicorn app.main:app --reload
 ```
 
 Then open:
 
 - `http://127.0.0.1:8000/docs`
 - `http://127.0.0.1:8000/health`
 
 ## Main endpoint
 
 ### `POST /v1/analyze-images`
 
 Consumes `multipart/form-data`.
 
 #### Form fields
 
 - `files`: repeated image field
 - `include_base64`: optional query parameter
 
 ### Example request
 
 ```bash
 curl -X POST "http://127.0.0.1:8000/v1/analyze-images?include_base64=false" \
   -F "files=@shirt.jpg" \
   -F "files=@dress.png"
 ```
 
 ### Example response shape
 
 ```json
 {
   "batch_id": "2a4d0f1e4a62494e88d70f8d2b75d394",
   "total_images": 2,
   "succeeded": 2,
   "failed": 0,
   "results": [
     {
       "original_filename": "shirt.jpg",
       "status": "succeeded",
       "image_width": 1024,
       "image_height": 1024,
       "processed_image_url": "/artifacts/processed/shirt-abc123.png",
       "processed_image_base64": null,
       "garments": [
         {
           "detection_id": "b9c0...",
           "bounding_box": {
             "left": 120,
             "top": 44,
             "right": 910,
             "bottom": 980
           },
           "detection_confidence": 0.91,
           "detector_name": "alpha_mask_clip_fallback",
           "metadata": {
             "garment_group": "top",
             "category": {
               "label": "short sleeve top",
               "confidence": 0.91,
               "alternatives": [],
               "applicable": true,
               "source_model": "alpha_mask_clip_fallback",
               "note": "Category provided by the detector."
             },
             "sleeve_length": {
               "label": "short sleeve",
               "confidence": 0.91,
               "alternatives": [],
               "applicable": true,
               "source_model": "alpha_mask_clip_fallback_derived",
               "note": "Derived directly from the garment category."
             },
             "neckline": {
               "label": "crew neck",
               "confidence": 0.63,
               "alternatives": [
                 {"label": "crew neck", "confidence": 0.63},
                 {"label": "v-neck", "confidence": 0.21}
               ],
               "applicable": true,
               "source_model": "openai/clip-vit-base-patch32",
               "note": null
             },
             "waist_rise": {
               "label": null,
               "confidence": null,
               "alternatives": [],
               "applicable": false,
               "source_model": "openai/clip-vit-base-patch32",
               "note": "Waist rise is predicted only for bottom garments."
             },
             "length": {"label": "regular length", "confidence": 0.42, "alternatives": [], "applicable": true, "source_model": "openai/clip-vit-base-patch32", "note": null},
             "fit": {"label": "regular", "confidence": 0.51, "alternatives": [], "applicable": true, "source_model": "openai/clip-vit-base-patch32", "note": null},
             "fashion_style": {"label": "casual", "confidence": 0.59, "alternatives": [], "applicable": true, "source_model": "openai/clip-vit-base-patch32", "note": null},
             "pattern": {"label": "solid", "confidence": 0.74, "alternatives": [], "applicable": true, "source_model": "openai/clip-vit-base-patch32", "note": null},
             "material": {"label": "cotton", "confidence": 0.38, "alternatives": [], "applicable": true, "source_model": "openai/clip-vit-base-patch32", "note": null},
             "closure": {"label": null, "confidence": null, "alternatives": [], "applicable": true, "source_model": "openai/clip-vit-base-patch32", "note": "No label exceeded the configured confidence threshold."},
             "color_family": {"label": "blue", "confidence": 0.78, "alternatives": [], "applicable": true, "source_model": "rgb_palette_heuristic", "note": "Computed from visible foreground pixels after background removal."},
             "dominant_hex_colors": ["#4060C0", "#6080E0"],
             "viewpoint": {"label": "front", "confidence": 0.83, "alternatives": [], "applicable": true, "source_model": "openai/clip-vit-base-patch32", "note": null},
             "notes": [
               "Attributes are returned as null when the configured confidence threshold is not met.",
               "Single-view images cannot guarantee hidden details such as exact fiber composition or unseen back-side structure.",
               "Fallback CLIP detection was used; localization and category precision can improve with a DeepFashion2-trained TorchScript checkpoint."
             ],
             "source_models": [
               "alpha_mask_clip_fallback",
               "openai/clip-vit-base-patch32",
               "rgb_palette_heuristic"
             ]
           }
         }
       ],
       "warnings": [],
       "error": null,
       "processing_ms": 812
     }
   ]
 }
 ```
 
 ## Extending the system
 
 ### Add a better detector
 
 Replace the primary detector with:
 
 - a DeepFashion2 fine-tuned Mask R-CNN,
 - a Detectron2 model exported to TorchScript,
 - a TorchScript YOLO-style model with an adapter.
 
 Only the detector adapter needs to change.
 
 ### Add more attributes
 
 Update `GarmentMetadataBuilder` and add another prompt map.
 
 Examples:
 
 - collar style,
 - cuff style,
 - pocket type,
 - logo presence,
 - embellishment,
 - dress silhouette.
 
 ### Move storage to object storage
 
 Replace `LocalArtifactStore` with an S3, GCS, or Azure Blob implementation. The pipeline does not need to change.
 
 ## Production notes
 
 - Run model loading once at startup.
 - Keep batch processing sequential unless you have measured memory headroom.
 - Return URLs by default instead of always returning Base64.
 - Use a real detector for multi-garment person photos.
 - Add request tracing, structured logging, and metrics before deploying at scale.
 
 ## Suggested next step
 
 Train or export a detector on DeepFashion2 and set `DEEPFASHION2_TORCHSCRIPT_PATH` so the API gets much better garment localization for images containing multiple clothing items.