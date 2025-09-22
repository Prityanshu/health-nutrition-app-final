"""
Custom Groq model with API key fallback support
"""

import logging
from typing import Optional, Any, Dict
from agno.models.groq import Groq
from app.config.groq_config import groq_config, handle_groq_error, mark_groq_success

logger = logging.getLogger(__name__)

class GroqWithFallback:
    """Groq model wrapper with automatic API key fallback"""
    
    def __init__(self, id: str = "llama-3.3-70b-versatile", **kwargs):
        self.model_id = id
        self.kwargs = kwargs
        self._current_model = None
        self._initialize_model()
    
    def _initialize_model(self):
        """Initialize the Groq model with the current API key"""
        api_key = groq_config.get_current_api_key()
        if not api_key:
            raise ValueError("No Groq API keys available")
        
        # Set the API key in environment for the Groq model
        import os
        os.environ['GROQ_API_KEY'] = api_key
        
        try:
            self._current_model = Groq(id=self.model_id, **self.kwargs)
            logger.info(f"Initialized Groq model with API key: {groq_config.api_keys[groq_config.current_key_index].name}")
        except Exception as e:
            logger.error(f"Failed to initialize Groq model: {e}")
            handle_groq_error(e)
            raise
    
    def _reinitialize_if_needed(self):
        """Reinitialize the model if the API key has changed"""
        current_api_key = groq_config.get_current_api_key()
        if not current_api_key:
            raise ValueError("No active Groq API keys available")
        
        # Check if we need to reinitialize
        import os
        if os.environ.get('GROQ_API_KEY') != current_api_key:
            os.environ['GROQ_API_KEY'] = current_api_key
            self._current_model = Groq(id=self.model_id, **self.kwargs)
            logger.info(f"Reinitialized Groq model with new API key: {groq_config.api_keys[groq_config.current_key_index].name}")
    
    def run(self, *args, **kwargs) -> Any:
        """Run the model with automatic fallback on errors"""
        max_retries = len(groq_config.api_keys)  # Try each key once
        last_error = None
        
        for attempt in range(max_retries):
            try:
                # Ensure we're using the current API key
                self._reinitialize_if_needed()
                
                # Run the model
                result = self._current_model.run(*args, **kwargs)
                
                # Mark success if we get here
                mark_groq_success()
                return result
                
            except Exception as e:
                last_error = e
                error_msg = str(e).lower()
                
                # Check if this is a rate limit or API key error
                if any(phrase in error_msg for phrase in [
                    "rate_limit_exceeded", 
                    "rate limit", 
                    "quota exceeded", 
                    "too many requests",
                    "high usage",
                    "429",
                    "unauthorized",
                    "invalid api key",
                    "api key"
                ]):
                    logger.warning(f"API error on attempt {attempt + 1}: {e}")
                    handle_groq_error(e)
                    
                    # If we have more keys to try, continue
                    if attempt < max_retries - 1:
                        logger.info(f"Retrying with next API key...")
                        continue
                else:
                    # For non-API errors, don't retry
                    logger.error(f"Non-API error: {e}")
                    raise e
        
        # If we get here, all keys failed
        logger.error(f"All API keys failed. Last error: {last_error}")
        raise last_error
    
    def __getattr__(self, name):
        """Delegate other attributes to the underlying model"""
        if self._current_model is None:
            self._reinitialize_if_needed()
        return getattr(self._current_model, name)
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current status of API keys"""
        return groq_config.get_status()
    
    def reset_keys(self):
        """Reset all API keys (useful for testing)"""
        groq_config.reset_all_keys()
        self._initialize_model()
