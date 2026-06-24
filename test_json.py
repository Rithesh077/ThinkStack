import asyncio
from infrastructure.ollama_client import ollama_client
import sys

async def main():
    print("starting test...")
    try:
        res = await ollama_client.generate_json("tell me a joke about json in valid json format with a 'joke' key")
        print("response:", res)
    except Exception as e:
        print("error:", e)
        sys.exit(1)

asyncio.run(main())
