import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('dart_agent', Path(__file__).parents[1] / 'src/dart_agent.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_parse_num():
    assert mod.parse_num('1,234') == 1234
    assert mod.parse_num('(123)') == -123
    assert mod.parse_num('-') is None
