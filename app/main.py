# Enable postponed evaluation of type hints so forward references remain readable.
from __future__ import annotations
 
 # Import `asynccontextmanager` so the service dependency graph can be created once at startup.
from contextlib import asynccontextmanager
 # Import `Annotated` so FastAPI request parameters can carry validation metadata.
from typing import Annotated
 
 # Import `FastAPI` so the HTTP API can be exposed.
from fastapi import FastAPI
 # Import `File` so FastAPI knows the endpoint consumes uploaded files from multipart form-data.
from fastapi import File
 # Import `HTTPException` so request validation failures can be returned with proper HTTP status codes.
from fastapi import HTTPException
 # Import `Request` so application-level singletons can be accessed from request handlers.
from fastapi import Request
 # Import `UploadFile` so large uploads can be read efficiently from multipart requests.
from fastapi import UploadFile
 # Import `StaticFiles` so processed images can be served back to API clients.
from fastapi.staticfiles import StaticFiles
 # Import `run_in_threadpool` so CPU-bound image processing does not block the event loop.
from starlette.concurrency import run_in_threadpool
 
 # Import the batch response model used by the main analysis endpoint.
from .models import BatchAnalysisResponse
 # Import the internal uploaded-image transport model used by the pipeline.
from .models import IncomingImage
 # Import the application-layer orchestrator used by the API handlers.
from .pipeline import FashionImageAnalysisService
 # Import the settings type used for request-time validation limits.
from .settings import Settings
 # Import the settings factory used by the composition root.
from .settings import get_settings
 # Import the CLIP fallback detector used when no DeepFashion2 model is configured.
from .services import AlphaMaskClipDetector
 # Import the CLIP zero-shot classifier used for categories and garment attributes.
from .services import ClipZeroShotClassifier
 # Import the detector chain that prefers DeepFashion2 but can fall back gracefully.
from .services import CompositeGarmentDetector
 # Import the optional DeepFashion2 TorchScript detector.
from .services import DeepFashion2TorchscriptDetector
 # Import the metadata builder that enriches each garment crop.
from .services import GarmentMetadataBuilder
 # Import the local artifact store that persists processed PNG files.
from .services import LocalArtifactStore
 # Import the rembg-backed background remover.
from .services import RembgBackgroundRemover
 
 # Load the application settings once at import time so the static-files mount can be configured.
settings = get_settings()
 # Ensure the artifact root exists before FastAPI mounts it as a static directory.
settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
 
 
 # Create the application lifespan so expensive models are deferred until first use.
@asynccontextmanager
async def lifespan(app: FastAPI):
     # Attach the settings singleton to application state so request handlers can read it.
     app.state.settings = settings
     # Initialize analysis service as None; it will be lazily created on first request.
     app.state.analysis_service = None
     # Yield control back to FastAPI immediately so the port gets bound quickly.
     yield


async def get_or_create_analysis_service(app: FastAPI) -> FashionImageAnalysisService:
     """Lazily initialize the analysis service on first request."""
     if app.state.analysis_service is None:
         # Create the local artifact store used to persist processed images.
         artifact_store = LocalArtifactStore(settings.artifacts_dir)
         # Create the background remover backed by rembg.
         background_remover = RembgBackgroundRemover(settings.rembg_model_name)
         # Create the shared CLIP zero-shot classifier used by the fallback detector and metadata builder.
         clip_classifier = ClipZeroShotClassifier(settings.clip_model_name)
         # Create the optional DeepFashion2 TorchScript detector when a checkpoint path is configured.
         deepfashion2_detector = DeepFashion2TorchscriptDetector(
             # Pass the configured checkpoint path into the detector.
             checkpoint_path=settings.deepfashion2_torchscript_path,
             # Pass the configured detector threshold into the detector.
             confidence_threshold=settings.detector_confidence_threshold,
         )
         # Create the alpha-mask fallback detector used when the dedicated detector is absent or returns no boxes.
         fallback_detector = AlphaMaskClipDetector(clip_classifier)
         # Create the composite detector that prefers DeepFashion2 but can fall back to CLIP.
         detector = CompositeGarmentDetector(
             # Pass the primary detector into the detector chain.
             primary=deepfashion2_detector,
             # Pass the fallback detector into the detector chain.
             fallback=fallback_detector,
             # Pass the configuration switch that enables or disables fallback logic.
             enable_fallback=settings.enable_clip_fallback_detector,
         )
         # Create the garment metadata builder that enriches each detected crop.
         metadata_builder = GarmentMetadataBuilder(
             # Pass the shared CLIP classifier into the metadata builder.
             classifier=clip_classifier,
             # Pass the configured attribute threshold into the metadata builder.
             attribute_threshold=settings.attribute_confidence_threshold,
         )
         # Create the application-layer analysis service that orchestrates the full workflow.
         app.state.analysis_service = FashionImageAnalysisService(
             # Pass the shared settings object into the analysis service.
             settings=settings,
             # Pass the background remover into the analysis service.
             background_remover=background_remover,
             # Pass the detector chain into the analysis service.
             detector=detector,
             # Pass the metadata builder into the analysis service.
             metadata_builder=metadata_builder,
             # Pass the artifact store into the analysis service.
             artifact_store=artifact_store,
         )
     return app.state.analysis_service
 
 
 # Create the FastAPI application with a descriptive title and the custom lifespan handler.
