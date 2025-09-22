# Groq API Key Fallback Setup

This application now supports multiple Groq API keys with automatic fallback when one key reaches its rate limit.

## Setup Instructions

### 1. Get Multiple Groq API Keys

1. Go to [Groq Console](https://console.groq.com/)
2. Log in to your account
3. Navigate to "API Keys" section
4. Create multiple API keys (recommended: 2-3 keys)

### 2. Configure Environment Variables

Create a `.env` file in your project root with the following variables:

```bash
# Primary API key (required)
GROQ_API_KEY=your-primary-groq-api-key-here

# Secondary API key (optional - for fallback)
GROQ_API_KEY_2=your-secondary-groq-api-key-here

# Tertiary API key (optional - for additional fallback)
GROQ_API_KEY_3=your-tertiary-groq-api-key-here
```

### 3. How It Works

The system automatically:
- Uses the primary API key by default
- Switches to the next available key when rate limits are hit
- Tracks error counts for each key
- Temporarily disables keys with too many errors
- Resets error counts periodically

### 4. Monitoring API Key Status

You can check the status of your API keys by calling:

```python
from app.config.groq_config import groq_config

# Get current status
status = groq_config.get_status()
print(status)
```

### 5. Manual Key Reset

If you need to reset all keys (useful for testing):

```python
from app.config.groq_config import groq_config

# Reset all keys
groq_config.reset_all_keys()
```

## Benefits

- **High Availability**: Service continues even when one key is exhausted
- **Load Distribution**: Spreads usage across multiple keys
- **Automatic Recovery**: Keys are re-enabled after cooldown period
- **Transparent Operation**: No code changes needed in your services

## Error Handling

The system automatically handles:
- Rate limit exceeded errors
- Quota exceeded errors
- Invalid API key errors
- Network timeouts
- Service unavailable errors

## Best Practices

1. **Monitor Usage**: Keep track of your API usage across all keys
2. **Rotate Keys**: Periodically rotate your API keys for security
3. **Set Alerts**: Monitor when keys are being switched
4. **Test Fallback**: Verify that fallback works in your environment

## Troubleshooting

### No API Keys Available
- Ensure at least `GROQ_API_KEY` is set in your environment
- Check that the API keys are valid and active

### All Keys Exhausted
- Wait for rate limits to reset (usually 1 hour)
- Consider getting additional API keys
- Check your usage patterns and optimize if needed

### Keys Not Switching
- Check the error logs for specific error messages
- Verify that the error detection patterns are working
- Manually reset keys if needed
