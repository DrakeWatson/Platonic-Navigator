#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
LLM Toolbox
============

This script serves as a template for toolbox modules within the self-iterating
code repository. Toolboxes contain a single class, `TYPEToolbox`, which groups
related utility functions and data structures for a specific category (e.g.,
FileIO, LLM interaction, Logging).

**File Header Format:**
	- Shebang: `#!/usr/bin/env python3`
	- Encoding: `-*- coding: utf-8 -*-`
	- Docstring: A comprehensive description of the toolbox's purpose and
	  functionality, adhering to standard Python docstring conventions. Should
	  include 'description' and 'usage' fields.

**Function Header Format:**
	Each method within the class should include a docstring explaining its
	purpose, arguments, and return values, following standard Python
	docstring conventions. Should include a brief description of the function
	and then 'args' and 'returns' fields.
"""


import os
import sys
import openai
import google.generativeai as genai
import tiktoken
import os
import time
from typing import Dict, Any, Tuple, Optional, Union

# If *_toolbox.py is in REPO_ROOT/TOOLBOXES/, then REPO_ROOT is two levels up.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
	sys.path.insert(0, project_root)

import argparse

# Assuming logging_toolbox.py and test_toolbox.py are in TOOLBOXES folder
# and TOOLBOXES is in PYTHONPATH or accessible
try:
	from TOOLBOXES import logging_toolbox
	from TOOLBOXES import test_toolbox
	from TOOLBOXES import file_io_toolbox
except ImportError as e:
	print(f"Error importing a core toolbox: {e}")
	sys.exit(1)

log = logging_toolbox.LoggingToolbox()

# --- Constants ---
# For retry logic
MAX_RATE_LIMIT_RETRY_DURATION_SECONDS = 10 * 60  # 10 minutes
DEFAULT_MAX_TRANSIENT_ERROR_RETRIES = 3
INITIAL_BACKOFF_SECONDS = 1
MAX_BACKOFF_SECONDS = 60

_MODEL_COSTS: Dict[str, Dict[str, Dict[str, Union[float, int]]]] = {
		"openai": {
			"gpt-3.5-turbo": {"input_cost_per_1k_tokens": 0.0005, "output_cost_per_1k_tokens": 0.0015, "context_window_tokens": 16385, "output_max_tokens": 4096},
			"gpt-3.5-turbo-0125": {"input_cost_per_1k_tokens": 0.0005, "output_cost_per_1k_tokens": 0.0015, "context_window_tokens": 16385, "output_max_tokens": 4096},
			"gpt-3.5-turbo-instruct": {"input_cost_per_1k_tokens": 0.0015, "output_cost_per_1k_tokens": 0.0020, "context_window_tokens": 4096, "output_max_tokens": 4096},
			"gpt-4": {"input_cost_per_1k_tokens": 0.03, "output_cost_per_1k_tokens": 0.06, "context_window_tokens": 8192, "output_max_tokens": 8192}, # gpt-4-0613
			"gpt-4-0613": {"input_cost_per_1k_tokens": 0.03, "output_cost_per_1k_tokens": 0.06, "context_window_tokens": 8192, "output_max_tokens": 8192},
			"gpt-4-turbo-preview": {"input_cost_per_1k_tokens": 0.01, "output_cost_per_1k_tokens": 0.03, "context_window_tokens": 128000, "output_max_tokens": 4096},
			"gpt-4-turbo": {"input_cost_per_1k_tokens": 0.01, "output_cost_per_1k_tokens": 0.03, "context_window_tokens": 128000, "output_max_tokens": 4096}, # gpt-4-turbo-2024-04-09
			"gpt-4-turbo-2024-04-09": {"input_cost_per_1k_tokens": 0.01, "output_cost_per_1k_tokens": 0.03, "context_window_tokens": 128000, "output_max_tokens": 4096},
			"gpt-4o": {"input_cost_per_1k_tokens": 0.005, "output_cost_per_1k_tokens": 0.015, "context_window_tokens": 128000, "output_max_tokens": 4096}, # gpt-4o-2024-05-13
			"gpt-4o-2024-05-13": {"input_cost_per_1k_tokens": 0.005, "output_cost_per_1k_tokens": 0.015, "context_window_tokens": 128000, "output_max_tokens": 4096},
			"gpt-4.1": {"input_cost_per_1k_tokens": 0.002, "output_cost_per_1k_tokens": 0.008, "context_window_tokens": 128000, "output_max_tokens": 4096},
			"gpt-4.1-mini": {"input_cost_per_1k_tokens": 0.0004, "output_cost_per_1k_tokens": 0.0016, "context_window_tokens": 128000, "output_max_tokens": 4096},
			"gpt-4.1-nano": {"input_cost_per_1k_tokens": 0.0001, "output_cost_per_1k_tokens": 0.0004, "context_window_tokens": 128000, "output_max_tokens": 4096},
			"gpt-4o-mini": {"input_cost_per_1k_tokens": 0.00015, "output_cost_per_1k_tokens": 0.0006, "context_window_tokens": 128000, "output_max_tokens": 4096} # Adjusted to be closer to $0.15/$0.60 per 1M
		},
		"google": {

			"gemini-1.5-flash-latest": {"input_cost_per_1k_tokens": 0.000075, "output_cost_per_1k_tokens": 0.00070, "context_window_tokens": 1048576, "output_max_tokens": 8192},
			"gemini-1.5-pro-latest": {"input_cost_per_1k_tokens": 0.00125, "output_cost_per_1k_tokens": 0.005, "context_window_tokens": 1048576, "output_max_tokens": 8192},
			"gemini-1.0-pro": {"input_cost_per_1k_tokens": 0.000125, "output_cost_per_1k_tokens": 0.000375, "context_window_tokens": 30720, "output_max_tokens": 2048},
			"gemini-2.5-pro-preview-05-06": {"input_cost_per_1k_tokens": 0.00125, "output_cost_per_1k_tokens": 0.01, "context_window_tokens": 1048576, "output_max_tokens": 65536},
			"gemini-2.5-flash-preview-05-20": {"input_cost_per_1k_tokens": 0.00015, "output_cost_per_1k_tokens": 0.0006, "context_window_tokens": 1048576, "output_max_tokens": 8192}
		}
	}

# --- Custom Exceptions ---
class LLMToolboxError(Exception):
	"""Base exception for LLMToolbox errors."""
	pass

class APIKeyMissingError(LLMToolboxError):
	"""Raised when an API key is not found."""
	pass

class ModelNotFoundError(LLMToolboxError):
	"""Raised when model cost info is not found."""
	pass

class APICommunicationError(LLMToolboxError):
	"""Raised for general API communication issues after retries."""
	pass

class RateLimitExceededError(APICommunicationError):
	"""Raised when rate limits are exceeded after all retries."""
	pass

class ContentGenerationError(LLMToolboxError):
	"""Raised when the LLM fails to generate content for reasons other than rate limits."""
	pass

class TokenLimitError(LLMToolboxError):
	"""Raised when the prompt exceeds the model's context window."""
	pass

