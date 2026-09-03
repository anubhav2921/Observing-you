from transformers import pipeline

# Loads the model from Hugging Face the first time (needs an NVIDIA GPU)
pipe = pipeline(
    "image-text-to-text",
    model="nvidia/LocateAnything-3B",
    trust_remote_code=True,
)

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "url": "my_photo.png"},
            {"type": "text", "text": "Locate all the instances that match: person."},
        ]
    }
]

result = pipe(text=messages)
print(result)  # -> labels + box coordinates
