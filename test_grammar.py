import asyncio
from infrastructure.ollama_client import ollama_client
import sys

async def main():
    print("starting long test...")
    text = "this is a test document. " * 100
    try:
        res = await ollama_client.generate_json(f"analyze this text: {text}. return a json object with a 'summary' key.")
        print("response:", res)
    except Exception as e:
        print("error:", e)
        sys.exit(1)

asyncio.run(main())
