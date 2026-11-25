import asyncio
async def research_agent():
    await asyncio.sleep(2)
    return "Customer Research Completed"

async def analysis_agent():
    await asyncio.sleep(3)
    return "Customer Analysis Completed"

async def email_agent():
    await asyncio.sleep(4)
    return "Email Preparation Completed"
async def main():
    results = await asyncio.gather(
        research_agent(),
        analysis_agent(),
        email_agent()
    )
    for result in results:
        print(result)

asyncio.run(main())