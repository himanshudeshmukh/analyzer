# Import `lru_cache` so the settings object is created only once and reused safely.
from functools import lru_cache
 # Import `Path` so filesystem paths are handled in a platform-independent way.
from pathlib import Path
 
 # Import `BaseSettings` so configuration can come from environment variables and `.env` files.
from pydantic_settings import BaseSettings
 # Import `SettingsConfigDict` so we can configure how environment settings are loaded.
from pydantic_settings import SettingsConfigDict
 
 
 # Define the configuration model that drives the whole service.
class Settings(BaseSettings):
     # Configure Pydantic Settings to read a local `.env` file and ignore unknown keys.
     model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
 
     # Store the human-readable application name used in OpenAPI docs and health responses.
     app_name: str = "fashion-image-analyzer"
     # Store the service version so clients can identify which build they are calling.
     app_version: str = "1.0.0"
     # Store the maximum number of images allowed in a single batch request.
     max_files_per_request: int = 20
     # Store the maximum size allowed for each uploaded image in megabytes.
     max_file_size_mb: int = 10
     # Store the root folder where generated files are written for later download.
     artifacts_dir: Path = Path("artifacts")
     # Store the rembg model name so background-removal behavior can be swapped without code changes.
     rembg_model_name: str = "u2net_cloth_seg"
     # Store the CLIP checkpoint name used by the zero-shot attribute classifier.
     clip_model_name: str = "openai/clip-vit-base-patch32"
     # Store an optional TorchScript checkpoint path for a detector trained on DeepFashion2.
     deepfashion2_torchscript_path: str | None = None
     # Store the minimum detector score that a garment detection must exceed to be returned.
     detector_confidence_threshold: float = 0.35
     # Store the minimum attribute score that a zero-shot attribute must exceed to be accepted.
     attribute_confidence_threshold: float = 0.25
     # Store whether the API should automatically fall back to CLIP-only detection when the detector is absent.
     enable_clip_fallback_detector: bool = True
 
     # Expose the processed-image folder as a derived property to avoid repeating path logic elsewhere.
     @property
     def processed_dir(self) -> Path:
         # Return the directory used for background-removed outputs and make the path easy to reuse.
         return self.artifacts_dir / "processed"
 
 
 # Cache the settings instance so imports across modules all receive the same configuration object.
@lru_cache(maxsize=1)
def get_settings() -> Settings:
     # Return the singleton settings object for the running process.
     return Settings()