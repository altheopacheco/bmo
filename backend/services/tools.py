def get_weather(city: str) -> str:
    return f"Weather in {city}: 22°C, sunny."

def calculate(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}))
    except Exception as e:
        return f"Error: {e}"

def search_web(query: str) -> str:
    return f"Stub result for '{query}'"

def dispatch_tool(name: str, args: dict) -> str:
    handlers = {
        "get_weather": get_weather,
        "calculate": calculate,
        "search_web": search_web,
    }
    fn = handlers.get(name)
    if not fn:
        return f"Unknown tool '{name}'"
    return fn(**args)