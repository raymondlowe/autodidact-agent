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

Autodidact supports multiple AI providers to give you flexibility in model choice and cost:

### OpenAI
- **Features**: Full deep research with web search, GPT models
- **Best for**: Comprehensive learning plans with real-time research
- **Models**: GPT-4o-mini (chat), o4-mini-deep-research (research)
- **Cost**: ~$0.50-2.00 per research session, $0.02-0.05 per tutoring session

### OpenRouter  
- **Features**: Access to Claude, Gemini, and other top models
- **Best for**: High-quality conversations with diverse model options
- **Models**: Claude 3.5 Sonnet/Haiku, Gemini, and many others
- **Cost**: Varies by model, typically $0.001-0.05 per request
- **Note**: Uses regular chat completion instead of deep research mode

You can switch providers anytime in Settings and configure API keys for multiple providers.

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
└── utils/
    └── config.py         # Configuration management
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
  - **OpenAI**: For full deep research capabilities
  - **OpenRouter**: For access to multiple AI models (Claude, Gemini, etc.)

## License

MIT License - see LICENSE file for details
