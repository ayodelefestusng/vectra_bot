import httpx
import json
import logging
import asyncio
import os
import httpx
import traceback
import httpx
import os
import logging
from ollama import Client
try:
    from ollama import Client as OllamaClient
except Exception:
    OllamaClient = None
from typing import List, Dict, Any, Optional, Union, Iterator, AsyncIterator
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage, HumanMessage, AIMessageChunk
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from langchain_core.callbacks.manager import CallbackManagerForLLMRun, AsyncCallbackManagerForLLMRun
from langchain_core.language_models import LanguageModelInput
from langchain_core.runnables import Runnable
from langchain_core.outputs import ChatResult, ChatGeneration, ChatGenerationChunk
from langchain_core.utils.function_calling import convert_to_openai_function
from langchain_core.utils.function_calling import convert_to_openai_function

from pydantic import Field
from langchain_core.language_models import BaseChatModel

logger = logging.getLogger(__name__)

# class OllamaService(BaseChatModel):
#     base_url: str
#     username: str
#     password: str
#     model: str
#     timeout: float = 60.0

#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)

#     @property
#     def _llm_type(self) -> str:
#         return "ollama_custom"

#     def _generate(
#         self,
#         messages: List[BaseMessage],
#         stop: Optional[List[str]] = None,
#         run_manager: Optional[CallbackManagerForLLMRun] = None,
#         **kwargs: Any,
#     ) -> ChatResult:
#         """Synchronous implementation of LLM generation."""
#         ollama_messages = self._prepare_messages(messages)

#         if self.model == "ollama_cloud":
#             try:
#                 logger.info(f"!!! TRACE: OllamaService._generate (cloud) starting for model {self.model}", flush=True)
#                 resp = self._cloud_call_sync(ollama_messages)
#                 logger.info("!!! TRACE: OllamaService._generate (cloud) call returned successfully", flush=True)
#                 return self._process_cloud_response(resp)
#             except Exception as e:
#                 logger.info(f"!!! TRACE: OllamaService._generate (cloud) FAILED: {e}", flush=True)
#                 logger.error(f"Ollama Cloud sync call failed: {e}")
#                 raise

#         # Local Ollama sync call
#         payload = self._prepare_payload(ollama_messages, **kwargs)
#         try:
#             import httpx
#             with httpx.Client(timeout=self.timeout) as client:
#                 response = client.post(
#                     self.base_url,
#                     json=payload,
#                     auth=(self.username, self.password),
#                     headers={"Content-Type": "application/json"}
#                 )
#                 if response.status_code != 200:
#                     return ChatResult(generations=[ChatGeneration(message=AIMessage(content=f"Error {response.status_code}"))])
                
#                 return self._process_local_response(response.json())
#         except Exception as e:
#             logger.error(f"Ollama local sync call failed: {e}")
#             raise

#     async def _agenerate(
#         self,
#         messages: List[BaseMessage],
#         stop: Optional[List[str]] = None,
#         run_manager: Optional[AsyncCallbackManagerForLLMRun] = None,
#         **kwargs: Any,
#     ) -> ChatResult:
#         """Asynchronous implementation of LLM generation."""
#         ollama_messages = self._prepare_messages(messages)

#         if self.model == "ollama_cloud":
#             try:
#                 resp = await asyncio.to_thread(self._cloud_call_sync, ollama_messages)
#                 return self._process_cloud_response(resp)
#             except Exception as e:
#                 logger.error(f"Ollama Cloud async call failed: {e}")
#                 raise

#         # Local Ollama async call
#         payload = self._prepare_payload(ollama_messages, **kwargs)
#         try:
#             async with httpx.AsyncClient(timeout=self.timeout) as client:
#                 response = await client.post(
#                     self.base_url,
#                     json=payload,
#                     auth=(self.username, self.password),
#                     headers={"Content-Type": "application/json"}
#                 )
#                 return self._process_local_response(response.json())
#         except Exception as e:
#             logger.error(f"Ollama local async call failed: {e}")
#             raise

