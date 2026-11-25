def research_agent():
    return "Researching Customers..."

def email_agent():
    return "Creating Sales Email..."

def analysis_agent():
    return "Analyzing Customer data..."

def router(task):
    if task == "research":
        return research_agent()
    elif task == "Email":
        return email_agent()
    elif task == "analysis":
        return analysis_agent()
    else:
        return "Task not supported"

result = router("research")
print(result)