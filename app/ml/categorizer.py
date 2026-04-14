"""
DEPRECATED: ML categorizer module.
scikit-learn has been removed. Use app.services.category_engine.CategoryEngine instead,
which provides Claude AI + persistent rule memory (no ML dependency required).

This stub is kept to avoid breaking the legacy ml.py router during transition.
"""
from typing import Optional, List, Dict, Tuple


class TransactionCategorizer:
    """Stub — replaced by CategoryEngine."""

    def __init__(self, model_dir: str = "./models"):
        self.pipeline = None
        self.categories = []
        self.stats = {
            "trained_samples": 0,
            "last_trained": None,
            "accuracy_estimate": 0.0,
            "categories_learned": [],
        }

    def train_from_transactions(self, transactions: List[Dict]) -> Dict:
        return {
            "success": False,
            "message": (
                "ML categorization has been replaced by the AI Category Engine. "
                "Use POST /api/categories/predict or PUT /api/categories/transactions/{id} instead."
            ),
            "samples": 0,
        }

    def predict_category(
        self,
        description: str,
        merchant_name: Optional[str] = None,
        min_confidence: float = 0.4,
    ) -> Tuple[Optional[str], float]:
        return None, 0.0

    def predict_batch(self, transactions, min_confidence=0.4):
        return [(None, 0.0)] * len(transactions)

    def get_stats(self) -> Dict:
        return {
            **self.stats,
            "model_loaded": False,
            "can_predict": False,
            "note": "ML removed. Use /api/categories/* endpoints.",
        }


_categorizer: Optional[TransactionCategorizer] = None


def get_categorizer() -> TransactionCategorizer:
    global _categorizer
    if _categorizer is None:
        _categorizer = TransactionCategorizer()
    return _categorizer
