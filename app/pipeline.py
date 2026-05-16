 # Enable postponed evaluation of type hints so forward references remain clean.
from __future__ import annotations
 
 # Import `time` so per-image processing duration can be captured for observability.
import time
 # Import `uuid` so batch ids and garment ids stay unique across requests.
import uuid
 # Import `BytesIO` so uploaded bytes can be opened by Pillow without touching disk.
from io import BytesIO
 
 # Import `Image` so uploaded bytes can be decoded into Pillow images.
from PIL import Image
 # Import `UnidentifiedImageError` so invalid image uploads can be reported clearly.
from PIL import UnidentifiedImageError
 
 # Import response models so the application layer can return strongly typed payloads.
from .models import BatchAnalysisResponse
 # Import response models so the application layer can build garment-level responses.
from .models import GarmentResult
 # Import response models so the application layer can build image-level responses.
from .models import ImageAnalysisResult
 # Import the uploaded-image transport model consumed by the analysis service.
from .models import IncomingImage
 # Import the shared settings model so limits and thresholds come from configuration.
from .settings import Settings
 # Import the artifact-store abstraction so the pipeline does not depend on the filesystem directly.
from .services import ArtifactStore
 # Import the background-remover abstraction so the pipeline does not depend on rembg directly.
from .services import BackgroundRemover
 # Import the detector abstraction so the pipeline can swap detector implementations without code changes.
from .services import GarmentDetector
 # Import the metadata builder that enriches each garment crop.
from .services import GarmentMetadataBuilder
 # Import the helper that converts processed images to inline Base64 when requested.
from .services import image_to_base64_png
 # Import the helper that converts internal tuple boxes into the public response model.
from .services import to_bounding_box
 
 
 # Implement the application-layer service that orchestrates validation, background removal, detection, and metadata enrichment.
