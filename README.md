# Autodidact - AI-Powered Learning Assistant

Note: I have a bunch of kinks I need to iron out with this project (I'll do them over the next few days), but the main structure is mostly done

Here is a quick video overview of the project: 
https://github.com/baibhavbista/autodidact-agent


Autodidact is an AI-powered personalized learning assistant that creates custom study plans, provides interactive tutoring sessions, and tracks your learning progress.

## Features

- 🔍 **Deep Research**: AI investigates your topic and creates comprehensive study plans
- 📊 **Knowledge Graphs**: Visual representation of concepts and their prerequisites
- 👨‍🏫 **AI Tutoring**: Personalized 30-minute learning sessions with an AI tutor
- 📈 **Progress Tracking**: Monitor your mastery of each concept over time
- 🔄 **Session Recovery**: Resume interrupted learning sessions

## Installation


### Option 1: Docker (Recommended)

The easiest way to run Autodidact is using Docker:

1. Clone the repository:
```bash
git clone https://github.com/yourusername/autodidact.git
cd autodidact
```

2. Build the Docker image locally (since it is not published on Docker Hub):
```bash
docker build -t autodidact-agent .
```

3. Run with Docker Compose:
```bash
docker compose up
```

The application will be available at http://localhost:8501

**Note**: Your data (database, configuration, projects) will be persisted in a Docker volume called `autodidact_data`, so it will be preserved across container restarts.

### Option 2: Local Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/autodidact.git
cd autodidact
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Run the application:
```bash
streamlit run app.py
```

## Setup

On first run, you'll need to choose an AI provider and provide your API key. The app supports:

- **OpenAI**: Full features including deep research with web search
- **OpenRouter**: Access to multiple models (Claude, Gemini, etc.) without deep research

The app will guide you through the setup process and store your configuration securely at `~/.autodidact/.env.json`.

## Database Schema

The application uses SQLite with the following schema:

- **project**: Learning projects with topics and metadata
- **node**: Knowledge graph nodes (concepts to learn)
- **edge**: Relationships between concepts
- **learning_objective**: Specific objectives for each concept
- **session**: Learning sessions linking projects and nodes
- **transcript**: Conversation history for each session

### Database Migration

If you're upgrading from an earlier version, run the migration script:

```bash
python backend/migrate_db.py
```

This will update your database schema to include the new session tracking features.

## AI Provider Options

Autodidact supports multiple AI providers to give you flexibility in model choice and cost. You can configure multiple providers and switch between them seamlessly.

### Provider Comparison

| Feature | OpenAI | OpenRouter |
|---------|---------|------------|
| **Deep Research** | ✅ o4-mini-deep-research | ❌ (uses Claude Sonnet) |
| **Web Search** | ✅ Built-in | ❌ |
| **Chat Models** | GPT-4o-mini | Claude 3.5 Sonnet/Haiku, Gemini |
| **Cost Range** | $0.50-2.00 (research), $0.02-0.05 (chat) | $0.001-0.05 per request |
| **Best For** | Comprehensive research projects | High-quality conversations, cost optimization |

### OpenAI Provider
- **Features**: Full deep research with web search capabilities
- **Models**: 
  - `o4-mini-deep-research-2025-06-26` for comprehensive research
  - `gpt-4o-mini` for interactive tutoring sessions
- **Setup**: Get API key from [OpenAI Platform](https://platform.openai.com/api-keys)
- **API Key Format**: Starts with `sk-`
- **Best for**: Users who need comprehensive research with real-time web data

### OpenRouter Provider
- **Features**: Access to Claude, Gemini, and other top models from multiple providers
- **Models**:
  - `anthropic/claude-3.5-sonnet` for complex reasoning (fallback for research)
  - `anthropic/claude-3.5-haiku` for fast, cost-effective conversations
  - Many other models available (Gemini, GPT variants, etc.)
- **Setup**: Get API key from [OpenRouter](https://openrouter.ai/keys)
- **API Key Format**: Starts with `sk-or-`
- **Best for**: Users who want model diversity, potentially lower costs, or prefer Claude/Gemini

### Provider Setup Examples

#### Initial Setup (New Users)
When you first run Autodidact, you'll see a provider selection dialog:

1. **Choose OpenAI** for comprehensive research capabilities
2. **Choose OpenRouter** for model diversity and cost optimization
3. Enter your API key when prompted
4. The app validates your key and saves the configuration

#### Adding Multiple Providers
You can configure multiple providers and switch between them:

```bash
# Your config will be stored at ~/.autodidact/.env.json
{
  "provider": "openai",
  "openai_api_key": "sk-your-openai-key",
  "openrouter_api_key": "sk-or-your-openrouter-key"
}
```

#### Switching Providers
You can change providers anytime through the Settings page:
1. Go to **Settings** in the sidebar
2. Select your preferred provider
3. Configure API keys for any new providers
4. Changes take effect immediately

### Programming Examples

The provider system is designed to work seamlessly in code:

#### Basic Usage
```python
from utils.providers import create_client, get_model_for_task

# Works with your currently configured provider
client = create_client()
model = get_model_for_task("chat")

# Make API calls (same interface regardless of provider)
response = client.chat.completions.create(
    model=model,
    messages=[{"role": "user", "content": "Explain quantum physics"}]
)
```

#### Provider-Specific Operations
```python
from utils.providers import create_client, get_model_for_task, get_provider_info
from utils.config import get_current_provider, set_current_provider

# Check current provider capabilities
current = get_current_provider()
info = get_provider_info(current)

if info.get("supports_deep_research"):
    # Use deep research model
    model = get_model_for_task("deep_research")
    print(f"Using {model} for comprehensive research")
else:
    # Fall back to chat model for research-style queries
    model = get_model_for_task("chat")
    print(f"Using {model} for research (no deep research available)")

# Switch providers programmatically
set_current_provider("openrouter")  # Switch to OpenRouter
set_current_provider("openai")      # Switch back to OpenAI
```

#### Multi-Provider Workflows
```python
from utils.providers import create_client
from utils.config import set_current_provider

# Use OpenAI for research phase
set_current_provider("openai")
research_client = create_client()
research_response = research_client.chat.completions.create(
    model="o4-mini-deep-research-2025-06-26",
    messages=[{"role": "user", "content": "Research latest developments in AI"}]
)

# Switch to OpenRouter for tutoring (potentially lower cost)
set_current_provider("openrouter") 
tutor_client = create_client()
tutor_response = tutor_client.chat.completions.create(
    model="anthropic/claude-3.5-haiku",
    messages=[{"role": "user", "content": "Explain this research in simple terms"}]
)
```

### Usage Recommendations

#### For Beginners
- **Start with OpenAI** if you want the full feature set including deep research
- **Start with OpenRouter** if you prefer Claude/Gemini models or want lower costs

#### For Cost Optimization
- **Research Phase**: Use OpenAI for comprehensive research with web search
- **Learning Phase**: Switch to OpenRouter for interactive tutoring sessions
- **Monitor usage** in your provider dashboards to track costs

#### For Model Experimentation
- Configure both providers to access different model families
- **OpenAI**: Access to latest GPT models and deep research
- **OpenRouter**: Access to Claude, Gemini, and many other models

### Troubleshooting

#### Common Issues
1. **API Key Invalid**: Ensure key format matches provider (sk- vs sk-or-)
2. **Provider Switch Failed**: Check that API keys are configured for target provider
3. **Model Not Available**: Some models may not be available in your region

#### Getting Help
- Check your API key format matches the provider requirements
- Verify your account has credits/billing set up with the provider
- See the [OpenRouter Guide](OPENROUTER_GUIDE.md) for detailed OpenRouter setup

You can configure multiple providers and switch between them anytime in Settings.

## Quick Start Guide

### New Users - Choose Your Provider

1. **For comprehensive research with web search**: Choose **OpenAI**
   ```bash
   # Get API key from https://platform.openai.com/api-keys
   # Format: sk-...
   ```

2. **For model diversity and cost optimization**: Choose **OpenRouter**
   ```bash
   # Get API key from https://openrouter.ai/keys  
   # Format: sk-or-...
   ```

3. **Run the application**:
   ```bash
   streamlit run app.py
   ```

4. **Follow the setup wizard** to configure your chosen provider

### Existing Users - Add More Providers

1. Go to **Settings** in the sidebar
2. Click **"Configure Additional Provider"**
3. Enter API key for new provider
4. Switch between providers anytime

## Usage

1. **Start a New Project**: Enter a topic you want to learn
2. **Review the Plan**: Examine the generated knowledge graph and report
3. **Begin Learning**: Start tutoring sessions for available topics
4. **Track Progress**: Monitor your mastery levels across concepts

## Project Structure

```
autodidact/
├── app.py                 # Main Streamlit application
├── backend/
│   ├── db.py             # Database operations
│   ├── jobs.py           # AI job processing
│   ├── graph.py          # LangGraph tutor implementation
│   ├── deep_research.py  # Deep research module
│   └── migrate_db.py     # Database migration script
├── components/
│   └── graph_viz.py      # Graph visualization
├── utils/
│   ├── config.py         # Configuration management
│   ├── providers.py      # AI provider abstraction layer
│   └── deep_research.py  # Deep research utilities
├── OPENROUTER_GUIDE.md   # Detailed OpenRouter setup guide
└── requirements.txt      # Python dependencies
```

## Development

To contribute or modify Autodidact:

1. Follow the installation steps above
2. Make your changes
3. Test thoroughly with various topics
4. Submit a pull request

## Requirements

- Python 3.8+
- API key from a supported provider:
  - **OpenAI**: For full deep research capabilities ([Get API Key](https://platform.openai.com/api-keys))
  - **OpenRouter**: For access to multiple AI models ([Get API Key](https://openrouter.ai/keys))

## Documentation

- **[OpenRouter Setup Guide](OPENROUTER_GUIDE.md)**: Detailed setup instructions for OpenRouter
- **[Architecture Guide](ARCHITECTURE.md)**: Technical details about the provider system

## License

MIT License - see LICENSE file for details
