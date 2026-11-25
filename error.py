def add(a, b):
    return a+b

def divide(a, b):
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a/b 

def execute_tool(name, a, b):
    try:
        if name == "add":
            return add(a, b)
        elif name == "divide":
            return divide(a, b)
    except Exception as e:
        return f"Error: {e}";
print(execute_tool("add", 10, 20))
print(execute_tool("divide", 10, 0))