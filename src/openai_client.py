
from openai import OpenAI
import os

class OpenAIClient:
    def __init__(self, config):
        self.config = config.get("openai", {})
        self.api_key = self.config.get("api_key", "").strip()
        self.model = self.config.get("model", "gpt-4o-mini")
        self.base_url = self.config.get("base_url")
        
        if self.api_key:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
        else:
            self.client = None
            print("Warning: No OpenAI API key provided in config.yml")

    def translate_text(self, text, prompt_template, style="strict"):
        """
        Translates text using OpenAI.
        Returns original text on ANY failure (hard fallback).
        """
        if not self.client or not text.strip():
            return text

        try:
            # Format the system prompt
            system_prompt = prompt_template.format(style=style)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text}
                ],
                timeout=10  # strict timeout
            )
            
            translated_text = response.choices[0].message.content.strip()
            return translated_text
            
        except Exception as e:
            print(f"OpenAI translation failed: {e}")
            return text
