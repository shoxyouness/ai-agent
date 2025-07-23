import yaml
from pathlib import Path
import openai
Models= ['openai','anthropic','google']
class LLM:
    def __init__(self, model, model_name = None):
        if model not in Models:
            raise ValueError(f"Model {model} is not supported." 
                             f"Supported models are: {Models}")
        self.model = model
        self.model_name = model_name
        self.model_config = self._get_model_config()
        self._init_model()

    def _get_model_config(self):
        path = r"C:\Users\medyo\Desktop\AI Agents\Bachelorarbeit\AI Perosnal Agent\backend\src\config\llm_config.yaml"
        with open(Path(path), 'r') as file:
            config = yaml.safe_load(file)

        if self.model not in config:
            raise ValueError(f"Model {self.model} not found in configuration file.")
        model_config = config.get(self.model)
        if not self.model_name:
            self.model_name = model_config.get('default_model', None)
        return model_config

    def _init_model(self):
        if self.model == 'openai':
            openai.api_key = self.model_config.get('api_key', None)
            openai.base_url = self.model_config.get('base_url', None)

        elif self.model == 'anthropic':
            import anthropic
            anthropic.api_key = self.model_config.get('api_key', None)
            anthropic.base_url = self.model_config.get('base_url', None)

        elif self.model == 'google':
            from google.generativeai import Client
            self.client = Client(api_key=self.model_config.get('api_key', None))
        else:
            raise ValueError(f"Model {self.model} is not supported for initialization.")

    def invoke(self, prompt :str ,history : list = None,**kwargs):
        messages = history if history else []
        messages.append({"role":"user", "content": prompt})
        if self.model == 'openai':
            response = openai.chat.completions.create(
                model= self.model_name,
                messages = messages,
            )
            return response.choices[0].message.content
        elif self.model == 'anthropic':
            import anthropic
            response = anthropic.chat.completions.create(
                model= self.model_name,
                messages = messages,
            )
            return response.choices[0].message.content
        elif self.model == 'google':
            response = self.client.chat.completions.create(
                model= self.model_name,
                messages = messages,
            )
            return response.choices[0].message.content