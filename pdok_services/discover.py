import unittest
import os

loader = unittest.TestLoader()
suites = loader.discover(os.path.join("test"), pattern="test_*.py")

print("start")  # Don't remove this line

for suite in suites._tests:
    for cls in suite._tests:
        try:
            for m in cls._tests:
                print(m.id())
        except:  # noqa
            pass
