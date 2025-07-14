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

On first run, you'll need to provide your OpenAI API key. The app will guide you through this process and store your key securely at `~/.autodidact/.env.json`.

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
- OpenAI API key

## License

MIT License - see LICENSE file for details
