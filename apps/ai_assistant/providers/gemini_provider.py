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

        # Cap output tokens to configured maximum to bound latency
        max_output_cap = getattr(settings, 'AI_MAX_OUTPUT_TOKENS', 400)
        max_output_tokens = min(max_tokens, max_output_cap)

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

        # Cap output tokens to configured maximum to bound latency
        max_output_cap = getattr(settings, 'AI_MAX_OUTPUT_TOKENS', 400)
        max_output_tokens = min(max_tokens, max_output_cap)

        # Config
        config_kwargs: dict = {
            'max_output_tokens': max_output_tokens,
            'temperature': getattr(settings, 'AI_TEMPERATURE', 0.2),
        }

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

    def chat_stream(
        self,
        messages: list[AIMessage],
        tools: list[dict] | None = None,
        system: str | None = None,
        max_tokens: int | None = None,
    ):
        """Fallback streaming: call chat() and yield text chunks, then final metadata dict.
        Real streaming is used if the SDK supports it; this fallback provides partial UX
        improvements by enabling the caller to consume chunks without changing the
        sync chat API contract.
        """
        resp = self.chat(messages=messages, tools=tools, system=system, max_tokens=max_tokens)
        text = resp.content or ''
        chunk_size = getattr(settings, 'AI_STREAM_CHUNK_SIZE', 160)
        for i in range(0, len(text), chunk_size):
            yield text[i:i+chunk_size]
        # Final metadata so caller can get tokens/tool_calls/raw
        yield {
            '__final': True,
            'tokens_used': resp.tokens_used,
            'tool_calls': resp.tool_calls,
            'raw': resp.raw,
        }

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
