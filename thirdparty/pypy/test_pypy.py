# A very simple test that pypy works at all
import sys
print '__pypy__' in sys.builtin_module_names
assert '__pypy__' in sys.builtin_module_names

from lxml import etree
root = etree.fromstring('<root><test pass="1"/></root>')
assert root.find('test').get('pass') == '1'
