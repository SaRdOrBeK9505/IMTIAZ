"""
Google Gemini AI Provider implementatsiyasi.
SDK: google-genai (yangi, rasmiy)  pip install google-genai
Model: gemini-3.6-flash (settings.GEMINI_MODEL orqali o'zgartiriladi)
"""

from __future__ import annotations

import logging
from django.conf import settings

from .base import BaseAIProvider, AIMessage, AIResponse

logger = logging.getLogger(__name__)


class GeminiProvider(BaseAIProvider):
    """
    Google Gemini API provider — google-genai SDK.
    Tool-calling Claude bilan bir xil interfeys orqali ishlaydi.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model   = model  or settings.GEMINI_MODEL

        from google import genai
        self._client = genai.Client(api_key=self.api_key)
        self._genai  = genai

    def get_model_name(self) -> str:
        return self.model

    def chat(
        self,
        messages: list[AIMessage],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ) -> AIResponse:
        from google.genai import types

        if max_tokens is None:
            max_tokens = getattr(settings, 'AI_MAX_TOKENS', 4096)

        # Xabarlarni Gemini Content formatiga o'girish
        gemini_contents = []
        for msg in messages:
            if msg.role == 'system':
                continue  # system_instruction orqali beriladi
            role    = 'user' if msg.role == 'user' else 'model'
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            gemini_contents.append(
                types.Content(role=role, parts=[types.Part(text=content)])
            )

        # Config
        config_kwargs: dict = {
            'max_output_tokens': max_tokens,
            'temperature': getattr(settings, 'AI_TEMPERATURE', 0.2),
        }
        if hasattr(types, 'ThinkingConfig'):
            try:
                config_kwargs['thinking_config'] = types.ThinkingConfig(thinking_budget=0)
            except Exception:
                pass

        if system:
            config_kwargs['system_instruction'] = system

        # Tool-calling: Gemini FunctionDeclaration
        if tools:
            config_kwargs['tools'] = [self._convert_tools(tools)]

        config = types.GenerateContentConfig(**config_kwargs)

        try:
            response = self._client.models.generate_content(
                model    = self.model,
                contents = gemini_contents,
                config   = config,
            )
        except Exception as e:
            logger.exception('Gemini API xatosi: %s', e)
            raise

        # Javobni parse qilish
        text_content = ''
        tool_calls   = []

        candidate = response.candidates[0] if response.candidates else None
        if candidate:
            for part in (candidate.content.parts or []):
                if part.text:
                    text_content += part.text
                elif part.function_call:
                    fc = part.function_call
                    tool_calls.append({
                        'id':    f'gemini-{fc.name}',
                        'name':  fc.name,
                        'input': dict(fc.args) if fc.args else {},
                    })

        # Token hisoblash
        try:
            tokens_used = (
                response.usage_metadata.prompt_token_count +
                response.usage_metadata.candidates_token_count
            )
        except Exception:
            tokens_used = 0

        return AIResponse(
            content     = text_content,
            tool_calls  = tool_calls,
            tokens_used = tokens_used,
            stop_reason = 'end_turn',
            raw         = response,
        )

    @staticmethod
    def _convert_tools(tools: list[dict]):
        """
        Claude tool format → Gemini Tool formatiga o'girish.

        Claude format:
            {'name': '...', 'description': '...', 'input_schema': {...}}

        Gemini format:
            Tool(function_declarations=[FunctionDeclaration(...)])
        """
        from google.genai import types

        declarations = []
        for tool in tools:
            schema = tool.get('input_schema', {})

            properties = {}
            for prop_name, prop_val in schema.get('properties', {}).items():
                prop_type = prop_val.get('type', 'string')
                properties[prop_name] = types.Schema(
                    type        = _map_type(prop_type),
                    description = prop_val.get('description', ''),
                )

            parameters = types.Schema(
                type       = types.Type.OBJECT,
                properties = properties,
                required   = schema.get('required', []),
            )

            declarations.append(
                types.FunctionDeclaration(
                    name        = tool['name'],
                    description = tool.get('description', ''),
                    parameters  = parameters,
                )
            )

        return types.Tool(function_declarations=declarations)


def _map_type(json_type: str):
    """JSON Schema type → Gemini Type."""
    from google.genai.types import Type
    mapping = {
        'string':  Type.STRING,
        'integer': Type.INTEGER,
        'number':  Type.NUMBER,
        'boolean': Type.BOOLEAN,
        'array':   Type.ARRAY,
        'object':  Type.OBJECT,
    }
    return mapping.get(json_type, Type.STRING)