#     def _prepare_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
#         ollama_messages = []
#         for m in messages:
#             role = "user"
#             if isinstance(m, SystemMessage): role = "system"
#             elif isinstance(m, AIMessage): role = "assistant"
#             ollama_messages.append({"role": role, "content": m.content})
#         return ollama_messages

#     def _prepare_payload(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
#         tools = kwargs.pop("tools", None)
#         format_val = kwargs.pop("format", None)
#         payload = {"model": self.model, "messages": messages, "stream": False, **kwargs}
#         if format_val: payload["format"] = format_val
#         if tools: payload["tools"] = tools
#         return payload

#     def _cloud_call_sync(self, messages: List[Dict[str, str]]):
#         api_key = os.getenv("OLLAMA_API_KEY", "").strip('"').strip("'")
#         cloud_model = os.getenv("OLLAMA_CLOUD_MODEL", "gpt-oss:120b")
#         if cloud_model.endswith("-cloud"): cloud_model = cloud_model[:-6]
        
#         # Use direct httpx for the cloud call as well to bypass any library-level async logic
#         import httpx
#         url = "https://ollama.com/api/chat"
#         payload = {
#             "model": cloud_model,
#             "messages": messages,
#             "stream": False
#         }
#         headers = {
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json"
#         }
        
#         with httpx.Client(timeout=self.timeout) as client:
#             response = client.post(url, json=payload, headers=headers)
#             if response.status_code != 200:
#                 raise Exception(f"Ollama Cloud API error {response.status_code}: {response.text}")
#             return response.json()

#     def _process_cloud_response(self, resp) -> ChatResult:
#         # Re-using the same extraction logic from your original file
#         content = ""
#         # Since resp is now a dict from response.json(), we use .get() instead of getattr
#         msg_data = resp.get("message", {}) if isinstance(resp, dict) else getattr(resp, "message", {})
        
#         if isinstance(msg_data, dict): content = msg_data.get("content") or msg_data.get("response")
#         elif hasattr(msg_data, "content"): content = msg_data.content
        
#         raw_tool_calls = msg_data.get('tool_calls') if isinstance(msg_data, dict) else getattr(msg_data, 'tool_calls', [])
#         if raw_tool_calls is None: raw_tool_calls = []
#         formatted_tool_calls = self._format_tool_calls(raw_tool_calls)
        
#         return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content or "", tool_calls=formatted_tool_calls))])

#     def _process_local_response(self, data: Dict[str, Any]) -> ChatResult:
#         msg_data = data.get('message', {})
#         content = msg_data.get('content', data.get('response', ''))
#         formatted_tool_calls = self._format_tool_calls(msg_data.get('tool_calls', []))
#         return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content, tool_calls=formatted_tool_calls))])

#     def _format_tool_calls(self, raw_tool_calls: Optional[List[Any]]) -> List[Dict[str, Any]]:
#         formatted = []
#         if raw_tool_calls is None:
#             return formatted
#         for i, tc in enumerate(raw_tool_calls):
#             if "function" in tc:
#                 f = tc["function"]
#                 args = f.get("arguments")
#                 if isinstance(args, str):
#                     try: args = json.loads(args)
#                     except: pass
#                 formatted.append({"name": f.get("name"), "args": args, "id": tc.get("id", f"call_{i}")})
#             else:
#                 formatted.append(tc)
#         return formatted


#     def bind_tools(
#         self,
#         tools: Union[List[Any], Any],
#         **kwargs: Any,
#     ) -> Runnable[LanguageModelInput, AIMessage]:
#         """
#         Bind tools for compatibility with LangGraph and other LangChain components.
#         """
#         from langchain_core.utils.function_calling import convert_to_openai_function
#         openai_tools = [convert_to_openai_function(t) for t in tools]
#         ollama_tools = [{"type": "function", "function": t} for t in openai_tools]
        
