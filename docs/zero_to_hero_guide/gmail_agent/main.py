import argparse
import gmagent
import asyncio
import json
from functions_prompt import *

from llama_stack_client import LlamaStackClient
from llama_stack_client.lib.agents.agent import Agent
from llama_stack_client.lib.agents.event_logger import EventLogger
from llama_stack_client.types.agent_create_params import (
    AgentConfig,
)

from shared import memory

LLAMA_STACK_API_TOGETHER_URL="https://llama-stack.together.ai"
LLAMA31_8B_INSTRUCT = "Llama3.1-8B-Instruct"

async def create_gmail_agent(client: LlamaStackClient) -> Agent:
    """Create an agent with gmail tool capabilities."""

    listEmailsTool = ListEmailsTool()
    getEmailDetailTool = GetEmailDetailTool()
    sendEmailTool = SendEmailTool()
    getPDFSummaryTool = GetPDFSummaryTool()
    createDraftTool = CreateDraftTool()
    sendDraftTool = SendDraftTool()

    agent_config = AgentConfig(
        model=LLAMA31_8B_INSTRUCT,
        instructions=system_prompt,
        sampling_params={
            "strategy": "greedy",
            "temperature": 0.0,
            "top_p": 0.9,
        },
        tools=[
            listEmailsTool.get_tool_definition(),
            getEmailDetailTool.get_tool_definition(),
            sendEmailTool.get_tool_definition(),
            getPDFSummaryTool.get_tool_definition(),
            createDraftTool.get_tool_definition(),
            sendDraftTool.get_tool_definition(),

        ],
        tool_choice="auto",
        tool_prompt_format="json",
        input_shields=[],
        output_shields=[],
        enable_session_persistence=True
    )

    agent = Agent(
        client=client,
        agent_config=agent_config,
        custom_tools=[listEmailsTool,
                      getEmailDetailTool,
                      sendEmailTool,
                      getPDFSummaryTool,
                      createDraftTool,
                      sendDraftTool]
    )

    return agent


async def main():
    parser = argparse.ArgumentParser(description="Set email address")
    parser.add_argument("--gmail", type=str, required=True, help="Your Gmail address")
    args = parser.parse_args()

    gmagent.set_email_service(args.gmail)

    greeting = llama31("hello", "Your name is Gmagent, an assistant that can perform all Gmail related tasks for your user.")
    agent_response = f"{greeting}\n\nYour ask: "

    # do i have emails with attachment larger than 5mb?
    # what's the detail of the email with subject this is an interesting paper

    while True:
        ask = input(agent_response)
        if ask == "bye":
            print(llama31("bye"))
            break
        print("\n-------------------------\nCalling Llama...")

        client = LlamaStackClient(base_url=LLAMA_STACK_API_TOGETHER_URL)
        agent = await create_gmail_agent(client)
        session_id = agent.create_session("email-session")

        response = agent.create_turn(
            messages=[{"role": "user", "content": ask}],
            session_id=session_id,
        )

        async for log in EventLogger().log(response):
            if log.role == "CustomTool":
                tool_name = json.loads(log.content)['name']
                result = json.loads(log.content)['result']
                if tool_name == 'list_emails':
                    # post processing
                    memory['emails'] = result
                    num = len(result)
                    if num == 0:
                        output = "I couldn't find any such emails. What else would you like to do?"
                    elif num <= 5:
                        output = f"I found {num} email{'s' if num > 1 else ''} matching your query:\n"
                        for i, email in enumerate(result, start=1):
                            output += f"{i}. From: {email['sender']}, Subject: {email['subject']}, Received on: {email['received_time']}\n"
                    else:
                        output = f"I found {num} emails matching your query. Here are the first 5 emails:\n"
                        for i in range(1, 6):
                            output += f"{i}. From: {result[i - 1]['sender']}, Subject: {result[i - 1]['subject']}, Received on: {result[i - 1]['received_time']}\n"

                elif tool_name == "get_email_detail":
                    output = result

                print(f"\n-------------------------\n\nGmagent: {output}\n")
            elif log.role == "inference":
                print("Llama returned: ", end="")
            else:
                print(log, end="")



        agent_response = "\n\nYour ask: "




if __name__ == "__main__":
    asyncio.run(main())



