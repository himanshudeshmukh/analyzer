# Enable postponed evaluation of type hints so annotations can reference classes defined later in the module.
from __future__ import annotations
 
# Import `base64` so the API can optionally embed processed images directly in JSON responses.
import base64
 # Import `re` so file names can be sanitized before writing to disk.
import re
 # Import `uuid` so generated artifact names and detection identifiers stay unique.
import uuid
 # Import `dataclass` so small immutable helper objects can be declared clearly.
from dataclasses import dataclass
 # Import `BytesIO` so Pillow images can move between bytes and image objects without temporary files.
from io import BytesIO
 # Import `Path` so filesystem paths are handled safely across operating systems.
from pathlib import Path
 # Import `Protocol` so the pipeline can depend on abstractions instead of concrete libraries.
from typing import Protocol
 # Import `Sequence` so classifier and detector methods can accept any ordered collection of candidates.
from typing import Sequence
 
 # Import `numpy` so masks, bounding boxes, and color palettes can be processed efficiently.
import numpy as np
 # Import `torch` so DeepFashion2-style detectors and device management can run on CPU or GPU.
import torch
 # Import `Image` so Pillow images can be manipulated in-memory.
from PIL import Image
 # Import `new_session` so rembg can reuse the same ONNX session for batch performance.
from rembg import new_session
 # Import `remove` so rembg can actually remove the image background.
from rembg import remove
 # Import `pipeline` so CLIP-style zero-shot image classification can be performed with an open model.
from transformers import pipeline
 
 # Import shared response models so infrastructure outputs stay strongly typed.
from .models import AttributePrediction
 # Import shared response models so ranked alternatives can be returned consistently.
from .models import BoundingBox
 # Import shared response models so garment-level metadata uses a stable contract.
from .models import GarmentMetadata
 # Import shared response models so top predictions can be serialized uniformly.
from .models import LabelScore
 
 
 # Map DeepFashion2 numeric category identifiers to normalized human-readable category names.
DEEPFASHION2_CATEGORY_BY_ID: dict[int, str] = {
     # Map class `1` to the DeepFashion2 short-sleeve top category.
     1: "short sleeve top",
     # Map class `2` to the DeepFashion2 long-sleeve top category.
     2: "long sleeve top",
     # Map class `3` to the DeepFashion2 short-sleeve outwear category.
     3: "short sleeve outwear",
     # Map class `4` to the DeepFashion2 long-sleeve outwear category.
     4: "long sleeve outwear",
     # Map class `5` to the DeepFashion2 vest category.
     5: "vest",
     # Map class `6` to the DeepFashion2 sling category.
     6: "sling",
     # Map class `7` to the DeepFashion2 shorts category.
     7: "shorts",
     # Map class `8` to the DeepFashion2 trousers category.
     8: "trousers",
     # Map class `9` to the DeepFashion2 skirt category.
     9: "skirt",
     # Map class `10` to the DeepFashion2 short-sleeve dress category.
     10: "short sleeve dress",
     # Map class `11` to the DeepFashion2 long-sleeve dress category.
     11: "long sleeve dress",
     # Map class `12` to the DeepFashion2 vest dress category.
     12: "vest dress",
     # Map class `13` to the DeepFashion2 sling dress category.
     13: "sling dress",
 }
 # Expose the DeepFashion2 category names in order so classifiers can rank against the full label space.
DEEPFASHION2_CATEGORIES: list[str] = list(DEEPFASHION2_CATEGORY_BY_ID.values())
 # Group all top-like categories so attribute applicability rules stay easy to read.
TOP_CATEGORIES: set[str] = {"short sleeve top", "long sleeve top", "vest", "sling"}
 # Group outerwear categories so the garment-group derivation remains explicit.
OUTERWEAR_CATEGORIES: set[str] = {"short sleeve outwear", "long sleeve outwear"}
 # Group bottom categories so sleeve and neckline rules can mark themselves as not applicable.
BOTTOM_CATEGORIES: set[str] = {"shorts", "trousers", "skirt"}
 # Group dress categories so dress-specific prompts can be handled as a coherent family.
DRESS_CATEGORIES: set[str] = {"short sleeve dress", "long sleeve dress", "vest dress", "sling dress"}
 # Store representative RGB points for broad color families used by the color heuristic.
COLOR_FAMILY_PROTOTYPES: dict[str, tuple[int, int, int]] = {
    # Use a near-black prototype for black garments.
     "black": (20, 20, 20),
     # Use a near-white prototype for white garments.
     "white": (245, 245, 245),
     # Use a neutral middle-gray prototype for gray garments.
     "gray": (128, 128, 128),
     # Use a saturated red prototype for red garments.
     "red": (210, 40, 40),
     # Use a warm orange prototype for orange garments.
     "orange": (230, 140, 40),
     # Use a warm yellow prototype for yellow garments.
     "yellow": (230, 210, 40),
     # Use a green prototype for green garments.
     "green": (60, 150, 70),
     # Use a blue prototype for blue garments.
     "blue": (50, 90, 200),
     # Use a purple prototype for purple garments.
     "purple": (140, 80, 170),
     # Use a pink prototype for pink garments.
     "pink": (230, 140, 190),
     # Use a brown prototype for brown garments.
     "brown": (130, 90, 50),
     # Use a beige prototype for beige garments.
     "beige": (210, 190, 150),
 }
 
 
 # Define a typed prompt object so zero-shot candidate labels and prompts do not get mixed up.
@dataclass(frozen=True)
class CandidatePrompt:
     # Store the normalized label that should appear in the API response.
     label: str
     # Store the descriptive prompt phrase that is actually passed to the zero-shot model.
     prompt: str
 
 
 # Define a typed detection object so detectors can return a stable internal contract.
@dataclass(frozen=True)
class DetectedGarment:
     # Store the bounding box of the detected garment in `(left, top, right, bottom)` format.
     bbox: tuple[int, int, int, int]
     # Store the detector category when available, or `None` when only a box is known.
     category: str | None
     # Store the detector confidence score for ranking and thresholding.
     score: float
     # Store the detector implementation name for traceability and debugging.
     detector_name: str
 
 
 # Define the abstraction for any background-removal implementation used by the pipeline.
class BackgroundRemover(Protocol):
     # Declare the method that converts an input image into a transparent-background image.
     def remove_background(self, image: Image.Image) -> Image.Image: ...
 
 
 # Define the abstraction for any garment detector implementation used by the pipeline.
class GarmentDetector(Protocol):
     # Declare the method that returns detected garments from a processed image.
     def detect(self, image: Image.Image) -> list[DetectedGarment]: ...
 
 
 # Define the abstraction for any artifact store that persists processed images.
