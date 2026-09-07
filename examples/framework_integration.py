"""The agent receives the wrapped function; no framework dependency required.

For LangChain: StructuredTool.from_function(wrapped).
For the OpenAI Agents SDK: function_tool(wrapped).
These optional framework-specific adapters are not integration-tested here.
"""

from typing import Any

from toolstorm import Contract, Rule, Storm, ToolUnavailable, VirtualClock


def get_weather(city: str) -> dict[str, Any]:
    return {"city": city, "temperature_c": 22}


def main() -> None:
    storm = Storm([Rule("outage", "weather", "unavailable", limit=1)], clock=VirtualClock())
    weather_tool = storm.tool("weather")(get_weather)
    # Replace this scripted caller with your framework's tool registration.
    try:
        weather_tool("Delhi")
    except ToolUnavailable:
        answer = weather_tool("Delhi")
    assert answer["city"] == "Delhi"
    Contract(storm.report()).require_triggered().at_most_calls(2).assert_valid()
    print("Framework-neutral wrapped tool: recovery verified.")


if __name__ == "__main__":
    main()
