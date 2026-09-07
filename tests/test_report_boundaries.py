"""Fresh review cases for the 0.2.0 work, independent of the original audit."""

import json

import pytest

from toolstorm import Cassette, ConfigurationError, Contract, Redactor, Rule, Storm, VirtualClock
from toolstorm.cli import main


@pytest.mark.parametrize("capture", [True, False])
def test_oversized_replacement_does_not_make_report_unavailable(capture):
    payload = "x" * 128_001
    try:
        storm = Storm([Rule("large", "answer", "replace", replacement=payload)], capture=capture)
    except ConfigurationError:
        # Rejecting an unreportable fixture before execution is also a safe API.
        return

    @storm.tool("answer")
    def answer():
        pytest.fail("replacement must not call the function")

    assert answer() == payload
    report = storm.report()
    if capture:
        assert report.calls[0]["capture_error"] is True
    assert report.calls[0]["status"] == "ok"
    assert Contract(report).require_triggered().passed


def test_unused_oversized_replacement_cannot_break_report():
    try:
        storm = Storm([Rule("large", "missing", "replace", replacement="x" * 128_001)])
    except ConfigurationError:
        return
    assert storm.report().calls == []


def test_redaction_key_collision_in_replacement_preserves_report():
    payload = {"private-a": 1, "private-b": 2}
    try:
        storm = Storm(
            [Rule("collides", "answer", "replace", replacement=payload)],
            redactor=Redactor(secrets=("private-a", "private-b")),
        )
    except ConfigurationError:
        return

    @storm.tool("answer")
    def answer():
        pytest.fail("replacement must not call the function")

    assert answer() == payload
    report = storm.report()
    assert report.calls[0]["capture_error"] is True
    assert report.calls[0]["status"] == "ok"


def nested_list(depth):
    value = "leaf"
    for _ in range(depth):
        value = [value]
    return value


@pytest.mark.parametrize("depth", [29, 30, 31, 32])
def test_accepted_captured_output_remains_exportable(depth):
    storm = Storm(clock=VirtualClock())
    result = nested_list(depth)

    @storm.tool("deep")
    def deep():
        return result

    assert deep() is result
    report = storm.report()
    exported = report.to_dict()
    # The implementation may reject payload capture, but may never poison a report.
    if report.calls[0]["capture_error"]:
        assert exported["calls"][0]["output"] is None
    else:
        assert Cassette.from_report(report).to_dict() == exported


def capture_replace():
    storm = Storm(
        [Rule("replacement", "value", "replace", replacement={"answer": 42})], clock=VirtualClock()
    )

    @storm.tool("value")
    def value():
        pytest.fail("replacement must not call the function")

    value()
    return storm.report().to_dict()


def test_impossible_probability_zero_selected_fault_is_rejected():
    data = capture_replace()
    data["rules"][0]["probability"] = 0.0
    with pytest.raises(ConfigurationError):
        Cassette(data)


def test_cli_check_does_not_certify_probability_zero_fault_as_exercised(tmp_path, capsys):
    data = capture_replace()
    data["rules"][0]["probability"] = 0.0
    path = tmp_path / "impossible.json"
    path.write_text(json.dumps(data))
    assert main(["check", str(path), "--json"]) == 2


def test_replacement_output_must_agree_with_declared_replacement():
    data = capture_replace()
    data["calls"][0]["output"] = {"answer": "not the configured replacement"}
    with pytest.raises(ConfigurationError):
        Cassette(data)


def test_successful_ordinary_call_requires_execution():
    storm = Storm(clock=VirtualClock())

    @storm.tool("value")
    def value():
        return 42

    value()
    data = storm.report().to_dict()
    data["calls"][0]["executed"] = False
    with pytest.raises(ConfigurationError):
        Cassette(data)
