from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

try:
    from langchain_openai import ChatOpenAI  # type: ignore
except Exception:
    ChatOpenAI = None  # type: ignore


class ToolCallingAgent:
    """
    Tool-calling agent for models that support bind_tools (OpenAI, Anthropic, …).

    Empty tools uses a chat-only executor with the same run() contract.
    """

    def __init__(
        self,
        tools: List[Union[BaseTool, Any]],
        llm: BaseChatModel,
        *,
        force_tool: bool = True,
        allow_parallel: bool = False,
        max_iterations: int = 6,
        verbose: bool = True,
        return_intermediate_steps: bool = True,
        system_prompt: Optional[str] = None,
    ) -> None:
        self.tools = tools
        self.llm = llm
        self.max_iterations = max_iterations
        self.system_prompt = system_prompt or self._default_system_prompt()

        if not tools:
            self.agent = None
            self.executor = _ChatOnlyExecutor(llm, self.system_prompt)
            return

        tool_choice = "any" if force_tool else "auto"

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", self.system_prompt),
                MessagesPlaceholder(variable_name="chat_history", optional=True),
                ("user", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        if not hasattr(llm, "bind_tools"):
            raise ValueError("The provided llm does not support .bind_tools(...)")
        try:
            bound_llm = llm.bind_tools(
                tools,
                tool_choice=tool_choice,
                parallel_tool_calls=allow_parallel,
            )
        except TypeError:
            bound_llm = llm.bind_tools(tools, tool_choice=tool_choice)

        self.agent = create_tool_calling_agent(bound_llm, tools, prompt)
        self.executor = AgentExecutor(
            agent=self.agent,
            tools=tools,
            verbose=verbose,
            return_intermediate_steps=return_intermediate_steps,
            max_iterations=max_iterations,
        )

    @staticmethod
    def _default_system_prompt() -> str:
        return """\
            You are a careful, step-by-step assistant that solves tasks using available tools.

            Follow this loop until you can confidently answer:
            1) THINK: Reason briefly about what to do.
            2) ACT: If needed, call exactly one tool with correct JSON arguments.
            3) OBSERVE: Read the tool result.
            4) REPEAT until done.
            5) FINAL: Give the user a clear answer.

            Rules:
            - Only use provided tools.
            - Tool calls must use the expected JSON schema.
            - If no tool is needed, answer directly.
            """

    def run(self, user_input: str, chat_history: Optional[List[Any]] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"input": user_input}
        if chat_history:
            payload["chat_history"] = chat_history
        return self.executor.invoke(payload)


class _ChatOnlyExecutor:
    """Same invoke/run payload as AgentExecutor when the agent has no tools yet."""

    def __init__(self, llm: BaseChatModel, system_prompt: str) -> None:
        self.llm = llm
        self.system_prompt = system_prompt

    def invoke(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        messages: List[Any] = []
        if self.system_prompt:
            messages.append(SystemMessage(content=self.system_prompt))
        messages.extend(inputs.get("chat_history") or [])
        messages.append(HumanMessage(content=inputs["input"]))
        response = self.llm.invoke(messages)
        return {"output": response.content, "intermediate_steps": []}


class OpenAIToolCallingAgent(ToolCallingAgent):
    """OpenAI-typed wrapper; Anthropic uses ToolCallingAgent instead."""

    def __init__(
        self,
        tools: List[Union[BaseTool, Any]],
        llm: BaseChatModel,
        **kwargs: Any,
    ) -> None:
        if ChatOpenAI is not None and not isinstance(llm, ChatOpenAI):  # type: ignore
            raise TypeError("OpenAIToolCallingAgent expects a ChatOpenAI instance")
        super().__init__(tools, llm, **kwargs)