class ArtifactStore(Protocol):
     # Declare the method that writes a processed image and returns a fetchable relative URL.
     def save_processed_image(self, image: Image.Image, original_filename: str) -> str: ...
 
 
 # Round raw floating-point scores into a predictable payload format.
def round_score(value: float) -> float:
     # Return the score rounded to four decimal places so responses stay compact and readable.
     return round(float(value), 4)
 
 
 # Convert a Pillow image into PNG bytes without writing an intermediate file.
def pil_to_png_bytes(image: Image.Image) -> bytes:
     # Allocate an in-memory buffer that will hold the PNG-encoded image.
     buffer = BytesIO()
     # Write the image into the buffer using PNG so transparency is preserved.
     image.save(buffer, format="PNG")
     # Return the raw buffer content as bytes for rembg or Base64 serialization.
     return buffer.getvalue()
 
 
 # Convert a Pillow image into a Base64-encoded PNG string for inline JSON responses.
def image_to_base64_png(image: Image.Image) -> str:
     # Encode the PNG bytes into Base64 text so the image can travel inside JSON.
     return base64.b64encode(pil_to_png_bytes(image)).decode("utf-8")
 
 
 # Sanitize a client-supplied file name so it becomes safe to use as part of an artifact path.
def sanitize_file_stem(filename: str) -> str:
     # Remove the extension and keep only the base name that should appear in generated artifacts.
     raw_stem = Path(filename).stem or "image"
     # Replace unsafe characters with dashes so the final file name is filesystem-friendly.
     safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", raw_stem)
     # Collapse repeated dashes so names stay tidy.
     collapsed_stem = re.sub(r"-{2,}", "-", safe_stem)
     # Strip leading and trailing dashes so the file name looks clean.
     normalized_stem = collapsed_stem.strip("-")
     # Return a fallback name when the original stem contained no safe characters.
     return normalized_stem or "image"
 
 
 # Flatten an RGBA image onto a white background so RGB-only models can consume it.
def flatten_to_rgb(image: Image.Image) -> Image.Image:
     # Convert the input image to RGBA so alpha compositing behaves predictably.
     rgba_image = image.convert("RGBA")
     # Create a fully white RGBA canvas with the same size as the input.
     white_canvas = Image.new("RGBA", rgba_image.size, (255, 255, 255, 255))
     # Composite the transparent image over the white canvas.
     composed_image = Image.alpha_composite(white_canvas, rgba_image)
     # Convert the composed image back to plain RGB for CLIP and Torch models.
     return composed_image.convert("RGB")
 
 
 # Compute a tight bounding box around the visible foreground pixels of a transparent image.
def compute_alpha_bbox(image: Image.Image) -> tuple[int, int, int, int]:
     # Convert the image to RGBA so an alpha channel is always available.
     rgba_image = image.convert("RGBA")
     # Turn the image into a NumPy array so foreground pixels can be found quickly.
     pixel_array = np.asarray(rgba_image)
     # Extract the alpha channel where non-zero values indicate visible foreground.
     alpha_channel = pixel_array[:, :, 3]
     # Collect the row and column coordinates of all visible pixels.
     visible_positions = np.argwhere(alpha_channel > 0)
     # Return the whole image when no transparent mask is available.
     if visible_positions.size == 0:
         # Use the full image extents as a safe fallback box.
         return (0, 0, rgba_image.width, rgba_image.height)
     # Find the top-most and left-most visible coordinates.
     top, left = visible_positions.min(axis=0)
     # Find the bottom-most and right-most visible coordinates.
     bottom, right = visible_positions.max(axis=0)
     # Return a box with an exclusive right and bottom edge suitable for Pillow cropping.
     return (int(left), int(top), int(right) + 1, int(bottom) + 1)
 
 
 # Clamp a raw box to valid image boundaries so cropping and serialization never fail.
def clamp_bbox(bbox: tuple[int, int, int, int], width: int, height: int) -> tuple[int, int, int, int]:
     # Clamp the left coordinate to the valid image range.
     left = max(0, min(int(bbox[0]), width))
     # Clamp the top coordinate to the valid image range.
     top = max(0, min(int(bbox[1]), height))
     # Clamp the right coordinate to the valid image range.
     right = max(0, min(int(bbox[2]), width))
     # Clamp the bottom coordinate to the valid image range.
     bottom = max(0, min(int(bbox[3]), height))
     # Return the normalized box after clamping.
     return (left, top, right, bottom)
 
 
 # Convert an internal tuple box into the public response model.
def to_bounding_box(bbox: tuple[int, int, int, int]) -> BoundingBox:
     # Build the response model from the left coordinate.
     return BoundingBox(
         # Store the left coordinate on the response model.
         left=int(bbox[0]),
         # Store the top coordinate on the response model.
         top=int(bbox[1]),
         # Store the right coordinate on the response model.
         right=int(bbox[2]),
         # Store the bottom coordinate on the response model.
         bottom=int(bbox[3]),
     )
 
 
 # Deduplicate strings while preserving their original order.
def dedupe_preserve_order(values: Sequence[str]) -> list[str]:
     # Allocate a set to track which values have already been emitted.
     seen: set[str] = set()
     # Allocate the ordered result list that will keep first-seen values only.
     ordered_values: list[str] = []
     # Walk the incoming values in their original order.
     for value in values:
         # Skip blank strings because they do not add meaningful metadata.
         if not value:
             # Continue to the next value when the current one is empty.
             continue
         # Skip values that have already been recorded.
         if value in seen:
             # Continue to the next value when the current one is duplicated.
             continue
         # Record the value in the `seen` set to block future duplicates.
         seen.add(value)
         # Append the value to the ordered output list.
         ordered_values.append(value)
     # Return the deduplicated ordered list.
     return ordered_values
 
 
 # Derive a coarse garment group from a category so attribute applicability becomes easier to reason about.
def derive_group_from_category(category: str | None) -> str:
     # Return `unknown` when no category is available.
     if not category:
         # Provide a stable fallback group for missing categories.
         return "unknown"
     # Return `top` for top-like categories.
     if category in TOP_CATEGORIES:
         # Label the garment as a top.
         return "top"
     # Return `outerwear` for jacket-like categories.
     if category in OUTERWEAR_CATEGORIES:
         # Label the garment as outerwear.
         return "outerwear"
     # Return `bottom` for shorts, trousers, and skirts.
     if category in BOTTOM_CATEGORIES:
         # Label the garment as a bottom.
         return "bottom"
     # Return `dress` for all dress categories.
     if category in DRESS_CATEGORIES:
         # Label the garment as a dress.
         return "dress"
     # Fall back to `unknown` for any category outside the known mapping.
     return "unknown"
 
 
 # Build a standardized not-applicable prediction object.
