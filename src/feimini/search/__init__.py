"""搜索求解器模块。"""

from .common import BaseSolver, CandidateRecord, SearchBudget, SearchResult
from .exhaustive import ExhaustiveSearchSolver
from .heuristic import DeterministicHeuristicScorer, HeuristicSearchSolver
from .guided import LearnedSearchSolver
from .random_search import RandomSearchSolver

__all__ = [
    "BaseSolver",
    "CandidateRecord",
    "SearchBudget",
    "SearchResult",
    "ExhaustiveSearchSolver",
    "DeterministicHeuristicScorer",
    "HeuristicSearchSolver",
    "LearnedSearchSolver",
    "RandomSearchSolver",
]
