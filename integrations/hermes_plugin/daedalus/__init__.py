"""Compatibility shim.

The production Hermes plugin entrypoint now lives in the core ``daedalus``
package so Hermes, CLI, and dashboard all use the same treasury implementation.
"""

from daedalus.hermes import register
