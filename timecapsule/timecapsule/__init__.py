"""Top-level package for timecapsule."""

__author__ = """Sean Micek"""
__email__ = 'seanrm100@gmail.com'
__version__ = '0.1.0'

#drill down to the goods no matter where you're importing from
if __package__ is None or __package__ == '':
    # uses current directory visibility
    from timecapsule import *
else:
    # uses current package visibility
    from .timecapsule import *