def not_applicable_prediction(source_model: str, note: str) -> AttributePrediction:
     # Return an empty prediction that explicitly marks the field as not applicable.
     return AttributePrediction(
         # Return no label because the field does not apply to this garment type.
         label=None,
         # Return no confidence because no prediction should be made.
         confidence=None,
         # Return no alternatives because the field is not applicable.
         alternatives=[],
         # Mark the attribute as not applicable.
         applicable=False,
         # Record which model or rule decided that the field is not applicable.
         source_model=source_model,
         # Explain why the field is not applicable.
         note=note,
     )
 
 
 # Implement a local artifact store that persists processed images under a static FastAPI mount.
class LocalArtifactStore:
     # Initialize the store with the configured base directory.
     def __init__(self, base_dir: Path) -> None:
         # Store the base directory for later writes.
         self._base_dir = base_dir
         # Derive the processed-image directory where PNG outputs will be written.
         self._processed_dir = base_dir / "processed"
         # Create the directory tree if it does not already exist.
         self._processed_dir.mkdir(parents=True, exist_ok=True)
 
     # Save a processed image to disk and return the relative static URL.
     def save_processed_image(self, image: Image.Image, original_filename: str) -> str:
         # Sanitize the original filename stem so it can safely appear in the generated file name.
         safe_stem = sanitize_file_stem(original_filename)
         # Create a unique artifact file name that preserves the original stem.
         output_name = f"{safe_stem}-{uuid.uuid4().hex}.png"
         # Build the absolute path where the processed image will be written.
         output_path = self._processed_dir / output_name
         # Save the image as PNG so transparency from background removal is retained.
         image.save(output_path, format="PNG")
         # Return the relative URL exposed by the FastAPI static-files mount.
         return f"/artifacts/processed/{output_name}"
 
 
 # Implement background removal using the open-source `rembg` library.
class RembgBackgroundRemover:
     # Initialize the remover once so its ONNX session can be reused across requests.
     def __init__(self, model_name: str) -> None:
         # Store the chosen rembg model name for diagnostics and traceability.
         self.model_name = model_name
         # Create and cache the rembg session so repeated image processing is faster.
         self._session = new_session(model_name=model_name)
 
     # Remove the background from an image and return an RGBA image with transparency.
     def remove_background(self, image: Image.Image) -> Image.Image:
         # Normalize the input to RGBA so transparency is preserved through the round trip.
         rgba_input = image.convert("RGBA")
         # Encode the input as PNG bytes because rembg handles bytes reliably.
         input_bytes = pil_to_png_bytes(rgba_input)
         # Ask rembg to remove the background while reusing the same session for performance.
         output_bytes = remove(input_bytes, session=self._session, force_return_bytes=True)
         # Open the returned PNG bytes as a Pillow image.
         output_image = Image.open(BytesIO(output_bytes))
         # Force pixel data to be loaded before the underlying buffer goes out of scope.
         output_image.load()
         # Return the output as RGBA so the transparency mask remains available to later stages.
         return output_image.convert("RGBA")
 
 
 # Implement CLIP-style zero-shot classification using an open-source Hugging Face pipeline.
class ClipZeroShotClassifier:
     # Initialize the classifier once so the model stays warm across API calls.
     def __init__(self, model_name: str) -> None:
         # Store the model name for traceability in API responses.
         self.model_name = model_name
         # Select GPU `0` when CUDA is available and `-1` when the service should run on CPU.
         self._device = 0 if torch.cuda.is_available() else -1
         # Create the zero-shot image-classification pipeline backed by the configured CLIP checkpoint.
         self._classifier = pipeline(task="zero-shot-image-classification", model=model_name, device=self._device)
 
     # Score a set of descriptive prompts against a garment image.
     def score_candidates(self, image: Image.Image, candidates: Sequence[CandidatePrompt]) -> list[LabelScore]:
         # Return an empty result when no candidates were supplied.
         if not candidates:
             # Stop early because no ranking can be produced without candidates.
             return []
         # Build a prompt-to-label lookup because the model sees prompts while the API returns normalized labels.
         prompt_lookup = {candidate.prompt: candidate.label for candidate in candidates}
         # Run the zero-shot classifier on an RGB-safe copy of the image.
         raw_predictions = self._classifier(flatten_to_rgb(image), candidate_labels=list(prompt_lookup.keys()))
         # Allocate the normalized result list that will contain label-and-score pairs.
         ranked_predictions: list[LabelScore] = []
         # Normalize every returned prompt back into the public label shape.
         for raw_prediction in raw_predictions:
             # Read the prompt string emitted by the model.
             prompt = str(raw_prediction["label"])
             # Read and normalize the floating-point score emitted by the model.
             score = round_score(float(raw_prediction["score"]))
             # Convert the prompt back to the canonical response label.
             label = prompt_lookup[prompt]
             # Append the normalized label-and-score object to the ranked list.
             ranked_predictions.append(LabelScore(label=label, confidence=score))
         # Return the model-ranked predictions in descending confidence order.
         return ranked_predictions
 
     # Convert a ranked list of candidate prompts into the standardized attribute payload.
     def predict_attribute(
         self,
         image: Image.Image,
         candidates: Sequence[CandidatePrompt],
         minimum_confidence: float = 0.0,
         note: str | None = None,
     ) -> AttributePrediction:
         # Score all candidate prompts against the image.
         ranked_predictions = self.score_candidates(image, candidates)
         # Return an empty prediction when the candidate list was empty.
         if not ranked_predictions:
             # Build the empty prediction payload for the caller.
             return AttributePrediction(
                 # Return no label because nothing was scored.
                 label=None,
                 # Return no confidence because nothing was scored.
                 confidence=None,
                 # Return no alternatives because nothing was scored.
                 alternatives=[],
                 # Keep the attribute marked as applicable because the absence is due to configuration, not garment type.
                 applicable=True,
                 # Record the CLIP model name that attempted the task.
                 source_model=self.model_name,
                 # Explain why the label is missing.
                 note="No candidates were supplied to the zero-shot classifier.",
             )
         # Read the strongest prediction from the ranked output.
         top_prediction = ranked_predictions[0]
         # Withhold the label when the confidence does not meet the configured threshold.
         if top_prediction.confidence < minimum_confidence:
             # Return the alternatives but omit the final label because confidence is too low.
             return AttributePrediction(
                 # Return no final label due to low confidence.
                 label=None,
                 # Return no final confidence due to low confidence.
                 confidence=None,
                 # Return the top alternatives so clients can inspect the ambiguity.
                 alternatives=ranked_predictions[:3],
                 # Keep the attribute marked as applicable because the field itself still makes sense.
                 applicable=True,
                 # Record the model that produced the ranking.
                 source_model=self.model_name,
                 # Explain why the final label was withheld.
                 note="No label exceeded the configured confidence threshold.",
             )
         # Return the strongest label because it cleared the configured threshold.
         return AttributePrediction(
             # Return the winning label.
             label=top_prediction.label,
             # Return the winning confidence score.
             confidence=top_prediction.confidence,
             # Return the strongest alternatives for transparency.
             alternatives=ranked_predictions[:3],
             # Mark the field as applicable because a prediction was produced.
             applicable=True,
             # Record the CLIP model name that produced the prediction.
             source_model=self.model_name,
             # Forward any caller-supplied note into the response.
             note=note,
         )
 
 
 # Implement a pluggable detector for a user-supplied TorchScript model trained on DeepFashion2.
