"""
Language handlers package.

This package provides language-specific handlers for the code commenting system.
Each handler encapsulates all language-specific logic including chunking,
prompts, models, and validation.

Supported languages:
- VFP (Visual FoxPro) - .prg, .spr files
- C# - .cs files

Usage:
    from language_handlers import get_handler

    # Get VFP handler
    vfp_handler = get_handler('vfp', config)

    # Get C# handler
    csharp_handler = get_handler('csharp', config)
"""

from typing import Optional
from .base_handler import LanguageHandler


# Registry of available handlers
# Will be populated as handlers are imported
_HANDLER_REGISTRY = {}


def register_handler(language: str, handler_class):
    """
    Register a language handler.

    Args:
        language: Language identifier (e.g., 'vfp', 'csharp')
        handler_class: Handler class (subclass of LanguageHandler)
    """
    _HANDLER_REGISTRY[language.lower()] = handler_class


def get_handler(language: str, config: Optional[dict] = None) -> LanguageHandler:
    """
    Factory function to get a language handler instance.

    This is the primary entry point for obtaining language handlers.
    It returns a configured handler instance for the specified language.

    Args:
        language: Language identifier ('vfp', 'csharp', 'java', etc.)
        config: Optional configuration dictionary

    Returns:
        LanguageHandler: Configured handler instance

    Raises:
        ValueError: If language is not supported

    Example:
        >>> from language_handlers import get_handler
        >>> handler = get_handler('vfp', config={'chunk_size': 150})
        >>> extensions = handler.get_file_extensions()
        >>> print(extensions)  # ['.prg', '.spr']
    """
    language_lower = language.lower()

    # Lazy import handlers to avoid circular dependencies
    if language_lower == 'vfp' and 'vfp' not in _HANDLER_REGISTRY:
        from .vfp_handler import VFPHandler
        register_handler('vfp', VFPHandler)

    if language_lower == 'csharp' and 'csharp' not in _HANDLER_REGISTRY:
        from .csharp_handler import CSharpHandler
        register_handler('csharp', CSharpHandler)

    # Get handler class from registry
    if language_lower not in _HANDLER_REGISTRY:
        available = ', '.join(_HANDLER_REGISTRY.keys())
        raise ValueError(
            f"Unsupported language: '{language}'. "
            f"Available languages: {available if available else 'none (no handlers registered)'}"
        )

    handler_class = _HANDLER_REGISTRY[language_lower]

    # Instantiate and return handler
    # Note: Handlers may need config in their __init__
    if config is not None:
        return handler_class(config)
    else:
        return handler_class()


def list_supported_languages() -> list:
    """
    Get list of all supported languages.

    Returns:
        list: List of language identifiers
    """
    # Ensure all handlers are registered by attempting to import
    try:
        from .vfp_handler import VFPHandler
        register_handler('vfp', VFPHandler)
    except ImportError:
        pass

    try:
        from .csharp_handler import CSharpHandler
        register_handler('csharp', CSharpHandler)
    except ImportError:
        pass

    return list(_HANDLER_REGISTRY.keys())


# Public API
__all__ = [
    'LanguageHandler',
    'get_handler',
    'list_supported_languages',
    'register_handler'
]
