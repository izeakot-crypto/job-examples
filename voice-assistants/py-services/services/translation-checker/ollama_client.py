#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DEPRECATED: Используйте llm_client.py вместо этого файла.
Этот файл сохранён для обратной совместимости.
"""
from .llm_client import LLMClient as OllamaClient, parse_llm_json  # noqa: F401

__all__ = ["OllamaClient", "parse_llm_json"]
