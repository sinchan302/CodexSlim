"""Transformation filters applied after parsing."""

from .skeletonizer import Skeletonizer
from .comment_pruner import prune

__all__ = ["Skeletonizer", "prune"]
