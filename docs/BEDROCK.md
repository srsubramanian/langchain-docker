# AWS Bedrock Integration

This document covers AWS Bedrock-specific configuration and behavior in the LangChain Docker application.

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# AWS Region for Bedrock (optional, defaults to us-east-1)
AWS_DEFAULT_REGION=us-east-1

# Bedrock Model ARNs (comma-separated list)
# Use inference profile ARNs or foundation model ARNs
BEDROCK_MODEL_ARNS=anthropic.claude-3-5-sonnet-20241022-v2:0,anthropic.claude-3-5-haiku-20241022-v1:0

# AWS Profile (optional)
# Use a specific AWS profile from ~/.aws/credentials or ~/.aws/config
AWS_PROFILE=default

# AWS Credentials (optional if using AWS CLI, profile, or IAM role)
# Only needed if not using 'aws configure', profile, or IAM role
# AWS_ACCESS_KEY_ID=your-access-key
# AWS_SECRET_ACCESS_KEY=your-secret-key
```

### Authentication Methods

Bedrock supports multiple authentication methods (in order of precedence):

1. **Environment Variables**: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`
2. **AWS Profile**: Set `AWS_PROFILE` to use a specific profile from `~/.aws/credentials`
3. **SSO Login**: Run `aws sso login --profile your-profile` and set `AWS_PROFILE`
4. **IAM Role**: When running on AWS infrastructure (EC2, ECS, Lambda)
5. **AWS CLI**: Run `aws configure` to set up default credentials

### Model Configuration

Bedrock models can be specified as:

- **Model ID**: `anthropic.claude-3-5-sonnet-20241022-v2:0`
- **Foundation Model ARN**: `arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20241022-v2:0`
- **Inference Profile ARN**: For cross-region inference

## Streaming Behavior

### Key Difference from Other Providers

Unlike OpenAI and Anthropic APIs, **AWS Bedrock's ChatBedrockConverse does not always emit streaming token events** (`on_chat_model_stream`). Instead, it may only emit a single `on_chat_model_end` event with the complete response.

This affects how responses are captured in the application:

| Provider | Streaming Events | Fallback Event |
|----------|-----------------|----------------|
| OpenAI | `on_chat_model_stream` (multiple) | `on_chat_model_end` |
| Anthropic | `on_chat_model_stream` (multiple) | `on_chat_model_end` |
| Google | `on_chat_model_stream` (multiple) | `on_chat_model_end` |
| **Bedrock** | May not emit | **`on_chat_model_end` (required)** |

### Implementation Details

The application handles this by:

1. **Primary**: Capturing streaming tokens from `on_chat_model_stream` events
2. **Fallback**: Capturing complete response from `on_chat_model_end` events

```python
# Streaming tokens (works for OpenAI, Anthropic, Google)
elif kind == "on_chat_model_stream":
    chunk = data.get("chunk")
    if chunk and hasattr(chunk, 'content') and chunk.content:
        content = chunk.content
        if isinstance(content, str):
            accumulated_content += content
            yield {"event": "token", "data": json.dumps({"content": content})}

# Fallback for non-streaming models (required for Bedrock)
elif kind == "on_chat_model_end":
    output = data.get("output")
    if output and hasattr(output, 'content'):
        content = output.content
        # Only yield if not already captured via streaming
        if content not in accumulated_content:
            accumulated_content += content
            yield {"event": "token", "data": json.dumps({"content": content})}
```

### Tool Calling with Bedrock

When using tools/skills with Bedrock, there are multiple LLM calls:

1. **First call**: LLM decides to use tools (e.g., "Let me load the SQL skill...")
2. **Tool execution**: Tools run and return results
3. **Second call**: LLM processes tool results and generates final response

For each LLM call, the `on_chat_model_end` fallback captures the response, ensuring all parts of the conversation are displayed.

## Supported Models

Common Bedrock models for Claude:

| Model | ID | Description |
|-------|-----|-------------|
| Claude 3.5 Sonnet v2 | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Balanced performance |
| Claude 3.5 Haiku | `anthropic.claude-3-5-haiku-20241022-v1:0` | Fast and efficient |
| Claude 3 Opus | `anthropic.claude-3-opus-20240229-v1:0` | Most capable |
| Claude 3 Sonnet | `anthropic.claude-3-sonnet-20240229-v1:0` | Balanced |
| Claude 3 Haiku | `anthropic.claude-3-haiku-20240307-v1:0` | Fastest |

## Troubleshooting

### Empty Responses

If you see empty chat bubbles with Bedrock:

1. **Check Phoenix traces**: If Phoenix shows a valid response, the issue is in event capture
2. **Verify streaming events**: Check backend logs for `[Stream Event]` entries
3. **Look for `on_chat_model_end`**: Bedrock responses come from this event, not streaming

### Authentication Errors

```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**Solutions**:
- Run `aws configure` to set up credentials
- Set `AWS_PROFILE` to use a specific profile
- For SSO: Run `aws sso login --profile your-profile`
- Verify IAM permissions include `bedrock:InvokeModel`

### Model Access Errors

```
AccessDeniedException: You don't have access to the model
```

**Solutions**:
- Enable model access in AWS Console → Bedrock → Model access
- Verify the model is available in your region
- Check IAM policy includes the specific model ARN

### Region Issues

```
Could not connect to the endpoint URL
```

**Solutions**:
- Verify `AWS_DEFAULT_REGION` is set to a region with Bedrock
- Check model availability in your region
- Bedrock is not available in all AWS regions

## Docker Configuration

When running in Docker, pass AWS credentials:

```yaml
# docker-compose.yml
services:
  api:
    environment:
      - AWS_DEFAULT_REGION=us-east-1
      - AWS_PROFILE=default
      # Or use explicit credentials (less secure)
      # - AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}
      # - AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}
    volumes:
      # Mount AWS credentials for profile-based auth
      - ~/.aws:/root/.aws:ro
```

## Performance Considerations

1. **Latency**: Bedrock may have higher latency than direct API calls due to AWS infrastructure
2. **No streaming**: Responses appear all at once rather than streaming token-by-token
3. **Region proximity**: Use a Bedrock region close to your deployment for lower latency
4. **Connection pooling**: The application caches Bedrock clients to reduce connection overhead
