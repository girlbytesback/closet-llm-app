import base64
from anthropic import Anthropic

client = Anthropic()

# read the image file, encode to base64 (turns raw bytes into a text-safe string)
with open("outfit.jpeg", "rb") as f:
    image_data = base64.standard_b64encode(f.read()).decode("utf-8")

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/jpeg",
                        "data": image_data,
                    },
                },
                {
                    "type": "text",
                    "text": "describe what's in this photo. what colors do you see?",
                },
            ],
        }
    ],
)

print(response.content[0].text)