class DeepFashion2TorchscriptDetector:
     # Initialize the detector and lazily disable it when no checkpoint path is configured.
     def __init__(self, checkpoint_path: str | None, confidence_threshold: float) -> None:
         # Store the detector name for traceability.
         self.detector_name = "deepfashion2_torchscript"
         # Store the minimum score a detection must exceed before it is returned.
         self._confidence_threshold = confidence_threshold
         # Pick the best available device for model inference.
         self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
         # Initialize the model slot to `None` so the detector can gracefully disable itself.
         self._model: torch.jit.ScriptModule | None = None
         # Load the TorchScript checkpoint when a path has been configured.
         if checkpoint_path:
             # Load the serialized model onto the selected device.
             self._model = torch.jit.load(checkpoint_path, map_location=self._device)
             # Switch the model into evaluation mode for deterministic inference.
             self._model.eval()
 
     # Return whether a TorchScript model is currently available.
     @property
     def enabled(self) -> bool:
         # Report whether the detector actually has a loaded model.
         return self._model is not None
 
     # Detect garments in an image using the loaded TorchScript model.
     def detect(self, image: Image.Image) -> list[DetectedGarment]:
         # Return no detections when the checkpoint is not configured.
         if self._model is None:
             # Stop early because there is no model to run.
             return []
         # Convert the image into RGB because most Torch detection models expect three channels.
         rgb_image = flatten_to_rgb(image)
         # Convert the image into a float tensor with shape `[C, H, W]` in the `[0, 1]` range.
         tensor = torch.from_numpy(np.asarray(rgb_image).astype(np.float32).transpose(2, 0, 1)) / 255.0
         # Move the tensor to the detector device.
         tensor = tensor.to(self._device)
         # Run inference without gradient tracking to reduce memory usage.
         with torch.inference_mode():
             # Try the common torchvision-style input contract first.
             try:
                 # Call the model with a single-element list of tensors.
                 raw_output = self._model([tensor])
             # Fall back to a batched tensor contract when the model does not accept lists.
             except Exception:
                 # Call the model with an explicit batch dimension.
                 raw_output = self._model(tensor.unsqueeze(0))
         # Normalize list-like outputs into a single detection dictionary.
         output = raw_output[0] if isinstance(raw_output, (list, tuple)) else raw_output
         # Return no detections when the output is not a dictionary-like structure.
         if not isinstance(output, dict):
             # Stop early because the result shape is not supported by this adapter.
             return []
         # Read the raw bounding boxes from the detector output.
         raw_boxes = output.get("boxes")
         # Read the raw class labels from the detector output.
         raw_labels = output.get("labels")
         # Read the raw confidence scores from the detector output when provided.
         raw_scores = output.get("scores")
         # Return no detections when boxes or labels are missing.
         if raw_boxes is None or raw_labels is None:
             # Stop early because the minimum detector contract was not met.
             return []
         # Convert boxes into a NumPy array regardless of whether the model returned tensors or lists.
         boxes_array = raw_boxes.detach().cpu().numpy() if torch.is_tensor(raw_boxes) else np.asarray(raw_boxes)
         # Convert labels into a flat NumPy array regardless of whether the model returned tensors or lists.
         labels_array = raw_labels.detach().cpu().numpy().reshape(-1) if torch.is_tensor(raw_labels) else np.asarray(raw_labels).reshape(-1)
         # Convert scores into a flat NumPy array or default to `1.0` for every label when scores are absent.
         scores_array = (
             raw_scores.detach().cpu().numpy().reshape(-1)
             if torch.is_tensor(raw_scores)
             else np.asarray(raw_scores).reshape(-1)
             if raw_scores is not None
             else np.ones(labels_array.shape[0], dtype=np.float32)
         )
         # Return no detections when the boxes array is empty.
         if boxes_array.size == 0:
             # Stop early because the model did not produce any boxes.
             return []
         # Normalize the boxes array into a two-dimensional `[N, 4]` shape.
         boxes_array = np.asarray(boxes_array).reshape(-1, 4)
         # Allocate the final normalized detection list.
         detections: list[DetectedGarment] = []
         # Walk boxes, labels, and scores together in detector order.
         for raw_box, raw_label, raw_score in zip(boxes_array, labels_array.tolist(), scores_array.tolist()):
             # Convert the raw confidence score into a Python float.
             score = float(raw_score)
             # Skip detections that do not meet the configured detector threshold.
             if score < self._confidence_threshold:
                 # Continue to the next detection candidate.
                 continue
             # Round and clamp the raw detector box to valid image boundaries.
             bbox = clamp_bbox(
                 (
                     int(round(float(raw_box[0]))),
                     int(round(float(raw_box[1]))),
                     int(round(float(raw_box[2]))),
                     int(round(float(raw_box[3]))),
                 ),
                 rgb_image.width,
                 rgb_image.height,
             )
             # Skip invalid boxes where the right edge is not beyond the left edge.
             if bbox[2] <= bbox[0]:
                 # Continue to the next detection candidate.
                 continue
             # Skip invalid boxes where the bottom edge is not beyond the top edge.
             if bbox[3] <= bbox[1]:
                 # Continue to the next detection candidate.
                 continue
             # Resolve the detector class id into the DeepFashion2 category name when possible.
             category = DEEPFASHION2_CATEGORY_BY_ID.get(int(raw_label))
             # Append the normalized detection to the output list.
             detections.append(
                 # Build the normalized internal detection object.
                 DetectedGarment(
                     # Store the normalized bounding box.
                     bbox=bbox,
                     # Store the resolved category name or `None` when the id is unknown.
                     category=category,
                     # Store the rounded detector confidence.
                     score=round_score(score),
                     # Store the detector implementation name.
                     detector_name=self.detector_name,
                 )
             )
         # Return all normalized detections that survived validation and thresholding.
         return detections
 
 
 # Implement a no-training fallback detector that uses the transparent foreground extent plus CLIP classification.
