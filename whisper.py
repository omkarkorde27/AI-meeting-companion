from openai import OpenAI
from config import current_config as config

client = OpenAI(api_key=config.OpenAI_API_KEY)

# Transcribe audio
with open("/Users/User/Documents/Luddy Hacks/bush-clinton_debate_waffle.wav", "rb") as audio_file:
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=audio_file,
        response_format="text"  # or "json", "srt", "vtt", etc.
    )

print(transcript)