#!/usr/bin/env python
"""
Simple test runner script that runs the test suite without server interference.
"""
import os
import sys
import django
from django.conf import settings
from django.test.utils import get_runner

if __name__ == "__main__":
    os.environ['DJANGO_SETTINGS_MODULE'] = 'kore.settings'
    django.setup()
    TestRunner = get_runner(settings)
    test_runner = TestRunner(verbosity=2)
    failures = test_runner.run_tests(["api.tests"])
    sys.exit(bool(failures))