class FashionImageAnalysisService:
     # Initialize the orchestrator with all dependencies supplied from the composition root.
     def __init__(
         self,
         settings: Settings,
         background_remover: BackgroundRemover,
         detector: GarmentDetector,
         metadata_builder: GarmentMetadataBuilder,
         artifact_store: ArtifactStore,
     ) -> None:
         # Store the configuration object so runtime limits are centralized and testable.
         self._settings = settings
         # Store the background remover behind an abstraction to keep the pipeline decoupled.
         self._background_remover = background_remover
         # Store the garment detector behind an abstraction to support multiple detector strategies.
         self._detector = detector
         # Store the metadata builder that turns crops into rich garment attributes.
         self._metadata_builder = metadata_builder
         # Store the artifact store that persists processed images.
         self._artifact_store = artifact_store
 
     # Analyze a batch of uploaded images and return a batch response in upload order.
     def analyze_batch(self, images: list[IncomingImage], include_base64: bool = False) -> BatchAnalysisResponse:
         # Reject requests that exceed the configured batch size.
         if len(images) > self._settings.max_files_per_request:
             # Raise a clear validation error before any heavy processing begins.
             raise ValueError(
                 f"A maximum of {self._settings.max_files_per_request} files is allowed per request."
             )
         # Generate a stable batch identifier for the whole request.
         batch_id = uuid.uuid4().hex
         # Allocate the ordered list of per-image results.
         results: list[ImageAnalysisResult] = []
         # Process images one by one to keep memory usage predictable.
         for image in images:
             # Analyze the current image and append its result in the original request order.
             results.append(self._analyze_one(image=image, include_base64=include_base64))
         # Count how many images completed successfully.
         succeeded = sum(1 for result in results if result.status == "succeeded")
         # Count how many images failed processing.
         failed = sum(1 for result in results if result.status == "failed")
         # Build and return the final batch response.
         return BatchAnalysisResponse(
             # Return the unique identifier for this analyzed batch.
             batch_id=batch_id,
             # Return the total number of uploaded images.
             total_images=len(images),
             # Return the number of successful image analyses.
             succeeded=succeeded,
             # Return the number of failed image analyses.
             failed=failed,
             # Return the detailed per-image results.
             results=results,
         )
 
     # Analyze a single uploaded image from raw bytes to final garment metadata.
     def _analyze_one(self, image: IncomingImage, include_base64: bool) -> ImageAnalysisResult:
         # Start a high-resolution timer so the final response can include processing time.
         started_at = time.perf_counter()
         # Allocate a warning list that can be returned even when processing succeeds.
         warnings: list[str] = []
         # Run the main analysis flow inside a guarded block so failures can be returned as structured responses.
         try:
             # Validate the file size and MIME type before decoding the image.
             self._validate_image(image)
             # Open the uploaded bytes with Pillow.
             opened_image = Image.open(BytesIO(image.data))
             # Force the image to decode fully while the byte buffer is still alive.
             opened_image.load()
             # Normalize the image to RGBA so transparency can be introduced by the background-removal step.
             normalized_image = opened_image.convert("RGBA")
             # Remove the background using the configured open-source remover.
             processed_image = self._background_remover.remove_background(normalized_image)
             # Persist the background-removed image and receive a fetchable relative URL.
             processed_image_url = self._artifact_store.save_processed_image(processed_image, image.filename)
             # Prepare an inline Base64 payload only when the caller explicitly requested it.
             processed_image_base64 = image_to_base64_png(processed_image) if include_base64 else None
             # Detect garments from the background-removed image.
             detections = self._detector.detect(processed_image)
             # Add a non-fatal warning when nothing was detected.
             if not detections:
                 # Explain the outcome while still returning the processed image.
                 warnings.append("No garments were detected in the processed image.")
             # Allocate the final garment result list.
             garments: list[GarmentResult] = []
             # Enrich every detected garment crop with detailed metadata.
             for detection in detections:
                 # Crop the processed image down to the detector box.
                 garment_crop = processed_image.crop(detection.bbox)
                 # Build rich metadata for the garment crop.
                 metadata = self._metadata_builder.build_metadata(
                     # Pass the garment crop into the metadata builder.
                     garment_image=garment_crop,
                     # Pass the detector category into the metadata builder.
                     detected_category=detection.category,
                     # Pass the detector name into the metadata builder.
                     detector_name=detection.detector_name,
                     # Pass the detector score into the metadata builder.
                     detection_score=detection.score,
                 )
                 # Append the normalized garment result to the response list.
                 garments.append(
                     # Build the public garment result model.
                     GarmentResult(
                         # Generate a unique identifier for the garment detection.
                         detection_id=uuid.uuid4().hex,
                         # Convert the internal tuple box into the public response model.
                         bounding_box=to_bounding_box(detection.bbox),
                         # Return the detector confidence score.
                         detection_confidence=detection.score,
                         # Return the detector implementation name.
                         detector_name=detection.detector_name,
                         # Return the rich garment metadata payload.
                         metadata=metadata,
                     )
                 )
             # Compute the total analysis duration in milliseconds.
             processing_ms = int((time.perf_counter() - started_at) * 1000)
             # Return the successful image analysis result.
             return ImageAnalysisResult(
                 # Return the original uploaded file name.
                 original_filename=image.filename,
                 # Mark the image processing as successful.
                 status="succeeded",
                 # Return the processed image width.
                 image_width=processed_image.width,
                 # Return the processed image height.
                 image_height=processed_image.height,
                 # Return the relative static URL of the processed image.
                 processed_image_url=processed_image_url,
                 # Return the optional inline Base64 PNG when requested.
                 processed_image_base64=processed_image_base64,
                 # Return the garment analysis results.
                 garments=garments,
                 # Return any non-fatal warnings emitted during processing.
                 warnings=warnings,
                 # Return no error because processing succeeded.
                 error=None,
                 # Return the end-to-end processing time.
                 processing_ms=processing_ms,
             )
         # Catch image-decoding failures explicitly so the client receives a clear error message.
         except UnidentifiedImageError:
             # Compute the elapsed time even on failure.
             processing_ms = int((time.perf_counter() - started_at) * 1000)
             # Return a structured failure result for the invalid image.
             return ImageAnalysisResult(
                 # Return the original uploaded file name.
                 original_filename=image.filename,
                 # Mark the image processing as failed.
                 status="failed",
                 # Return no width because the image could not be decoded.
                 image_width=None,
                 # Return no height because the image could not be decoded.
                 image_height=None,
                 # Return no processed image URL because the image could not be decoded.
                 processed_image_url=None,
                 # Return no inline Base64 because the image could not be decoded.
                 processed_image_base64=None,
                 # Return no garment results because the image could not be decoded.
                 garments=[],
                 # Return any warnings collected before the failure occurred.
                 warnings=warnings,
                 # Return a clear image-decoding error message.
                 error="The uploaded file could not be decoded as an image.",
                 # Return the elapsed failure duration.
                 processing_ms=processing_ms,
             )
         # Catch any other processing failure and convert it into a structured response.
         except Exception as exc:
             # Compute the elapsed time even on failure.
             processing_ms = int((time.perf_counter() - started_at) * 1000)
             # Return a structured failure result for the current image.
             return ImageAnalysisResult(
                 # Return the original uploaded file name.
                 original_filename=image.filename,
                 # Mark the image processing as failed.
                 status="failed",
                 # Return no width because processing did not complete.
                 image_width=None,
                 # Return no height because processing did not complete.
                 image_height=None,
                 # Return no processed image URL because processing did not complete.
                 processed_image_url=None,
                 # Return no inline Base64 because processing did not complete.
                 processed_image_base64=None,
                 # Return no garments because processing did not complete.
                 garments=[],
                 # Return any warnings collected before the failure occurred.
                 warnings=warnings,
                 # Return the string form of the exception for easier debugging.
                 error=str(exc),
                 # Return the elapsed failure duration.
                 processing_ms=processing_ms,
             )
 
     # Validate a raw uploaded image before decoding and processing it.
     def _validate_image(self, image: IncomingImage) -> None:
         # Reject empty uploads before any expensive work begins.
         if not image.data:
             # Raise a clear validation error for an empty file.
             raise ValueError("The uploaded file is empty.")
         # Reject uploads that exceed the configured per-file size limit.
         if len(image.data) > self._settings.max_file_size_mb * 1024 * 1024:
             # Raise a clear validation error for an oversized file.
             raise ValueError(
                 f"The file `{image.filename}` exceeds the {self._settings.max_file_size_mb} MB size limit."
             )
         # Reject uploads whose MIME type clearly is not an image when the client provided a MIME type.
         if image.content_type and not image.content_type.startswith("image/"):
             # Raise a clear validation error for a non-image content type.
             raise ValueError(f"The file `{image.filename}` is not an image upload.")