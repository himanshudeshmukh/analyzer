# Enable postponed evaluation of type hints so forward references stay clean and readable.
from __future__ import annotations
 
 # Import `dataclass` so small immutable transport objects can be defined with little boilerplate.
from dataclasses import dataclass
 # Import `Literal` so status fields can be limited to a known and documented set of values.
from typing import Literal
 
 # Import `BaseModel` so API request and response payloads are validated and serialized consistently.
from pydantic import BaseModel
 # Import `Field` so defaults and OpenAPI descriptions can be attached to response fields.
from pydantic import Field
 
 
 # Define a lightweight in-memory representation of an uploaded file after FastAPI reads it.
@dataclass(frozen=True)
class IncomingImage:
     # Store the original file name so the response can reference the exact uploaded asset.
     filename: str
     # Store the MIME type received from the client so basic validation and debugging are easier.
     content_type: str | None
     # Store the raw uploaded bytes so the analysis pipeline can process the image offline.
     data: bytes
 
 
 # Define a generic label-and-score object reused across multiple prediction fields.
class LabelScore(BaseModel):
     # Store the predicted label text such as `short sleeve` or `striped`.
     label: str = Field(description="The predicted label.")
     # Store the confidence score for the label as a normalized probability-like value.
     confidence: float = Field(description="The confidence score for the label.")
 
 
 # Define the shape of a single attribute prediction returned by the service.
class AttributePrediction(BaseModel):
     # Store the winning label when the model is confident enough, or `None` when uncertain.
     label: str | None = Field(default=None, description="The selected label when the score is high enough.")
     # Store the confidence associated with the winning label, or `None` when the label is withheld.
     confidence: float | None = Field(default=None, description="The confidence score for the selected label.")
     # Store the strongest alternatives so downstream systems can reason about ambiguity.
     alternatives: list[LabelScore] = Field(default_factory=list, description="The top alternative labels and scores.")
     # Store whether the attribute makes sense for the garment, such as sleeve length on a skirt.
     applicable: bool = Field(default=True, description="Whether this attribute is applicable for the garment type.")
     # Store the model or heuristic name that produced the prediction for traceability.
     source_model: str = Field(default="", description="The model or heuristic used to produce this attribute.")
     # Store an optional note that explains withheld labels or derivations.
     note: str | None = Field(default=None, description="Extra explanation about the prediction.")
 
 
 # Define a normalized bounding box that is easy to consume from any client.
class BoundingBox(BaseModel):
     # Store the left pixel coordinate of the box.
     left: int = Field(description="Left coordinate in pixels.")
     # Store the top pixel coordinate of the box.
     top: int = Field(description="Top coordinate in pixels.")
     # Store the right pixel coordinate of the box.
     right: int = Field(description="Right coordinate in pixels.")
     # Store the bottom pixel coordinate of the box.
     bottom: int = Field(description="Bottom coordinate in pixels.")
 
 
 # Define the full metadata payload for one detected garment.
