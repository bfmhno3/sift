"""Module b imports a name from a before a has defined it."""

from circular.a import a_value  # BAD: a is only half initialized

b_value = a_value + 1
