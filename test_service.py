from src.services.groq_service import ask_groq


messages = [
    {
        "role": "user",
        "content": "Say hello to Vijayvargiya Clinic in one sentence."
    }
]


response = ask_groq(messages)


print()
print("=" * 50)
print("SERVICE RESPONSE")
print("=" * 50)
print(response)
print("=" * 50)