class AlphaMaskClipDetector:
     # Initialize the fallback detector with a shared CLIP classifier.
     def __init__(self, classifier: ClipZeroShotClassifier) -> None:
         # Store the detector name for traceability.
         self.detector_name = "alpha_mask_clip_fallback"
         # Store the shared zero-shot classifier used for category inference.
         self._classifier = classifier
         # Pre-build the DeepFashion2 category prompts so they do not need to be recreated per request.
         self._category_candidates = [
             # Create one candidate prompt for each DeepFashion2 category.
             CandidatePrompt(label=category, prompt=f"a photo of a {category}") for category in DEEPFASHION2_CATEGORIES
         ]
 
     # Detect a single garment by using the visible alpha mask and classifying the resulting crop.
     def detect(self, image: Image.Image) -> list[DetectedGarment]:
         # Compute a tight box around the visible foreground.
         bbox = compute_alpha_bbox(image)
         # Crop the processed image to the visible foreground region.
         crop = image.crop(bbox)
         # Classify the crop into one of the DeepFashion2 categories.
         category_prediction = self._classifier.predict_attribute(crop, self._category_candidates, minimum_confidence=0.0)
         # Return a single fallback detection that covers the visible foreground extent.
         return [
             # Build the normalized detection object.
             DetectedGarment(
                 # Store the foreground bounding box.
                 bbox=bbox,
                 # Store the classified category label when available.
                 category=category_prediction.label,
                 # Store the CLIP score as a proxy confidence for the fallback detection.
                 score=round_score(category_prediction.confidence or 0.0),
                 # Store the detector implementation name.
                 detector_name=self.detector_name,
             )
         ]
     
     # Implement a composite detector that prefers a DeepFashion2 detector but can fall back gracefully.
class CompositeGarmentDetector:
     # Initialize the detector chain with a primary and fallback implementation.
     def __init__(self, primary: DeepFashion2TorchscriptDetector, fallback: AlphaMaskClipDetector, enable_fallback: bool) -> None:
         # Store the primary detector that should be tried first.
         self._primary = primary
         # Store the fallback detector used when the primary is missing or returns nothing.
         self._fallback = fallback
         # Store whether fallback behavior is enabled in configuration.
         self._enable_fallback = enable_fallback
 
     # Detect garments by trying the primary detector before the fallback detector.
     def detect(self, image: Image.Image) -> list[DetectedGarment]:
         # Run the primary detector first because it can provide better localization and native categories.
         primary_detections = self._primary.detect(image)
         # Return the primary detections when at least one was found.
         if primary_detections:
             # Stop here because the preferred detector succeeded.
             return primary_detections
         # Return an empty list when fallback detection has been disabled.
         if not self._enable_fallback:
             # Stop here because no fallback should be attempted.
             return []
         # Run the fallback detector when the primary detector is unavailable or produced no boxes.
         return self._fallback.detect(image)
 
 
 # Implement a simple foreground-color extractor that works on already background-removed images.
