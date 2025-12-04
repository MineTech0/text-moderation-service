from typing import Protocol, Tuple
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class BaseModelAdapter(Protocol):
    def score(self, text: str) -> Tuple[float, str]:
        """Returns (score, label). Score 0-1."""
        ...

class HuggingFacePipelineAdapter:
    def __init__(self, model_name: str, device: int = -1):
        from transformers import pipeline
        logger.info(f"Loading Hugging Face model: {model_name} on device {device}")
        # top_k=None returns all scores. function_to_apply="sigmoid" is crucial for multi-label models 
        # like TurkuNLP/bert-large-finnish-cased-toxicity to get independent probabilities.
        self._pipe = pipeline(
            "text-classification", 
            model=model_name, 
            device=device, 
            top_k=None,
            function_to_apply="sigmoid" 
        )
        logger.info("Model loaded successfully.")

    def score(self, text: str) -> Tuple[float, str]:
        # Handle empty text to avoid pipeline errors
        if not text or not text.strip():
            return 0.0, "neutral"
            
        # Truncate text to max length (512 is typical for BERT)
        text = text[:512]
        
        # Pipeline with top_k=None returns a list of dicts:
        # [{'label': 'toxic', 'score': 0.9}, {'label': 'obscene', 'score': 0.1}, ...]
        try:
            results = self._pipe(text)
        except Exception as e:
            logger.error(f"Model inference failed: {e}")
            return 0.0, "error"
        
        # Handle potential batch output format (list of lists)
        if isinstance(results, list) and len(results) > 0 and isinstance(results[0], list):
            results = results[0]
            
        toxic_score = 0.0
        max_score = 0.0
        max_label = "neutral"
        found_toxic = False
        
        # Iterate through all labels to find 'toxic' or the highest scoring label
        for res in results:
            label = res.get("label", "")
            score = float(res.get("score", 0.0))
            
            # Track max score generic fallback
            if score > max_score:
                max_score = score
                max_label = label
            
            # Specific check for toxicity
            # TurkuNLP model uses 'toxic' as one of the labels
            if label.lower() == "toxic":
                toxic_score = score
                found_toxic = True

        if found_toxic:
            return toxic_score, "toxic"
            
        # Fallback: if we didn't find "toxic" explicitly, return the highest scoring label
        return max_score, max_label

class DummyAdapter:
    """For testing without heavy models"""
    def score(self, text: str) -> Tuple[float, str]:
        return 0.0, "dummy"

def get_model_adapter() -> BaseModelAdapter:
    if settings.MODEL_BACKEND == "huggingface_pipeline":
        return HuggingFacePipelineAdapter(
            model_name=settings.MODEL_NAME,
            device=settings.MODEL_DEVICE
        )
    return DummyAdapter()
