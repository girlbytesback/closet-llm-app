from anthropic import Anthropic

client = Anthropic()

response = client.messages.create(
    model="claude-sonnet-5",
    max_tokens=1024,
    messages=[
        {"role": "user", "content": "hi, tell me a joke again"}
    ]
)

print(response.content[0].text)