class ColorPaletteExtractor:
     # Extract dominant colors and a normalized color-family prediction from a garment crop.
     def extract(self, image: Image.Image) -> tuple[AttributePrediction, list[str]]:
         # Convert the crop to RGBA so transparent pixels can be ignored.
         rgba_image = image.convert("RGBA")
         # Convert the crop to a NumPy array for fast pixel-level processing.
         pixel_array = np.asarray(rgba_image)
         # Select only pixels whose alpha channel is non-zero.
         visible_pixels = pixel_array[pixel_array[:, :, 3] > 0][:, :3]
         # Fall back to all RGB pixels when no alpha mask is available.
         if visible_pixels.size == 0:
             # Flatten all RGB pixels into a two-dimensional array.
             visible_pixels = pixel_array[:, :, :3].reshape(-1, 3)
         # Reduce the working set when the garment contains many pixels.
         sample_step = max(1, int(len(visible_pixels) / 5000))
         # Subsample the visible pixels to keep color extraction fast and stable.
         sampled_pixels = visible_pixels[::sample_step]
         # Quantize colors into coarse buckets so dominant colors are easier to count.
         quantized_pixels = (sampled_pixels // 32) * 32
         # Find the unique quantized colors and their frequencies.
         unique_colors, counts = np.unique(quantized_pixels, axis=0, return_counts=True)
         # Rank colors from most frequent to least frequent.
         rank_order = np.argsort(counts)[::-1]
         # Reorder colors by descending frequency.
         ranked_colors = unique_colors[rank_order]
         # Reorder counts by descending frequency.
         ranked_counts = counts[rank_order]
         # Return an empty prediction when no colors were extracted.
         if ranked_colors.size == 0:
             # Build the empty color prediction payload.
             return (
                 # Return an unknown color-family prediction.
                 AttributePrediction(
                     # Return no label because the color extraction failed.
                     label=None,
                     # Return no confidence because the color extraction failed.
                     confidence=None,
                     # Return no alternatives because the color extraction failed.
                     alternatives=[],
                     # Keep the field applicable because color would normally apply.
                     applicable=True,
                     # Record the heuristic name used for this field.
                     source_model="rgb_palette_heuristic",
                     # Explain why the field is missing.
                     note="No visible pixels were available for color extraction.",
                 ),
                 # Return no hexadecimal colors because the extraction failed.
                 [],
             )
         # Compute the total sampled pixel count for confidence normalization.
         total_count = int(ranked_counts.sum()) or 1
         # Allocate the list of top hexadecimal colors.
         dominant_hex_colors: list[str] = []
         # Allocate the ranked color-family alternatives.
         family_alternatives: list[LabelScore] = []
         # Track color families already emitted so alternatives stay unique and useful.
         seen_families: set[str] = set()
         # Walk the top quantized colors in descending frequency order.
         for color, count in zip(ranked_colors[:5], ranked_counts[:5]):
             # Convert the NumPy color triplet into plain Python integers.
             rgb = (int(color[0]), int(color[1]), int(color[2]))
             # Convert the RGB color to a hexadecimal string.
             hex_color = self._rgb_to_hex(rgb)
             # Append the hexadecimal color to the output list when it is new.
             if hex_color not in dominant_hex_colors:
                 # Record the unique hexadecimal color.
                 dominant_hex_colors.append(hex_color)
             # Resolve the RGB value into the nearest broad color family.
             family = self._nearest_color_family(rgb)
             # Skip duplicate family names because alternatives should stay compact.
             if family in seen_families:
                 # Continue to the next ranked color.
                 continue
             # Mark the family as already emitted.
             seen_families.add(family)
             # Convert the color frequency into a normalized confidence score.
             confidence = round_score(int(count) / total_count)
             # Append the family alternative to the ranked list.
             family_alternatives.append(LabelScore(label=family, confidence=confidence))
         # Read the strongest family prediction when alternatives are available.
         top_family = family_alternatives[0] if family_alternatives else None
         # Build the final normalized color-family prediction payload.
         color_prediction = AttributePrediction(
             # Return the strongest family label when one exists.
             label=top_family.label if top_family else None,
             # Return the strongest family confidence when one exists.
             confidence=top_family.confidence if top_family else None,
             # Return up to three family alternatives for transparency.
             alternatives=family_alternatives[:3],
             # Mark the field as applicable because garments always have visible color information.
             applicable=True,
             # Record the heuristic name used for this field.
             source_model="rgb_palette_heuristic",
             # Explain how the color result was produced.
             note="Computed from visible foreground pixels after background removal.",
         )
         # Return both the normalized family prediction and the top hexadecimal colors.
         return color_prediction, dominant_hex_colors[:3]
 
     # Convert an RGB tuple into a `#RRGGBB` string.
     def _rgb_to_hex(self, rgb: tuple[int, int, int]) -> str:
         # Format the RGB tuple using uppercase hexadecimal digits.
         return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
 
     # Resolve an RGB tuple into the nearest broad color family.
     def _nearest_color_family(self, rgb: tuple[int, int, int]) -> str:
         # Initialize the current best family to a safe default.
         best_family = "unknown"
         # Initialize the current best squared distance to positive infinity.
         best_distance = float("inf")
         # Compare the input color with every family prototype.
         for family, prototype in COLOR_FAMILY_PROTOTYPES.items():
             # Compute the squared Euclidean distance to the prototype.
             distance = float(
                 (rgb[0] - prototype[0]) ** 2 + (rgb[1] - prototype[1]) ** 2 + (rgb[2] - prototype[2]) ** 2
             )
             # Update the best family when a smaller distance is found.
             if distance < best_distance:
                 # Record the smaller distance.
                 best_distance = distance
                 # Record the better matching family name.
                 best_family = family
         # Return the nearest broad color family.
         return best_family
 
 
 # Implement the garment-metadata builder that combines detector output, CLIP attributes, and color heuristics.
class GarmentMetadataBuilder:
     # Initialize the metadata builder with its shared model dependencies.
     def __init__(self, classifier: ClipZeroShotClassifier, attribute_threshold: float) -> None:
         # Store the shared CLIP classifier for attribute inference.
         self._classifier = classifier
         # Store the score threshold used to accept or withhold attribute labels.
         self._attribute_threshold = attribute_threshold
         # Create the color extractor used for deterministic color metadata.
         self._color_extractor = ColorPaletteExtractor()
 
     # Build the full metadata payload for a single detected garment crop.
     def build_metadata(
         self,
         garment_image: Image.Image,
         detected_category: str | None,
         detector_name: str,
         detection_score: float,
     ) -> GarmentMetadata:
         # Resolve the garment category from detector output or CLIP classification.
         category_prediction = self._resolve_category(garment_image, detected_category, detector_name, detection_score)
         # Derive the coarse garment family from the resolved category.
         garment_group = derive_group_from_category(category_prediction.label)
         # Resolve the sleeve-length prediction with category-aware applicability rules.
         sleeve_length = self._predict_sleeve_length(garment_image, category_prediction)
         # Resolve the neckline prediction with category-aware applicability rules.
         neckline = self._predict_neckline(garment_image, category_prediction.label)
         # Resolve the waist-rise prediction with category-aware applicability rules.
         waist_rise = self._predict_waist_rise(garment_image, category_prediction.label)
         # Resolve the garment-length prediction from a generic style prompt set.
         length = self._predict_length(garment_image)
         # Resolve the fit prediction from a generic fit prompt set.
         fit = self._predict_fit(garment_image)
         # Resolve the fashion-style prediction from a generic style prompt set.
         fashion_style = self._predict_fashion_style(garment_image)
         # Resolve the pattern prediction from a generic pattern prompt set.
         pattern = self._predict_pattern(garment_image)
         # Resolve the material prediction from a generic material prompt set.
         material = self._predict_material(garment_image)
         # Resolve the closure prediction from a generic closure prompt set.
         closure = self._predict_closure(garment_image)
         # Resolve the color-family prediction and dominant hexadecimal palette.
         color_family, dominant_hex_colors = self._color_extractor.extract(garment_image)
         # Resolve the viewpoint prediction from a generic viewpoint prompt set.
         viewpoint = self._predict_viewpoint(garment_image)
         # Start collecting explanatory notes for the final payload.
         notes = [
             # Explain why some fields may be null even though the service returned successfully.
             "Attributes are returned as null when the configured confidence threshold is not met.",
             # Explain the inherent limit of single-view visual inference.
             "Single-view images cannot guarantee hidden details such as exact fiber composition or unseen back-side structure.",
         ]
         # Record when the fallback detector was used instead of a dedicated DeepFashion2 detector.
         if detector_name != "deepfashion2_torchscript":
             # Add a note that clarifies the precision tradeoff of fallback detection.
             notes.append("Fallback CLIP detection was used; localization and category precision can improve with a DeepFashion2-trained TorchScript checkpoint.")
         # Build the final metadata payload.
         return GarmentMetadata(
             # Store the coarse garment group.
             garment_group=garment_group,
             # Store the resolved category prediction.
             category=category_prediction,
             # Store the resolved sleeve-length prediction.
             sleeve_length=sleeve_length,
             # Store the resolved neckline prediction.
             neckline=neckline,
             # Store the resolved waist-rise prediction.
             waist_rise=waist_rise,
             # Store the resolved garment-length prediction.
             length=length,
             # Store the resolved fit prediction.
             fit=fit,
             # Store the resolved high-level fashion-style prediction.
             fashion_style=fashion_style,
             # Store the resolved pattern prediction.
             pattern=pattern,
             # Store the resolved material prediction.
             material=material,
             # Store the resolved closure prediction.
             closure=closure,
             # Store the resolved color-family prediction.
             color_family=color_family,
             # Store the top dominant hexadecimal colors.
             dominant_hex_colors=dominant_hex_colors,
             # Store the resolved viewpoint prediction.
             viewpoint=viewpoint,
             # Store the explanatory notes.
             notes=notes,
             # Store the distinct contributing model names.
             source_models=dedupe_preserve_order(
                 [
                     # Record the detector name that contributed category or boxes.
                     detector_name,
                     # Record the CLIP model used for zero-shot attributes.
                     self._classifier.model_name,
                     # Record the color heuristic used for color extraction.
                     "rgb_palette_heuristic",
                 ]
             ),
         )
     
     # Resolve the category using the detector category when available, otherwise use CLIP on the crop.
def _resolve_category(
     self,
     garment_image: Image.Image,
     detected_category: str | None,
     detector_name: str,
     detection_score: float,
 ) -> AttributePrediction:
     # Return a detector-backed category when one is already available.
     if detected_category:
         # Build the detector-backed category payload.
         return AttributePrediction(
             # Return the detector category label.
             label=detected_category,
             # Return the detector confidence score.
             confidence=round_score(detection_score),
             # Return the detector category as the only known alternative.
             alternatives=[LabelScore(label=detected_category, confidence=round_score(detection_score))],
             # Mark the field as applicable.
             applicable=True,
             # Record the detector implementation that produced the label.
             source_model=detector_name,
             # Explain that the category came directly from the detector.
             note="Category provided by the detector.",
         )
     # Build the category prompt set for CLIP-based fallback classification.
     candidates = [CandidatePrompt(label=category, prompt=f"a photo of a {category}") for category in DEEPFASHION2_CATEGORIES]
     # Ask CLIP to infer the category from the garment crop.
     return self._classifier.predict_attribute(
         # Pass the garment crop to CLIP.
         garment_image,
         # Pass the DeepFashion2 category prompt set to CLIP.
         candidates,
         # Always return the strongest category when CLIP is used for fallback classification.
         minimum_confidence=0.0,
         # Explain why CLIP was used for category prediction.
         note="Category inferred from the garment crop because the detector did not supply a category.",
     )
 
 # Predict sleeve length or derive it directly from the category when the category already encodes it.
def _predict_sleeve_length(self, garment_image: Image.Image, category_prediction: AttributePrediction) -> AttributePrediction:
     # Read the resolved category label once so the logic stays concise.
     category = category_prediction.label
     # Return `not applicable` for bottom garments.
     if category in BOTTOM_CATEGORIES:
         # Explain that bottom garments do not have sleeves.
         return not_applicable_prediction(self._classifier.model_name, "Sleeve length does not apply to bottoms.")
     # Derive `short sleeve` directly from categories that explicitly encode short sleeves.
     if category and "short sleeve" in category:
         # Return the derived sleeve-length prediction.
         return AttributePrediction(
             # Return the derived sleeve label.
             label="short sleeve",
             # Reuse the category confidence as the derived confidence.
             confidence=category_prediction.confidence,
             # Return the derived label as the only alternative.
             alternatives=[LabelScore(label="short sleeve", confidence=round_score(category_prediction.confidence or 0.0))],
             # Mark the field as applicable.
             applicable=True,
             # Record that the value was derived from the category.
             source_model=f"{category_prediction.source_model}_derived",
             # Explain the derivation logic.
             note="Derived directly from the garment category.",
         )
     # Derive `long sleeve` directly from categories that explicitly encode long sleeves.
     if category and "long sleeve" in category:
         # Return the derived sleeve-length prediction.
         return AttributePrediction(
             # Return the derived sleeve label.
             label="long sleeve",
             # Reuse the category confidence as the derived confidence.
             confidence=category_prediction.confidence,
             # Return the derived label as the only alternative.
             alternatives=[LabelScore(label="long sleeve", confidence=round_score(category_prediction.confidence or 0.0))],
             # Mark the field as applicable.
             applicable=True,
             # Record that the value was derived from the category.
             source_model=f"{category_prediction.source_model}_derived",
             # Explain the derivation logic.
             note="Derived directly from the garment category.",
         )
     # Derive `sleeveless` directly from vest and sling categories.
     if category in {"vest", "sling", "vest dress", "sling dress"}:
         # Return the derived sleeve-length prediction.
         return AttributePrediction(
             # Return the derived sleeve label.
             label="sleeveless",
             # Reuse the category confidence as the derived confidence.
             confidence=category_prediction.confidence,
             # Return the derived label as the only alternative.
             alternatives=[LabelScore(label="sleeveless", confidence=round_score(category_prediction.confidence or 0.0))],
             # Mark the field as applicable.
             applicable=True,
             # Record that the value was derived from the category.
             source_model=f"{category_prediction.source_model}_derived",
             # Explain the derivation logic.
             note="Derived directly from the garment category.",
         )
     # Ask CLIP to infer sleeve length when the category did not already encode it.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass sleeve prompts to CLIP.
         {
             # Describe the short-sleeve option.
             "short sleeve": "a garment with short sleeves",
             # Describe the long-sleeve option.
             "long sleeve": "a garment with long sleeves",
             # Describe the three-quarter-sleeve option.
             "three-quarter sleeve": "a garment with three-quarter sleeves",
             # Describe the cap-sleeve option.
             "cap sleeve": "a garment with cap sleeves",
             # Describe the sleeveless option.
             "sleeveless": "a sleeveless garment",
         },
     )
 
 # Predict neckline only for garment families where neckline is visually meaningful.
