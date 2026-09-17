import json
import logging

from pool_qa.eval.capture import capture, malformed, retrieved, tokens

LOGGER = logging.getLogger("pool_qa.graph")


def log(payload: dict) -> None:
    LOGGER.info(json.dumps(payload))


def test_capture_parses_json_lines():
    with capture() as cap:
        log({"node": "intake", "tokens": {}})
        log({"node": "researcher", "tokens": {}})
    assert [r["node"] for r in cap.records] == ["intake", "researcher"]


def test_tokens_summed_per_model_across_records():
    with capture() as cap:
        log({"node": "intake", "tokens": {"m1": {"input": 10, "output": 2}}})
        log({"node": "researcher", "tokens": {"m1": {"input": 5, "output": 1}, "m2": {"input": 3, "output": 1}}})
    assert tokens(cap.records) == {"m1": {"input": 15, "output": 3}, "m2": {"input": 3, "output": 1}}


def test_malformed_true_only_when_a_record_has_it():
    with capture() as cap:
        log({"node": "intake", "tokens": {}})
        log({"node": "researcher", "tokens": {}, "malformed": True})
    assert malformed(cap.records) is True


def test_malformed_false_when_no_record_has_it():
    with capture() as cap:
        log({"node": "intake", "tokens": {}})
    assert malformed(cap.records) is False


def test_retrieved_is_sorted_union():
    with capture() as cap:
        log({"node": "researcher", "tokens": {}, "retrieved": ["b", "a"]})
        log({"node": "researcher", "tokens": {}, "retrieved": ["a", "c"]})
    assert retrieved(cap.records) == ["a", "b", "c"]


def test_handler_removed_after_exit():
    with capture():
        pass
    assert LOGGER.handlers == []


def test_level_restored_after_exit():
    previous = LOGGER.level
    LOGGER.setLevel(logging.WARNING)
    with capture():
        assert LOGGER.level == logging.INFO
    assert LOGGER.level == logging.WARNING
    LOGGER.setLevel(previous)
