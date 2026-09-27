import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()


api_key = os.getenv("GROQ_API_KEY")

print(
    "GROQ KEY FOUND:",
    bool(api_key)
)

if not api_key:
    raise RuntimeError(
        "GROQ_API_KEY not found in .env"
    )


client = Groq(
    api_key=api_key
)


response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {
            "role": "user",
            "content": (
                "Say hello to Vijayvargiya Clinic "
                "in one sentence."
            )
        }
    ],
)


print()
print("==============================")
print("GROQ RESPONSE")
print("==============================")

print(
    response.choices[0].message.content
)