import os

from dotenv import load_dotenv

load_dotenv()

NEATLOGS_API_KEY = os.environ["NEATLOGS_API_KEY"]
GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]

import neatlogs

neatlogs.init(
    api_key=NEATLOGS_API_KEY,
    workflow_name="trace-test",
)

from openai import OpenAI

client = neatlogs.wrap(
    OpenAI(
        api_key=GEMINI_API_KEY,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )
)

response = client.chat.completions.create(
    model="gemini-3.8-flash",
    messages=[{"role": "user", "content": "Say hello in one short sentence."}],
)
print(response.choices[0].message.content)

neatlogs.flush()
neatlogs.shutdown()
