def get_weather(city: str):
    return f"The weather in {city} is sunny, 22°C."

TOOLS = {
    "get_weather": get_weather
}

TOOL_SCHEMAS = [
                    {
                    "type":"function",
                    "function":{
                            "name":"get_weather",
                            "description":"Gets the current weather conditions of a city",
                            "parameters":{
                            "type":"object",
                            "properties":{
                                "city":{
                                "type":"string",
                                "description":"The name of the city"
                                }
                            },
                            "required":["city"]
                            }
                        }
                    }
                ]