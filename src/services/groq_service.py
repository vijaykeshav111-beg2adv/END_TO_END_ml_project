import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()


GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY"
)


if not GROQ_API_KEY:

    raise RuntimeError(
        "GROQ_API_KEY not found in .env"
    )


MODEL_NAME = "openai/gpt-oss-120b"


client = Groq(
    api_key=GROQ_API_KEY
)


def ask_groq(
    messages: list[dict],
) -> str:

    try:

        response = client.chat.completions.create(

            model=MODEL_NAME,

            messages=messages,

            temperature=0.3,

            max_tokens=1000,
        )

        return (
            response
            .choices[0]
            .message
            .content
            .strip()
        )

    except Exception as exc:

        print(
            "Groq API error:",
            repr(exc)
        )

        raise