#         return self.bind(tools=ollama_tools, **kwargs)

#     async def close(self):
#         pass



class OllamaService(BaseChatModel):
    model: str = Field(default="gpt-oss:120b")
    timeout: float = Field(default=60.0)
    base_url: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)

    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)

    @property
    def _llm_type(self) -> str:
        return "ollama_cloud_only"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        # Pass tools and format through to the cloud call
        ollama_messages = self._prepare_messages(messages)
        tools = kwargs.get("tools")
        format_val = kwargs.get("format") or kwargs.get("response_format")
        resp = self._cloud_call_sync(ollama_messages, tools=tools, format=format_val)
        return self._process_cloud_response(resp)
    
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        ollama_messages = self._prepare_messages(messages)
        tools = kwargs.get("tools")
        format_val = kwargs.get("format") or kwargs.get("response_format")
        # Offload sync cloud call to thread
        resp = await asyncio.to_thread(self._cloud_call_sync, ollama_messages, tools=tools, format=format_val)
        return self._process_cloud_response(resp)

    def _prepare_messages(self, messages: List[Any]) -> List[Dict[str, Any]]:
        ollama_messages = []
        for m in messages:
            role = "user"
            msg_dict = {"content": m.content or ""}
            
            m_type = getattr(m, "type", "")
            m_class = m.__class__.__name__
            
            if m_type == "system" or m_class == "SystemMessage":
                role = "system"
            elif m_type == "ai" or m_class == "AIMessage":
                role = "assistant"
                tool_calls = getattr(m, "tool_calls", [])
                if tool_calls:
                    msg_dict["tool_calls"] = [
                        {"function": {"name": tc["name"], "arguments": tc.get("args", {})}}
                        for tc in tool_calls
                    ]
            elif m_type == "tool" or m_class == "ToolMessage":
                role = "tool"
                
            msg_dict["role"] = role
            ollama_messages.append(msg_dict)
        return ollama_messages

    def _prepare_payload(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        tools = kwargs.pop("tools", None)
        format_val = kwargs.pop("format", None)
        payload = {"model": self.model, "messages": messages, "stream": False, **kwargs}
        if format_val: payload["format"] = format_val
        if tools: payload["tools"] = tools
        return payload

    def _cloud_call_sync(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None, format: Optional[Any] = None):
        api_key = os.getenv("OLLAMA_API_KEY", "").strip('"').strip("'")
        cloud_model = self.model if self.model != "ollama_cloud" else os.getenv("OLLAMA_CLOUD_MODEL", "gpt-oss:120b")
        if cloud_model.endswith("-cloud"): cloud_model = cloud_model[:-6]
        
        # Use direct httpx for the cloud call as well to bypass any library-level async logic
        
        url = self.base_url if self.base_url else "https://ollama.com/api/chat"
        payload = {
            "model": cloud_model,
            "messages": messages,
            "stream": False
        }
        if tools:
            payload["tools"] = tools

        if format:
            # Handle potential pydantic/schema objects for format
            if hasattr(format, "schema"): payload["format"] = format.schema()
            elif isinstance(format, dict): payload["format"] = format
            else: payload["format"] = format

        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        auth = (self.username, self.password) if self.username and self.password else None
        with httpx.Client(timeout=self.timeout) as client:
            if auth:
                response = client.post(url, json=payload, headers=headers, auth=auth)
            else:
                response = client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"Ollama Cloud API error {response.status_code}: {response.text}")
            return response.json()

    def _process_cloud_response(self, resp) -> ChatResult:
        # Re-using the same extraction logic from your original file
        content = ""
        # Since resp is now a dict from response.json(), we use .get() instead of getattr
        msg_data = resp.get("message", {}) if isinstance(resp, dict) else getattr(resp, "message", {})
        
        if isinstance(msg_data, dict): content = msg_data.get("content") or msg_data.get("response")
        elif hasattr(msg_data, "content"): content = msg_data.content
        
        raw_tool_calls = msg_data.get('tool_calls') if isinstance(msg_data, dict) else getattr(msg_data, 'tool_calls', [])
        if raw_tool_calls is None: raw_tool_calls = []
        formatted_tool_calls = self._format_tool_calls(raw_tool_calls)
        
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content or "", tool_calls=formatted_tool_calls))])

    def _process_local_response(self, data: Dict[str, Any]) -> ChatResult:
        msg_data = data.get('message', {})
        content = msg_data.get('content', data.get('response', ''))
        formatted_tool_calls = self._format_tool_calls(msg_data.get('tool_calls', []))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content, tool_calls=formatted_tool_calls))])

    def _format_tool_calls(self, raw_tool_calls: Optional[List[Any]]) -> List[Dict[str, Any]]:
        formatted = []
        if raw_tool_calls is None:
            return formatted
        for i, tc in enumerate(raw_tool_calls):
            if "function" in tc:
                f = tc["function"]
                args = f.get("arguments")
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except: pass
                formatted.append({"name": f.get("name"), "args": args, "id": tc.get("id", f"call_{i}")})
            else:
                formatted.append(tc)
        return formatted


    def bind_tools(
        self,
        tools: Union[List[Any], Any],
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """
        Bind tools for compatibility with LangGraph and other LangChain components.
        """
        openai_tools = [convert_to_openai_function(t) for t in tools]
        ollama_tools = [{"type": "function", "function": t} for t in openai_tools]
        
        return self.bind(tools=ollama_tools, **kwargs)

    async def close(self):
        pass



class OllamaServicev1(BaseChatModel):
    model: str = Field(default="gpt-oss:120b")
    timeout: float = Field(default=60.0)
    base_url: Optional[str] = Field(default=None)
    username: Optional[str] = Field(default=None)
    password: Optional[str] = Field(default=None)

    # def __init__(self, **kwargs):
    #     super().__init__(**kwargs)

    @property
    def _llm_type(self) -> str:
        return "ollama_cloud_only"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        # Pass tools and format through to the cloud call
        ollama_messages = self._prepare_messages(messages)
        tools = kwargs.get("tools")
        format_val = kwargs.get("format") or kwargs.get("response_format")
        resp = self._cloud_call_sync(ollama_messages, tools=tools, format=format_val)
        return self._process_cloud_response(resp)
    
    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        ollama_messages = self._prepare_messages(messages)
        tools = kwargs.get("tools")
        format_val = kwargs.get("format") or kwargs.get("response_format")
        # Offload sync cloud call to thread
        resp = await asyncio.to_thread(self._cloud_call_sync, ollama_messages, tools=tools, format=format_val)
        return self._process_cloud_response(resp)

    def _prepare_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        ollama_messages = []
        for m in messages:
            role = "user"
            if isinstance(m, SystemMessage): role = "system"
            elif isinstance(m, AIMessage): role = "assistant"
            ollama_messages.append({"role": role, "content": m.content})
        return ollama_messages

    def _prepare_payload(self, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        tools = kwargs.pop("tools", None)
        format_val = kwargs.pop("format", None)
        payload = {"model": self.model, "messages": messages, "stream": False, **kwargs}
        if format_val: payload["format"] = format_val
        if tools: payload["tools"] = tools
        return payload

    def _cloud_call_sync(self, messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None, format: Optional[Any] = None):
        api_key = os.getenv("OLLAMA_API_KEY", "").strip('"').strip("'")
        cloud_model = self.model if self.model != "ollama_cloud" else os.getenv("OLLAMA_CLOUD_MODEL", "gpt-oss:120b")
        if cloud_model.endswith("-cloud"): cloud_model = cloud_model[:-6]
        
        # Use direct httpx for the cloud call as well to bypass any library-level async logic
      
        url = self.base_url if hasattr(self, 'base_url') and self.base_url else "https://ollama.com/api/chat"
        payload = {
            "model": cloud_model,
            "messages": messages,
            "stream": False
        }
        if tools:
            payload["tools"] = tools

        if format:
            if hasattr(format, "schema"): payload["format"] = format.schema()
            elif isinstance(format, dict): payload["format"] = format
            else: payload["format"] = format

        headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        auth = (self.username, self.password) if self.username and self.password else None
        with httpx.Client(timeout=self.timeout) as client:
            if auth:
                response = client.post(url, json=payload, headers=headers, auth=auth)
            else:
                response = client.post(url, json=payload, headers=headers)
            if response.status_code != 200:
                raise Exception(f"Ollama Cloud API error {response.status_code}: {response.text}")
            return response.json()

    def _process_cloud_response(self, resp) -> ChatResult:
        # Re-using the same extraction logic from your original file
        content = ""
        # Since resp is now a dict from response.json(), we use .get() instead of getattr
        msg_data = resp.get("message", {}) if isinstance(resp, dict) else getattr(resp, "message", {})
        
        if isinstance(msg_data, dict): content = msg_data.get("content") or msg_data.get("response")
        elif hasattr(msg_data, "content"): content = msg_data.content
        
        raw_tool_calls = msg_data.get('tool_calls') if isinstance(msg_data, dict) else getattr(msg_data, 'tool_calls', [])
        if raw_tool_calls is None: raw_tool_calls = []
        formatted_tool_calls = self._format_tool_calls(raw_tool_calls)
        
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content or "", tool_calls=formatted_tool_calls))])

    def _process_local_response(self, data: Dict[str, Any]) -> ChatResult:
        msg_data = data.get('message', {})
        content = msg_data.get('content', data.get('response', ''))
        formatted_tool_calls = self._format_tool_calls(msg_data.get('tool_calls', []))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content, tool_calls=formatted_tool_calls))])

    def _format_tool_calls(self, raw_tool_calls: Optional[List[Any]]) -> List[Dict[str, Any]]:
        formatted = []
        if raw_tool_calls is None:
            return formatted
        for i, tc in enumerate(raw_tool_calls):
            if "function" in tc:
                f = tc["function"]
                args = f.get("arguments")
                if isinstance(args, str):
                    try: args = json.loads(args)
                    except: pass
                formatted.append({"name": f.get("name"), "args": args, "id": tc.get("id", f"call_{i}")})
            else:
                formatted.append(tc)
        return formatted


    def bind_tools(
        self,
        tools: Union[List[Any], Any],
        **kwargs: Any,
    ) -> Runnable[LanguageModelInput, AIMessage]:
        """
        Bind tools for compatibility with LangGraph and other LangChain components.
        """
        openai_tools = [convert_to_openai_function(t) for t in tools]
        ollama_tools = [{"type": "function", "function": t} for t in openai_tools]
        
        return self.bind(tools=ollama_tools, **kwargs)

    async def close(self):
        pass

class OllamaCloudWrapper:
    def __init__(self, model_name: str, host: str, api_key: str):
        self.model_name = model_name
        self.client = Client(
            host=host,
            headers={'Authorization': f'Bearer {api_key}'}
        )

    def invoke(self, prompt: str) -> str:
        """
        Standardized invoke method to match LangChain style.
        """
        try:
            logger.info(f"Invoking {self.model_name} via {self.client._client.base_url}")
            
            # Non-streaming call for a single block response
            response = self.client.chat(
                model=self.model_name,
                messages=[{'role': 'user', 'content': prompt}],
                stream=False
            )
            
            # Extract content safely
            content = response.get('message', {}).get('content', '')
            return content

        except Exception as e:
            logger.error(f"Invoke failed: {str(e)}", exc_info=True)
            return "Error: Could not retrieve response from Ollama Cloud."

# --- Implementation ---