app = FastAPI(
     # Expose the configured application name in the generated OpenAPI schema.
     title=settings.app_name,
     # Expose the configured application version in the generated OpenAPI schema.
     version=settings.app_version,
     # Expose a concise description of the service purpose in the generated OpenAPI schema.
     description="Batch API for clothing background removal and garment metadata extraction.",
     # Use the custom lifespan function so expensive models are initialized only once.
     lifespan=lifespan,
 )
 # Mount the artifact directory so processed images can be downloaded from the API host.
app.mount("/artifacts", StaticFiles(directory=settings.artifacts_dir), name="artifacts")
 
 
 # Read the settings singleton from the current request context.
def get_request_settings(request: Request) -> Settings:
     # Return the settings object stored during application startup.
     return request.app.state.settings
 
 
 # Read the analysis service singleton from the current request context, creating it on first call.
async def get_analysis_service(request: Request) -> FashionImageAnalysisService:
     # Return the analysis service, creating it on first request if needed.
     return await get_or_create_analysis_service(request.app)
 
 
 # Expose a small root endpoint so operators can discover the main API surface quickly.
@app.get("/")
async def root() -> dict[str, str]:
     # Return a simple discovery payload with the main endpoint locations.
     return {
         # Expose the application name for a quick sanity check.
         "service": settings.app_name,
         # Expose the health endpoint path.
         "health": "/health",
         # Expose the main analysis endpoint path.
         "analyze_endpoint": "/v1/analyze-images",
         # Expose the built-in OpenAPI docs path.
         "docs": "/docs",
     }
 
 
 # Expose a health endpoint so load balancers and operators can verify the service is up.
@app.get("/health")
async def health(request: Request) -> dict[str, str | bool]:
     # Read the settings singleton from application state.
     current_settings = get_request_settings(request)
     # Return a simple health payload that includes basic configuration visibility.
     return {
         # Report the overall service status.
         "status": "ok",
         # Report the service version.
         "version": current_settings.app_version,
         # Report whether CLIP fallback detection is enabled.
         "clip_fallback_enabled": current_settings.enable_clip_fallback_detector,
         # Report whether a DeepFashion2 checkpoint path was configured.
         "deepfashion2_checkpoint_configured": bool(current_settings.deepfashion2_torchscript_path),
     }
 
 
 # Expose the main batch-analysis endpoint that accepts one or more clothing images.
@app.post("/v1/analyze-images", response_model=BatchAnalysisResponse)
async def analyze_images(
     request: Request,
     files: Annotated[list[UploadFile], File(description="One or more clothing images to analyze.")],
     include_base64: bool = False,
 ) -> BatchAnalysisResponse:
     # Read the settings singleton from the current request.
     current_settings = get_request_settings(request)
     # Read the analysis service singleton from the current request (lazily initialized).
     analysis_service = await get_analysis_service(request)
     # Reject empty file lists before any work begins.
     if not files:
         # Raise a client error that explains at least one image is required.
         raise HTTPException(status_code=400, detail="At least one image file must be uploaded.")
     # Reject requests that exceed the configured batch size.
     if len(files) > current_settings.max_files_per_request:
         # Raise a client error that explains the configured maximum file count.
         raise HTTPException(
             status_code=400,
             detail=f"A maximum of {current_settings.max_files_per_request} files is allowed per request.",
         )
     # Allocate the list that will hold fully read upload payloads.
     incoming_images: list[IncomingImage] = []
     # Read each uploaded file into memory before handing the work to the synchronous pipeline.
     for uploaded_file in files:
         # Read the complete file content from the multipart upload.
         file_bytes = await uploaded_file.read()
         # Convert the FastAPI upload into the internal transport model expected by the pipeline.
         incoming_images.append(
             # Build the normalized internal uploaded-image object.
             IncomingImage(
                 # Use the provided file name or a safe fallback name.
                 filename=uploaded_file.filename or "upload",
                 # Preserve the content type for validation.
                 content_type=uploaded_file.content_type,
                 # Preserve the raw uploaded bytes for image decoding.
                 data=file_bytes,
             )
         )
         # Close the underlying multipart file handle as soon as its bytes have been copied.
         await uploaded_file.close()
     # Execute the CPU-heavy analysis work in a threadpool so the async event loop stays responsive.
     try:
         # Run the analysis service on the uploaded batch.
         return await run_in_threadpool(analysis_service.analyze_batch, incoming_images, include_base64)
     # Convert request-level validation errors into HTTP 400 responses.
     except ValueError as exc:
         # Raise a client error that forwards the validation failure message.
         raise HTTPException(status_code=400, detail=str(exc)) from exc 