def _predict_neckline(self, garment_image: Image.Image, category: str | None) -> AttributePrediction:
     # Return `not applicable` for bottom garments.
     if category in BOTTOM_CATEGORIES:
         # Explain that neckline does not apply to bottoms.
         return not_applicable_prediction(self._classifier.model_name, "Neckline does not apply to bottoms.")
     # Ask CLIP to infer neckline from a garment crop.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass neckline prompts to CLIP.
         {
             # Describe the crew-neck option.
             "crew neck": "a garment with a crew neck",
             # Describe the v-neck option.
             "v-neck": "a garment with a v-neck",
             # Describe the collared option.
             "collared": "a garment with a visible collar",
             # Describe the turtleneck option.
             "turtleneck": "a garment with a turtleneck",
             # Describe the square-neck option.
             "square neck": "a garment with a square neckline",
             # Describe the off-shoulder option.
             "off-shoulder": "an off-shoulder garment",
             # Describe the halter-neck option.
             "halter neck": "a garment with a halter neckline",
         },
     )
 
 # Predict waist rise only for bottom garments where the field is semantically meaningful.
def _predict_waist_rise(self, garment_image: Image.Image, category: str | None) -> AttributePrediction:
     # Return `not applicable` for anything that is not a bottom garment.
     if category not in BOTTOM_CATEGORIES:
         # Explain that waist rise is only exposed for bottoms in this service design.
         return not_applicable_prediction(self._classifier.model_name, "Waist rise is predicted only for bottom garments.")
     # Ask CLIP to infer waist rise from the bottom-garment crop.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass waist-rise prompts to CLIP.
         {
             # Describe the high-waist option.
             "high waist": "a bottom garment with a high waist",
             # Describe the mid-waist option.
             "mid waist": "a bottom garment with a mid waist",
             # Describe the low-waist option.
             "low waist": "a bottom garment with a low waist",
         },
     )
 
 # Predict overall garment length from a generic length prompt set.
