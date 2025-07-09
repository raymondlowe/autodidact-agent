from openai import OpenAI
import os

openai_api_key = os.environ.get("OPENAI_API_KEY")
if not openai_api_key:
  raise ValueError("OPENAI_API_KEY environment variable is not set")

client = OpenAI(api_key=openai_api_key)

clarification_prompt = '''
You are an intelligent assistant preparing to conduct a deep research report. Before proceeding, ask the user any clarifying questions necessary to fully understand the topic they want researched. If you have multiple questions, ask them in a numbered list.

Examples of good clarifying questions include:
- “What aspect of X are you most interested in?”
- “Should the research focus on technical mechanisms, social impacts, or both?”
- “What is your current level of familiarity with the topic?”

Once the topic is clear, you will summarize it in 1-2 sentences and indicate that you are ready to proceed with deep research.
'''

user_first_request = "I want to learn about Modern World History."

messages = [
        {"role": "system", "content": clarification_prompt},
        {"role": "user", "content": user_first_request}
    ]

response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages
)

follow_up_questions = response.choices[0].message.content
print(follow_up_questions)

messages.append({"role": "assistant", "content": follow_up_questions})

# fetch a text response from the user and use it to create a polished prompt to pass to deep research
print("\n" + "="*50 + "\n")
user_response = input("Please enter your responses to the questions above:\n")

messages.append({"role": "user", "content": user_response + "\n\nNow using the above information, please update the user's first request to be a more specific and detailed request for the next step - 'deep research'. Start with 'Research the topic of' and then use the user's response to create a more specific and detailed request."})

polished_prompt_response = client.chat.completions.create(
    model="gpt-4o",
    messages=messages
)

polished_prompt = polished_prompt_response.choices[0].message.content

print("\n" + "="*50 + "\n")
print("Polished Research Prompt:")
print(polished_prompt)

# This polished prompt can now be passed to the deep research API
# For example, if using OpenAI's assistants API for deep research:
# thread = client.beta.threads.create()
# message = client.beta.threads.messages.create(
#     thread_id=thread.id,
#     role="user",
#     content=polished_prompt
# )
