import logging
from app.config import settings
from app.models import ModerationRequest, CallbackPayload, ModerationReason
from app.wordlist import wordlist_loader
from app.adapters import get_model_adapter, BaseModelAdapter

logger = logging.getLogger(__name__)

class ModerationEngine:
    def __init__(self):
        self.adapter: BaseModelAdapter = None
        
    def initialize(self):
        """Loads resources. This can be slow."""
        logger.info("Initializing ModerationEngine...")
        wordlist_loader.load_wordlists()
        self.adapter = get_model_adapter()
        logger.info("ModerationEngine initialized.")

    def is_trivial(self, text: str) -> bool:
        stripped = text.strip()
        return len(stripped) < settings.TRIVIAL_LENGTH_THRESHOLD

    def moderate(self, request: ModerationRequest) -> CallbackPayload:
        text = request.text
        
        # 1. Trivial check
        if self.is_trivial(text):
            return CallbackPayload(
                id=request.id,
                text=text, # or None based on privacy config
                decision="allow",
                reason=ModerationReason(
                    badword=False,
                    toxicity_score=0.0,
                    model_label="trivial"
                )
            )

        # 2. Wordlist check
        is_badword = wordlist_loader.contains_badword(text)
        
        # 3. Model score
        score, label = self.adapter.score(text)
        
        # 4. Decision logic
        decision = "allow"
        
        if is_badword:
            decision = "block"
        elif score > settings.BLOCK_THRESHOLD:
            decision = "block"
        elif score > settings.FLAG_THRESHOLD:
            decision = "flag"
            
        return CallbackPayload(
            id=request.id,
            text=text,
            decision=decision,
            reason=ModerationReason(
                badword=is_badword,
                toxicity_score=score,
                model_label=label
            )
        )

# Global instance
engine = ModerationEngine()

