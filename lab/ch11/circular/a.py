"""Module a imports a name from b; b imports a name from a."""

from circular.b import b_value  # BAD: b imports a back, at the top

a_value = b_value + 1
