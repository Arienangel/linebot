import openai
import yaml
import random
from typing import Union

with open('config/app.yaml', encoding='utf-8') as f:
    conf = yaml.load(f, yaml.SafeLoader)['chatgpt']

openai.api_key = conf['token']
max_tokens = conf['max_tokens']


async def gpt35(message: str, temperature: Union[float, list[float]]):
    if isinstance(temperature, list): temperature = random.random() * (temperature[1] - temperature[0]) + temperature[0]
    completion = await openai.ChatCompletion.acreate(model="gpt-3.5-turbo", messages=[{"role": "user", "content": message}], temperature=temperature, max_tokens=max_tokens)
    return completion, temperature