class LLMToolbox:
	"""
	LLM Toolbox
	"""
	def __init__(self):
		"""
		Initializes the LLMToolbox.
		"""
		self.f_io = file_io_toolbox.FileIOToolbox()
		self.openai_client = None
		self.google_client = None
		self.requests_sent_this_minute = 0
		self.tokens_sent_this_minute = 0
		self.last_minute_sent = time.time()

		# Load API keys and initialize clients
		try:
			openai_api_key = os.environ.get("OPENAI_API_KEY")
			if not openai_api_key:
				log.warning("OPENAI_API_KEY environment variable not found. OpenAI calls will fail.")
			else:
				self.openai_client = openai.OpenAI(api_key=openai_api_key)
				log.info("OpenAI client initialized.")

			google_api_key = os.environ.get("GEMINI_API_KEY") # Changed from GOOGLE_API_KEY to GEMINI_API_KEY as per user
			if not google_api_key:
				log.warning("GEMINI_API_KEY environment variable not found. Google Gemini calls will fail.")
			else:
				genai.configure(api_key=google_api_key)
				# Test configuration by listing models (optional, can be removed)
				# models_list = [m for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
				# if not models_list:
				#	 log.warning("Google Gemini API key configured, but no usable models found or API test failed.")
				# else:
				# self.google_client = genai # The genai module itself is used for calls like genai.GenerativeModel
				log.info("Google Gemini client configured.")

		except Exception as e:
			log.error(f"Error during API client initialization: {e}")
			# Not raising here, allow partial functionality if one key is missing.

	def _get_model_info(self, provider: str, model_name: str) -> Dict[str, Union[float, int]]:
		"""
		Retrieves cost and context window info for a given model.
		
		Args:
			provider (str): The provider name (e.g., "openai", "google")
			model_name (str): The model name (e.g., "gpt-4", "gemini-1.5-pro-latest")

		Returns:
			Dict[str, Union[float, int]]: A dictionary containing cost and context window info.
		"""
		try:
			return _MODEL_COSTS[provider][model_name]
		except KeyError:
			log.error(f"Model '{model_name}' not found in cost dictionary for provider '{provider}'.")
			raise ModelNotFoundError(f"Cost and context information for model '{provider}/{model_name}' not found.")

	def _count_tokens(self, text: str, provider: str, model_name: str) -> int:
		"""
		Counts tokens for the given text using the appropriate tokenizer.

		Args:
			text (str): The text to count tokens for.
			provider (str): The provider name (e.g., "openai", "google")
			model_name (str): The model name (e.g., "gpt-4", "gemini-1.5-pro-latest")

		Returns:
			int: The number of tokens in the text.
		"""
		if provider == "openai":
			try:
				encoding = tiktoken.encoding_for_model(model_name)
			except KeyError:
				log.warning(f"No encoding found for OpenAI model {model_name}. Using cl100k_base as default.")
				encoding = tiktoken.get_encoding("cl100k_base")
			return len(encoding.encode(text))
		elif provider == "google":
			# For Google Gemini, we use the model's count_tokens method.
			# This requires the model object. We'll do this within the call_llm
			# or have a separate setup for Google models if direct token count is needed before API call.
			# For now, this is a placeholder; actual counting happens with the model instance.
			# A more direct way:
			try:
				# Ensure the model name is valid for genai.GenerativeModel
				# This might require stripping suffixes not used by the SDK model identifier
				# e.g. if _MODEL_COSTS has "gemini-1.5-pro-latest" but SDK needs "models/gemini-1.5-pro-latest"
				# For simplicity, we assume model_name in _MODEL_COSTS is usable or adapted.
				# A common pattern is "models/model-name" for Gemini API.
				sdk_model_name = model_name if model_name.startswith("models/") else f"models/{model_name}"

				# Check if client is configured
				if os.environ.get("GEMINI_API_KEY"):
					model_instance = genai.GenerativeModel(sdk_model_name)
					return model_instance.count_tokens(text).total_tokens
				else:
					log.warning("GEMINI_API_KEY not set, cannot count tokens for Google model.")
					return 0 # Or raise an error
			except Exception as e:
				log.error(f"Could not count tokens for Google model {model_name}: {e}")
				# Fallback or re-raise. For now, returning a high number to potentially prevent call
				# Or, better, this should be handled before attempting the call.
				# This indicates a setup issue or invalid model name for the SDK.
				raise APICommunicationError(f"Failed to initialize Google model {model_name} for token counting: {e}")
		else:
			log.error(f"Unsupported provider for token counting: {provider}")
			raise ValueError(f"Unsupported provider: {provider}")


	def _calculate_cost(self, tokens: int, cost_per_1k_tokens: float) -> float:
		"""
		Calculates the cost for a given number of tokens.

		Args:
			tokens (int): The number of tokens to calculate cost for.
			cost_per_1k_tokens (float): The cost per 1k tokens.

		Returns:
		"""
		return (tokens / 1000) * cost_per_1k_tokens
	
	def call_gemini(self, gemini_prompt: str, force_json: bool = False, json_schema: dict = None) -> str:
		"""
		Calls the Gemini Pro model with the given prompt and parameters.

		Args:
			gemini_prompt: str
		"""
		log.line_break("debug")
		log.debug(f"Waiting for Gemini call to complete...")
		return_dict, stats = self.call_llm(provider="google", model_name="gemini-2.5-flash-preview-05-20", prompt=gemini_prompt, max_output_tokens=65536, 
									 temperature=0, force_json = force_json, json_schema=json_schema)
		log.debug("Gemini call returned.")
		#for key, value in return_dict.items():
		#	log.debug(f"{key}: {value}\n")
		log.debug("Gemini call stats:")
		for key, value in stats.items():
			if key not in ["raw_api_response"]:
				log.debug(f"{key}: {value}\n")
		log.line_break("debug")
        
		log.debug(f"Total Return Dict: \n {return_dict}")
		# Need to remove ```python ```json and ``` from the response text because gemini is fucking annoying
		if return_dict["llm_response_text"] is not None:
			return_dict["llm_response_text"] = return_dict["llm_response_text"].replace("```python", "").replace("```json", "").replace("```", "")
		else:
			return_dict["llm_response_text"] = ""
			
		return return_dict["llm_response_text"], stats

	def call_gpt_4_1(self, gpt_4_1_prompt: str) -> str:
		"""
		Calls the GPT-4.1 model with the given prompt and parameters.
		"""
		log.line_break("debug")
		log.debug(f"Waiting for GPT-4.1 call to complete...")
		return_dict, stats = self.call_llm(provider="openai", model_name="gpt-4.1", prompt=gpt_4_1_prompt, max_output_tokens=32768, temperature=0)
		log.debug("GPT-4.1 call returned.")
		#for key, value in return_dict.items():
		#	log.debug(f"{key}: {value}\n")
		log.debug("GPT-4.1 call stats:")
		for key, value in stats.items():
			if key not in ["raw_api_response"]:
				log.debug(f"{key}: {value}\n")
		log.line_break("debug")
		
		return return_dict["llm_response_text"]

	def call_llm(self,
		provider: str,
		model_name: str,
		prompt: str,
		max_output_tokens: Optional[int] = None, # For OpenAI, this is 'max_tokens'
		temperature: float = 0.7,
		force_json: bool = False,
		json_schema: Optional[dict] = None,
		# Add other common parameters like top_p, top_k etc. as needed
		transient_error_retries: int = DEFAULT_MAX_TRANSIENT_ERROR_RETRIES) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
		"""
		Calls the specified LLM with the given prompt and parameters.

		Args:
			provider (str): The provider name (e.g., "openai", "google")
			model_name (str): The model name (e.g., "gpt-4", "gemini-1.5-pro-latest")
			prompt (str): The prompt to call the LLM with.
			max_output_tokens (Optional[int]): The maximum number of tokens to generate.
			temperature (float): The temperature to use for the response.
			force_json (bool): Whether to force the response to be in JSON format.
			json_schema (Optional[dict]): The JSON schema to use for the response (only works with Gemini)
			transient_error_retries (int): The number of transient error retries.
			
		Returns:
			A tuple: (response_data, statistics_dict).
			response_data is a dict like {"llm_response_text": "..."} or None if an error.
			statistics_dict contains metrics about the call.
		"""
		start_time = time.time()
		
		stats: Dict[str, Any] = {
			"provider": provider,
			"model_name": model_name,
			"input_tokens": 0,
			"output_tokens": 0,
			"estimated_input_cost": 0.0,
			"estimated_output_cost": 0.0,
			"total_estimated_cost_dollars": 0.0,
			"api_call_duration_seconds": 0.0,
			"error_message": None,
			"warnings": [],
			"raw_api_response": None # Optionally store raw response for debugging
		}
		if self.last_minute_sent < time.time() - 60:
			self.requests_sent_this_minute = 0
			self.tokens_sent_this_minute = 0
			self.last_minute_sent = time.time()

		# Gemini 2.5 flash pro has a 1000 request per minute limit.
		# Gemini 2.5 flash has a 1000000 token per minute limit.
		if self.requests_sent_this_minute > 950 or self.tokens_sent_this_minute > 1000000: 
			while self.last_minute_sent < time.time() - 60:
				time.sleep(1)
			self.requests_sent_this_minute = 0
			self.tokens_sent_this_minute = 0
			self.last_minute_sent = time.time()
		else:
			self.requests_sent_this_minute += 1
			stats["input_tokens"] = self._count_tokens(prompt, provider, model_name)
			self.tokens_sent_this_minute += stats["input_tokens"]

		try:
			# 1. Get model info and validate
			model_info = self._get_model_info(provider, model_name)
			context_window = model_info["context_window_tokens"]
			# Use provided max_output_tokens, else fallback to model_info, else a default
			effective_max_output_tokens = max_output_tokens if max_output_tokens is not None else model_info.get("output_max_tokens", 2048) # Default if not in model_info

			# 2. Check tokens against context window
			if stats["input_tokens"] >= context_window:
				msg = (f"Input prompt ({stats['input_tokens']} tokens) exceeds model's context window "
					   f"({context_window} tokens) for {provider}/{model_name}.")
				log.error(msg)
				stats["error_message"] = msg
				raise TokenLimitError(msg)

			# Check if input_tokens + max_output_tokens > context_window
			if stats["input_tokens"] + effective_max_output_tokens > context_window:
				# Reduce effective_max_output_tokens to fit
				original_requested_max_output = effective_max_output_tokens
				effective_max_output_tokens = context_window - stats["input_tokens"]
				warning_msg = (f"Requested max_output_tokens ({original_requested_max_output}) plus input tokens ({stats['input_tokens']}) "
							   f"exceeds context window ({context_window}). "
							   f"Adjusting max_output_tokens to {effective_max_output_tokens}.")
				log.warning(warning_msg)
				stats["warnings"].append(warning_msg)
				if effective_max_output_tokens <= 0:
					msg = "Not enough tokens remaining in context window for any output."
					log.error(msg)
					stats["error_message"] = msg
					raise TokenLimitError(msg)


			# 3. Estimate input cost
			stats["estimated_input_cost"] = self._calculate_cost(
				stats["input_tokens"],
				model_info["input_cost_per_1k_tokens"]
			)
			stats["total_estimated_cost_dollars"] += stats["estimated_input_cost"] # Initial total cost

			# 4. API Call with retry logic
			response_content = None
			current_retry = 0
			rate_limit_start_time = None
			backoff_time = INITIAL_BACKOFF_SECONDS

			while True:
				api_call_start_time = time.time()
				try:
					if provider == "openai":
						if not self.openai_client:
							raise APIKeyMissingError("OpenAI client not initialized. Check OPENAI_API_KEY.")
						
						# Construct messages for chat models
						messages = [{"role": "user", "content": prompt}]
						
						openai_api_params = {
							"model": model_name,
							"messages": messages,
							"max_tokens": effective_max_output_tokens,
							"temperature": temperature,
						}
						if force_json:
							openai_api_params["response_format"] = {"type": "json_object"}
							log.debug(f"OpenAI call to {model_name}: JSON mode enabled. Ensure prompt guides JSON output.")

						api_response = self.openai_client.chat.completions.create(**openai_api_params)
						stats["raw_api_response"] = api_response.model_dump_json(indent=2)
						stats["raw_api_response"] = api_response.model_dump_json(indent=2)
						response_content = api_response.choices[0].message.content
						if api_response.usage:
							stats["input_tokens"] = api_response.usage.prompt_tokens # More accurate from API
							stats["output_tokens"] = api_response.usage.completion_tokens
						else: # Fallback if usage is not present (should be rare for chat completions)
							stats["output_tokens"] = self._count_tokens(response_content or "", provider, model_name)

					elif provider == "google":
						if not os.environ.get("GEMINI_API_KEY"): # Check if client was configured
							raise APIKeyMissingError("Google Gemini client not configured. Check GEMINI_API_KEY.")

						sdk_model_name = model_name if model_name.startswith("models/") else f"models/{model_name}"
						model_instance = genai.GenerativeModel(sdk_model_name)
						
						generation_config_params = {
							"max_output_tokens": effective_max_output_tokens,
							"temperature": temperature,
						}

						if force_json:
							generation_config_params["response_mime_type"] = "application/json"
							log.debug(f"Google Gemini call to {model_name}: JSON mode (application/json) enabled.")
							if json_schema:
								generation_config_params["response_schema"] = json_schema
								
						generation_config_obj = genai.types.GenerationConfig(**generation_config_params)
						safety_settings = [
						{
							"category": genai.types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
							"threshold": genai.types.HarmBlockThreshold.BLOCK_NONE # Or BLOCK_NONE
						}]
						api_response = model_instance.generate_content(
							prompt,
							generation_config=generation_config_obj,
							safety_settings=safety_settings
						)
						stats["raw_api_response"] = str(api_response) # Or more structured if possible
						# If the finish reason is 'STOP' and there is no 'text' attribute, return an empty string
						if api_response.candidates[0].finish_reason.value == 1 and not api_response.candidates[0].content.parts:
							log.debug("Returning an empty string because the finish reason is 'STOP' and there is no 'text' attribute.")
							response_content = ""
						else:
							log.debug("Returning the text from the Google Gemini response.")
							response_content = api_response.text
						
						# Get token counts from Google's response
						if hasattr(api_response, 'usage_metadata') and api_response.usage_metadata:
							stats["input_tokens"] = api_response.usage_metadata.prompt_token_count
							stats["output_tokens"] = api_response.usage_metadata.candidates_token_count # Sum of tokens in all candidates
							# If you only care about the first candidate:
							# stats["output_tokens"] = api_response.usage_metadata.candidates[0].token_count (check structure)
						else: # Fallback
							stats["output_tokens"] = self._count_tokens(response_content or "", provider, model_name)
					else:
						raise ValueError(f"Unsupported provider: {provider}")

					stats["api_call_duration_seconds"] = time.time() - api_call_start_time
					break # Successful call

				except openai.RateLimitError as e:
					log.warning(f"OpenAI Rate limit hit for {model_name}: {e}. Retrying...")
					stats["raw_api_response"] = str(e)
					if rate_limit_start_time is None:
						rate_limit_start_time = time.time()
					if time.time() - rate_limit_start_time > MAX_RATE_LIMIT_RETRY_DURATION_SECONDS:
						msg = f"OpenAI Rate limit persisted for over {MAX_RATE_LIMIT_RETRY_DURATION_SECONDS // 60} minutes. Aborting."
						log.error(msg)
						stats["error_message"] = msg
						raise RateLimitExceededError(msg) from e
					time.sleep(backoff_time)
					backoff_time = min(backoff_time * 2, MAX_BACKOFF_SECONDS) # Exponential backoff

				except genai.types.generation_types.BlockedPromptException as e: # Google specific for safety
					msg = f"Google Gemini prompt blocked for safety reasons: {e}"
					log.error(msg)
					stats["error_message"] = msg
					stats["raw_api_response"] = str(e)
					raise ContentGenerationError(msg) from e

				except genai.types.generation_types.StopCandidateException as e: # Google specific for safety
					msg = f"Google Gemini generation stopped, possibly due to safety settings or invalid response: {e}"
					log.error(msg)
					stats["error_message"] = msg
					stats["raw_api_response"] = str(e)
					# This might still have partial content in e.response.text
					# For now, treating as an error preventing full desired output.
					raise ContentGenerationError(msg) from e
				
				except (openai.APIError, openai.APIConnectionError,
						# Add Google specific transient error types here if identifiable
						# e.g., google.api_core.exceptions.ServiceUnavailable, ResourceExhausted
						# For google-genai, common errors are under google.api_core.exceptions
						# For example, google.api_core.exceptions.ResourceExhausted for rate limits
						# google.api_core.exceptions.DeadlineExceeded for timeouts
						Exception) as e: # Catching broader Exception for Google for now
					
					# Specifically handle Google's ResourceExhausted as a rate limit
					is_google_rate_limit = provider == "google" and "ResourceExhausted" in str(type(e)) # Basic check
					
					if is_google_rate_limit:
						log.warning(f"Google Gemini Rate limit (ResourceExhausted) hit for {model_name}: {e}. Retrying...")
						stats["raw_api_response"] = str(e)
						if rate_limit_start_time is None:
							rate_limit_start_time = time.time()
						if time.time() - rate_limit_start_time > MAX_RATE_LIMIT_RETRY_DURATION_SECONDS:
							msg = f"Google Gemini Rate limit persisted for over {MAX_RATE_LIMIT_RETRY_DURATION_SECONDS // 60} minutes. Aborting."
							log.error(msg)
							stats["error_message"] = msg
							raise RateLimitExceededError(msg) from e
						time.sleep(backoff_time)
						backoff_time = min(backoff_time * 2, MAX_BACKOFF_SECONDS)
						continue # Continue to next retry iteration for rate limit

					# For other transient errors
					current_retry += 1
					log.warning(f"API call failed for {provider}/{model_name} (Attempt {current_retry}/{transient_error_retries}): {e}")
					stats["raw_api_response"] = str(e)
					if current_retry >= transient_error_retries:
						msg = f"API call failed after {transient_error_retries} retries for {provider}/{model_name}."
						log.error(msg)
						stats["error_message"] = msg
						raise APICommunicationError(msg) from e
					time.sleep(backoff_time) # Use backoff for other transient errors too
					backoff_time = min(backoff_time * 2, MAX_BACKOFF_SECONDS)


			# 5. Post-flight calculations (output cost)
			# Input tokens might have been updated by API response, recalculate if so.
			stats["estimated_input_cost"] = self._calculate_cost(
				stats["input_tokens"], model_info["input_cost_per_1k_tokens"]
			)
			stats["estimated_output_cost"] = self._calculate_cost(
				stats["output_tokens"], model_info["output_cost_per_1k_tokens"]
			)
			stats["total_estimated_cost_dollars"] = stats["estimated_input_cost"] + stats["estimated_output_cost"]

			response_data = {"llm_response_text": response_content.strip() if response_content else None}
			return response_data, stats

		except (ModelNotFoundError, TokenLimitError, APIKeyMissingError, ContentGenerationError) as e:
			# These are considered non-retryable setup/prompt issues or critical failures.
			log.error(f"LLM call failed: {e}")
			if not stats["error_message"]: # Ensure error_message is set
				stats["error_message"] = str(e)
			stats["api_call_duration_seconds"] = time.time() - start_time # Total time until failure
			return None, stats
		except (RateLimitExceededError, APICommunicationError) as e:
			# These are errors after retries.
			log.error(f"LLM call failed after retries: {e}")
			if not stats["error_message"]:
				stats["error_message"] = str(e)
			stats["api_call_duration_seconds"] = time.time() - start_time
			return None, stats
		except Exception as e:
			# Catch-all for unexpected errors
			log.critical(f"An unexpected error occurred in call_llm: {e}")
			stats["error_message"] = f"Unexpected error: {str(e)}"
			stats["api_call_duration_seconds"] = time.time() - start_time
			return None, stats
		finally:
			if "api_call_duration_seconds" not in stats or stats["api_call_duration_seconds"] == 0.0 and stats["error_message"]:
				 stats["api_call_duration_seconds"] = time.time() - start_time # Ensure duration is set on error

