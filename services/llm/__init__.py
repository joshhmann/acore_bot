"""LLM domain - backends, caching, tools, and extended capabilities."""

# Lazy/guarded imports to keep unit tests isolated from optional
# dependencies (e.g., PIL) that are not required for core logic tests.
try:
    from services.llm.image_tools import ImageToolSystem, image_tool_system, ImageResult
except Exception:
    # Fallback stubs for environments without optional dependencies
    class ImageToolSystem:  # type: ignore
        pass

    image_tool_system = None  # type: ignore

    class ImageResult:  # type: ignore
        pass


from services.llm.code_tools import (
    CodeToolSystem,
    code_tool_system,
    CodeResult,
    CommandResult,
)

__all__ = [
    "ImageToolSystem",
    "image_tool_system",
    "ImageResult",
    "CodeToolSystem",
    "code_tool_system",
    "CodeResult",
    "CommandResult",
]
