# A very simple test that cpython works at all
import platform
print platform.python_implementation()
assert platform.python_implementation() == 'CPython'