def test(test_plan_path: str) -> dict:
	"""
	Runs tests for this toolbox based on the provided test plan.

	Args:
		test_plan_path (str): The path to the JSON test plan file for this toolbox.

	Returns:
		dict: A dictionary containing the test results.
	"""
	logger.log_info(f"Running tests for toolbox_template using test plan: {test_plan_path}")
	if not os.path.exists(test_plan_path):
		logger.log_error(f"Test plan not found: {test_plan_path}")
		return {"error": "Test plan not found", "passed": 0, "failed": 0, "coverage": 0}
		
	test_tb = TestToolBox(test_plan_path)
	results = test_tb.execute_test_plan()
	logger.log_info(f"Test results: {results}")
	return results

def main():
	"""
	Main execution function for the toolbox template.
	Primarily for demonstration or direct testing of toolbox methods.
	"""
	parser = argparse.ArgumentParser(description="Toolbox Template script.")
	parser.add_argument("--data", default="sample_data", help="Data for the action.")
	parser.add_argument("--run-tests", nargs='?', const="TOOLBOXES/tests/toolbox_template_test/test_plan.json", # Adjust path
						help="Run self-tests. Optionally provide a path to a specific test plan.")


	args = parser.parse_args()
	logger.log_info("Toolbox_template.py main() started.")

	if args.run_tests:
		test_results = test(args.run_tests)
		logger.log_info("Test Results:")
		for key, value in test_results.items():
			logger.log_info(f"	{key}: {value}")
		logger.log_info(f"Test run completed with results: {test_results}")
	else:
		# Instantiate the toolbox
		my_toolbox = TypeToolbox(custom_setting="main_setting")

		logger.log_info(f"Processing data '{args.data}' with TypeToolbox...")
		output = my_toolbox.example_method(args.data)
		logger.log_info(f"Processing output: {output}")
		logger.log_info(f"Process action completed. Output: '{output}'")

	logger.log_info("Toolbox_template.py main() finished.")

if __name__ == "__main__":
	main()