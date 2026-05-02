import yaml
import os

from langchain_core.prompts import PromptTemplate

class PromptRegistry:
    def __init__(self, path="prompts"):
        self.path = path
        self.cache = {}

    def _load(self, name):
        if name not in self.cache:
            with open(os.path.join(self.path, f"{name}.yaml"), "r") as f:
                self.cache[name] = yaml.safe_load(f)
        return self.cache[name]

    def get(self, name, version=None):
        data = self._load(name)

        if version is None:
            version = data["default_version"]

        return data["versions"][version]

import os

def sys_prompt(name, version=None) -> str:
    registry = PromptRegistry()

    # 1. input validation
    if not isinstance(name, str) or not name.strip():
        raise ValueError("`name` must be a non-empty string")

    try:
        prompt = registry.get(name, version)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Prompt file not found: {os.path.join(registry.path, f'{name}.yaml')}"
        )
    except KeyError as e:
        raise KeyError(f"Missing expected key in prompt YAML: {e}")
    except Exception as e:
        raise RuntimeError(f"Failed to load prompt '{name}': {e}")

    # 2. type checking
    if not isinstance(prompt, dict):
        raise TypeError(f"Prompt '{name}' should be a dict, got {type(prompt)}")

    # 3. key field checking
    system = prompt.get("system")
    if system is None:
        raise KeyError(f"'system' field missing in prompt '{name}'")

    if not isinstance(system, str):
        raise TypeError(f"'system' must be a string in prompt '{name}'")

    # 4. content validation (optional but recommended)
    if not system.strip():
        raise ValueError(f"'system' prompt is empty in '{name}'")

    return system

import os


def temp_prompt(name, version=None, **kwargs) -> str:
    registry = PromptRegistry()
    prompt = registry.get(name, version)

    template = prompt.get("template")
    if not template:
        raise ValueError(f"Missing template in prompt '{name}'")

    try:
        prompt_template = PromptTemplate.from_template(template)
        return prompt_template.format(**kwargs)
    except Exception as e:
        raise ValueError(f"Template rendering failed: {e}")
