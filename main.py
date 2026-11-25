def add(a, b):
    return a+b

def subtract(a, b):
    return a-b

def multiply(a, b):
    return a * b
def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a/b 
def greet(name):
    return f"Hello, {name}! "


#tool_name = "multiply"
tool_name = "add"
#tool_name = "divide"
#tool_name = "subtract"




tool_registry = {
    "add" : add,
    "subtract" : subtract,
    "multiply" : multiply,
    "divide" : divide,
    "greet" : greet
}

result = tool_registry[tool_name] (5,4)
print(result)