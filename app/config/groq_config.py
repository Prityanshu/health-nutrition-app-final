"""
Groq API Configuration with Fallback Support
Handles multiple API keys with automatic failover
"""

import os
import logging
from typing import List, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

@dataclass
class GroqAPIKey:
    """Represents a Groq API key with metadata"""
    key: str
    name: str
    is_active: bool = True
    usage_count: int = 0
    last_used: Optional[str] = None
    error_count: int = 0

class GroqConfigManager:
    """Manages multiple Groq API keys with automatic failover"""
    
    def __init__(self):
        self.api_keys: List[GroqAPIKey] = []
        self.current_key_index = 0
        self.max_errors_per_key = 3  # Switch key after 3 consecutive errors
        self._load_api_keys()
    
    def _load_api_keys(self):
        """Load API keys from environment variables"""
        # Primary API key
        primary_key = os.getenv('GROQ_API_KEY')
        if primary_key:
            self.api_keys.append(GroqAPIKey(
                key=primary_key,
                name="primary",
                is_active=True
            ))
            logger.info("Loaded primary Groq API key")
        
        # Secondary API key
        secondary_key = os.getenv('GROQ_API_KEY_2')
        if secondary_key:
            self.api_keys.append(GroqAPIKey(
                key=secondary_key,
                name="secondary",
                is_active=True
            ))
            logger.info("Loaded secondary Groq API key")
        
        # Tertiary API key (if available)
        tertiary_key = os.getenv('GROQ_API_KEY_3')
        if tertiary_key:
            self.api_keys.append(GroqAPIKey(
                key=tertiary_key,
                name="tertiary",
                is_active=True
            ))
            logger.info("Loaded tertiary Groq API key")
        
        if not self.api_keys:
            logger.warning("No Groq API keys found in environment variables")
        else:
            logger.info(f"Loaded {len(self.api_keys)} Groq API keys")
    
    def get_current_api_key(self) -> Optional[str]:
        """Get the current active API key"""
        if not self.api_keys:
            return None
        
        # Find the first active key starting from current index
        for i in range(len(self.api_keys)):
            key_index = (self.current_key_index + i) % len(self.api_keys)
            api_key = self.api_keys[key_index]
            
            if api_key.is_active and api_key.error_count < self.max_errors_per_key:
                return api_key.key
        
        # If no active keys found, reset all error counts and try again
        logger.warning("All API keys have exceeded error limit, resetting error counts")
        for api_key in self.api_keys:
            api_key.error_count = 0
            api_key.is_active = True
        
        # Return the first key
        return self.api_keys[0].key if self.api_keys else None
    
    def mark_key_error(self, error_type: str = "general"):
        """Mark the current key as having an error"""
        if not self.api_keys:
            return
        
        current_key = self.api_keys[self.current_key_index]
        current_key.error_count += 1
        
        logger.warning(f"API key '{current_key.name}' error count: {current_key.error_count}/{self.max_errors_per_key}")
        
        # If this key has too many errors, switch to next key
        if current_key.error_count >= self.max_errors_per_key:
            current_key.is_active = False
            logger.error(f"API key '{current_key.name}' disabled due to too many errors")
            self._switch_to_next_key()
    
    def mark_key_success(self):
        """Mark the current key as successful (reset error count)"""
        if not self.api_keys:
            return
        
        current_key = self.api_keys[self.current_key_index]
        current_key.error_count = 0
        current_key.usage_count += 1
        current_key.is_active = True
    
    def _switch_to_next_key(self):
        """Switch to the next available API key"""
        if not self.api_keys:
            return
        
        original_index = self.current_key_index
        
        # Find next active key
        for i in range(1, len(self.api_keys) + 1):
            next_index = (self.current_key_index + i) % len(self.api_keys)
            api_key = self.api_keys[next_index]
            
            if api_key.is_active and api_key.error_count < self.max_errors_per_key:
                self.current_key_index = next_index
                logger.info(f"Switched to API key '{api_key.name}' (index {next_index})")
                return
        
        # If no active keys found, reset and use first key
        logger.warning("No active API keys found, resetting all keys")
        for api_key in self.api_keys:
            api_key.error_count = 0
            api_key.is_active = True
        
        self.current_key_index = 0
        logger.info(f"Reset all keys, using '{self.api_keys[0].name}'")
    
    def get_status(self) -> dict:
        """Get the current status of all API keys"""
        return {
            "total_keys": len(self.api_keys),
            "active_keys": len([k for k in self.api_keys if k.is_active]),
            "current_key_index": self.current_key_index,
            "current_key_name": self.api_keys[self.current_key_index].name if self.api_keys else None,
            "keys": [
                {
                    "name": key.name,
                    "is_active": key.is_active,
                    "error_count": key.error_count,
                    "usage_count": key.usage_count,
                    "last_used": key.last_used
                }
                for key in self.api_keys
            ]
        }
    
    def reset_all_keys(self):
        """Reset all API keys (useful for testing or manual reset)"""
        for api_key in self.api_keys:
            api_key.error_count = 0
            api_key.is_active = True
        self.current_key_index = 0
        logger.info("Reset all API keys")

# Global instance
groq_config = GroqConfigManager()

def get_groq_api_key() -> Optional[str]:
    """Get the current Groq API key with fallback support"""
    return groq_config.get_current_api_key()

def handle_groq_error(error: Exception):
    """Handle a Groq API error and switch keys if necessary"""
    error_msg = str(error).lower()
    
    # Check for rate limit or quota exceeded errors
    if any(phrase in error_msg for phrase in [
        "rate_limit_exceeded", 
        "rate limit", 
        "quota exceeded", 
        "too many requests",
        "high usage",
        "429"
    ]):
        logger.warning(f"Rate limit detected: {error}")
        groq_config.mark_key_error("rate_limit")
    else:
        logger.warning(f"API error detected: {error}")
        groq_config.mark_key_error("general")

def mark_groq_success():
    """Mark the current API key as successful"""
    groq_config.mark_key_success()
