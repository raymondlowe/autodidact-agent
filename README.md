Autodidact 🧠

Autodidact is an open-source AI-powered learning assistant built for autodidacts—people who love to learn independently. The app helps you break down complex topics or books into a structured, auditable, and personalized learning journey.

Autodidact supports two modes:
- 🔍 Partially Autonomous Mode: Upload a textbook or PDF, and Autodidact will extract its structure, build a prerequisite-based knowledge graph, and generate 30-minute learning sessions to guide you through the material.
- 🤖 Agentic Mode: Just tell Autodidact what you want to learn (e.g., “Bitcoin and Ethereum”), and it will ask clarifying questions, build a custom knowledge graph, gather resources, and plan a learning path—all powered by AI.

The system emphasizes transparency and user control, allowing you to toggle AI involvement up or down and audit your learning journey via the generated knowledge graph. Think of it as a blend of personal tutor, research assistant, and interactive syllabus—all in one.


# Some notes

`python3 -m venv .venv`
`source .venv/bin/activate`
`pip install -r requirements.txt`

`python 02-topic-then-deep-research.py 'Foundations of Statistical Learning'`

also have to first apply the openAI api key to the environment variable OPENAI_API_KEY. Note that to use such a thinking model, your organization needs to be verified. You can apply for verification [here]( https://platform.openai.com/settings/organization/general).