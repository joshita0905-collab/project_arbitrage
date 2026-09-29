import os

from dotenv import load_dotenv
from groq import Groq
from hindsight_client import Hindsight

load_dotenv()


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    cleaned = value.strip()
    placeholders = {
        "",
        "your_groq_key",
        "your_hindsight_key",
        "placeholder",
        "changeme",
        "<your_groq_key>",
        "<your_hindsight_key>",
        "your_api_key",
        "your_key_here",
    }
    return cleaned.lower() in placeholders or not cleaned


print("Checking configuration...\n")

groq_key = os.getenv("GROQ_API_KEY")
hindsight_key = os.getenv("HINDSIGHT_API_KEY")

groq_status = "missing" if is_placeholder(groq_key) else "configured"
hindsight_status = "missing" if is_placeholder(hindsight_key) else "configured"

print(f"Groq status: {groq_status}")
print(f"Hindsight status: {hindsight_status}")

if is_placeholder(groq_key):
    print("Groq: No valid API key configured. Skipping Groq API test.")
else:
    print("Testing Groq...")
    try:
        groq = Groq(api_key=groq_key)
        response = groq.chat.completions.create(
            model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"),
            messages=[
                {
                    "role": "system",
                    "content": "You are Project Arbitrage, a corporate treasury risk analysis AI.",
                },
                {
                    "role": "user",
                    "content": "Say hello and explain your role in one sentence.",
                },
            ],
            temperature=0.1,
        )
        content = response.choices[0].message.content
        print("Groq OK: response received.")
        print(f"Groq sample: {content[:120] if content else '<empty response>'}")
    except Exception as exc:
        print(f"Groq FAILED: {type(exc).__name__}: {exc}")

if is_placeholder(hindsight_key):
    print("Hindsight: No valid API key configured. Skipping Hindsight API test.")
else:
    print("\nTesting Hindsight...")
    try:
        hindsight = Hindsight(
            base_url=os.getenv("HINDSIGHT_API_URL", "https://api.hindsight.vectorize.io"),
            api_key=hindsight_key,
        )
        bank = hindsight.create_bank(
            bank_id=os.getenv("HINDSIGHT_BANK_ID", "project-arbitrage"),
            name="Project Arbitrage",
        )
        print("Hindsight OK: memory bank confirmed.")
        print(f"Memory bank: {os.getenv('HINDSIGHT_BANK_ID', 'project-arbitrage')}")
        hindsight.close()
    except Exception as exc:
        print(f"Hindsight FAILED: {type(exc).__name__}: {exc}")

print("\nSummary:")
print(f"- Groq: {groq_status}")
print(f"- Hindsight: {hindsight_status}")
if is_placeholder(groq_key) and is_placeholder(hindsight_key):
    print("Configuration status: both services are not configured; add valid keys to .env to enable live testing.")
elif is_placeholder(groq_key) or is_placeholder(hindsight_key):
    print("Configuration status: one service is configured, one is not. Complete the missing key(s) in .env.")
else:
    print("Configuration status: both services appear configured. Live tests were attempted.")