def _predict_length(self, garment_image: Image.Image) -> AttributePrediction:
     # Ask CLIP to infer length from the garment crop.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass length prompts to CLIP.
         {
             # Describe the cropped option.
             "cropped": "a cropped garment",
             # Describe the regular-length option.
             "regular length": "a regular length garment",
             # Describe the long option.
             "long": "a long garment",
             # Describe the mini option.
             "mini": "a mini dress or skirt",
             # Describe the midi option.
             "midi": "a midi dress or skirt",
             # Describe the maxi option.
             "maxi": "a maxi dress or skirt",
         },
     )
 
 # Predict fit using a generic set of fashion-fit prompts.
def _predict_fit(self, garment_image: Image.Image) -> AttributePrediction:
     # Ask CLIP to infer garment fit.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass fit prompts to CLIP.
         {
             # Describe the slim-fit option.
             "slim": "a slim fit garment",
             # Describe the regular-fit option.
             "regular": "a regular fit garment",
             # Describe the relaxed-fit option.
             "relaxed": "a relaxed fit garment",
             # Describe the oversized-fit option.
             "oversized": "an oversized garment",
             # Describe the bodycon-fit option.
             "bodycon": "a bodycon garment",
         },
     )
 
 # Predict high-level fashion style from a generic style prompt set.
def _predict_fashion_style(self, garment_image: Image.Image) -> AttributePrediction:
     # Ask CLIP to infer fashion style.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass fashion-style prompts to CLIP.
         {
             # Describe the casual option.
             "casual": "a casual fashion garment",
             # Describe the formal option.
             "formal": "a formal fashion garment",
             # Describe the sporty option.
             "sporty": "a sporty garment",
             # Describe the streetwear option.
             "streetwear": "a streetwear garment",
             # Describe the party option.
             "party": "a partywear garment",
             # Describe the minimalist option.
             "minimalist": "a minimalist fashion garment",
             # Describe the bohemian option.
             "bohemian": "a bohemian style garment",
             # Describe the ethnic option.
             "ethnic": "an ethnic style garment",
         },
     )
 
 # Predict visual pattern from a generic pattern prompt set.
def _predict_pattern(self, garment_image: Image.Image) -> AttributePrediction:
     # Ask CLIP to infer pattern.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass pattern prompts to CLIP.
         {
             # Describe the solid option.
             "solid": "a solid colored garment",
             # Describe the striped option.
             "striped": "a striped garment",
             # Describe the checked option.
             "checked": "a checked garment",
             # Describe the floral option.
             "floral": "a floral garment",
             # Describe the graphic option.
             "graphic": "a graphic print garment",
             # Describe the logo option.
             "logo": "a garment with a visible logo",
             # Describe the polka-dot option.
             "polka dot": "a polka dot garment",
             # Describe the abstract option.
             "abstract": "an abstract print garment",
         },
     )
 
 # Predict visual material from a generic material prompt set.
def _predict_material(self, garment_image: Image.Image) -> AttributePrediction:
     # Ask CLIP to infer material.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass material prompts to CLIP.
         {
             # Describe the denim option.
             "denim": "a denim garment",
             # Describe the cotton option.
             "cotton": "a cotton garment",
             # Describe the knit option.
             "knit": "a knit garment",
             # Describe the leather option.
             "leather": "a leather garment",
             # Describe the linen option.
             "linen": "a linen garment",
             # Describe the satin option.
             "satin": "a satin garment",
             # Describe the chiffon option.
             "chiffon": "a chiffon garment",
             # Describe the wool option.
             "wool": "a wool garment",
         },
     )
 
 # Predict visible closure details from a generic closure prompt set.
def _predict_closure(self, garment_image: Image.Image) -> AttributePrediction:
     # Ask CLIP to infer closure type.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass closure prompts to CLIP.
         {
             # Describe the buttons option.
             "buttons": "a garment with visible buttons",
             # Describe the zipper option.
             "zipper": "a garment with a visible zipper",
             # Describe the pullover option.
             "pullover": "a pullover garment with no visible front closure",
             # Describe the drawstring option.
             "drawstring": "a garment with a drawstring",
             # Describe the belted option.
             "belted": "a belted garment",
             # Describe the hook closure option.
             "hook closure": "a garment with a hook closure",
         },
     )
 
 # Predict the visible camera viewpoint from a generic viewpoint prompt set.
def _predict_viewpoint(self, garment_image: Image.Image) -> AttributePrediction:
     # Ask CLIP to infer viewpoint.
     return self._predict_from_prompt_map(
         # Pass the garment image to CLIP.
         garment_image,
         # Pass viewpoint prompts to CLIP.
         {
             # Describe the front-view option.
             "front": "a front view of a garment",
             # Describe the side-view option.
             "side": "a side view of a garment",
             # Describe the back-view option.
             "back": "a back view of a garment",
         },
     )
 
 # Convert a dictionary of labels and prompts into a standardized CLIP attribute prediction.
def _predict_from_prompt_map(self, garment_image: Image.Image, prompt_map: dict[str, str]) -> AttributePrediction:
     # Convert the prompt map into the typed candidate objects expected by the classifier.
     candidates = [CandidatePrompt(label=label, prompt=prompt) for label, prompt in prompt_map.items()]
     # Ask CLIP to rank the candidates using the configured confidence threshold.
     return self._classifier.predict_attribute(
         # Pass the garment crop to CLIP.
         garment_image,
         # Pass the prompt candidates to CLIP.
         candidates,
         # Use the configured attribute threshold so low-confidence labels are withheld.
         minimum_confidence=self._attribute_threshold,
     )