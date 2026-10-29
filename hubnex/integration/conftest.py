"""Run with:  pip install pytest-homeassistant-custom-component hassil home-assistant-intents
              pytest -p pytest_homeassistant_custom_component tests

pytest-homeassistant-custom-component ships its own `custom_components` package, which shadows
ours: make this folder (which contains hubnex/) part of it."""

import pathlib
import sys

import pytest_homeassistant_custom_component

sys.path.insert(0, str(pathlib.Path(pytest_homeassistant_custom_component.__file__).parent / "testing_config"))
import custom_components  # noqa: E402

custom_components.__path__.append(str(pathlib.Path(__file__).parent))
