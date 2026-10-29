"""Compatibility imports for callers that used the former script module."""

from showdown_pipeline.parser import fetch_and_parse_replay, parse_replay_payload

__all__ = ["fetch_and_parse_replay", "parse_replay_payload"]