class GarmentMetadata(BaseModel):
     # Store a coarse garment group such as `top`, `bottom`, `dress`, or `outerwear`.
     garment_group: str = Field(description="A normalized garment family derived from the category.")
     # Store the garment category, ideally aligned with DeepFashion2 categories when possible.
     category: AttributePrediction = Field(description="The garment category prediction.")
     # Store sleeve-length metadata when relevant for the garment.
     sleeve_length: AttributePrediction = Field(description="The sleeve-length prediction.")
     # Store neckline metadata when relevant for the garment.
     neckline: AttributePrediction = Field(description="The neckline prediction.")
     # Store waist-rise metadata when relevant for bottom garments.
     waist_rise: AttributePrediction = Field(description="The waist-rise prediction.")
     # Store garment-length metadata such as cropped, midi, or maxi.
     length: AttributePrediction = Field(description="The garment-length prediction.")
     # Store fit metadata such as slim, regular, or oversized.
     fit: AttributePrediction = Field(description="The fit prediction.")
     # Store high-level fashion style metadata such as casual or formal.
     fashion_style: AttributePrediction = Field(description="The fashion-style prediction.")
     # Store pattern metadata such as solid, striped, or floral.
     pattern: AttributePrediction = Field(description="The pattern prediction.")
     # Store visual material metadata such as denim, knit, or linen.
     material: AttributePrediction = Field(description="The material prediction inferred from the image.")
     # Store closure metadata such as zipper or buttons when visible.
     closure: AttributePrediction = Field(description="The closure prediction.")
     # Store a normalized color-family prediction such as blue or black.
     color_family: AttributePrediction = Field(description="The dominant color-family prediction.")
     # Store the top dominant colors in hexadecimal format for UI and catalog use cases.
     dominant_hex_colors: list[str] = Field(default_factory=list, description="The dominant hexadecimal colors.")
     # Store the estimated viewpoint such as front, side, or back.
     viewpoint: AttributePrediction = Field(description="The viewpoint prediction.")
     # Store notes that explain uncertainty, fallbacks, and non-visual limitations.
     notes: list[str] = Field(default_factory=list, description="Additional metadata notes and caveats.")
     # Store the set of model names that contributed to this garment result.
     source_models: list[str] = Field(default_factory=list, description="The models or heuristics that contributed to the result.")
 
 
 # Define the response object for one detected garment within an image.
class GarmentResult(BaseModel):
     # Store a stable identifier for the detection so clients can track garments across UI actions.
     detection_id: str = Field(description="The identifier for this detected garment.")
     # Store the bounding box that localizes the garment in the processed image.
     bounding_box: BoundingBox = Field(description="The detected garment bounding box.")
     # Store the detector confidence score for the garment localization step.
     detection_confidence: float = Field(description="The confidence score of the detector.")
     # Store the detector name so operators know whether DeepFashion2 or fallback logic was used.
     detector_name: str = Field(description="The detector implementation used for this garment.")
     # Store the attribute-rich metadata attached to the garment.
     metadata: GarmentMetadata = Field(description="The attribute metadata for this garment.")


# Define the per-image response object returned inside a batch.
class ImageAnalysisResult(BaseModel):
     # Store the original client-supplied file name for traceability.
     original_filename: str = Field(description="The original uploaded file name.")
     # Store whether analysis completed successfully or failed.
     status: Literal["succeeded", "failed"] = Field(description="The processing status for the image.")
     # Store the final processed image width for downstream layout use cases.
     image_width: int | None = Field(default=None, description="The processed image width in pixels.")
     # Store the final processed image height for downstream layout use cases.
     image_height: int | None = Field(default=None, description="The processed image height in pixels.")
     # Store a relative URL that can be fetched from the FastAPI static mount.
     processed_image_url: str | None = Field(default=None, description="The relative URL to the background-removed image.")
     # Store an optional inline Base64 payload when callers prefer a single self-contained JSON response.
     processed_image_base64: str | None = Field(default=None, description="The processed image encoded as Base64 PNG.")
     # Store all garments found in the image after detection and attribute enrichment.
     garments: list[GarmentResult] = Field(default_factory=list, description="The garments found in the image.")
     # Store non-fatal warnings so operators know where the service used fallbacks or skipped fields.
     warnings: list[str] = Field(default_factory=list, description="Warnings emitted while processing the image.")
     # Store the fatal error message when processing fails.
     error: str | None = Field(default=None, description="The failure reason when processing does not succeed.")
     # Store the end-to-end processing duration in milliseconds for observability.
     processing_ms: int | None = Field(default=None, description="The total processing duration in milliseconds.")
 
 
 # Define the batch response object returned by the main API endpoint.
class BatchAnalysisResponse(BaseModel):
     # Store a batch identifier so logs and clients can correlate the whole request.
     batch_id: str = Field(description="The identifier for the analyzed batch.")
     # Store the number of images received in the batch.
     total_images: int = Field(description="The number of uploaded images.")
     # Store the number of images that were processed successfully.
     succeeded: int = Field(description="The number of successfully processed images.")
     # Store the number of images that failed processing.
     failed: int = Field(description="The number of failed images.")
     # Store the detailed per-image results in upload order.
     results: list[ImageAnalysisResult] = Field(default_factory=list, description="The per-image analysis results.")



