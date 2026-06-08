"""
LangGraph agent — the C2 brain.

Fresh conversation context per agent activation; no checkpointer.
The agent receives events, calls tools, and drives all propagation decisions.

Supported providers (set via configs/llm.yaml → llm.provider):
  openai            — OpenAI API  (ChatOpenAI, langchain-openai)
  anthropic         — Anthropic Claude  (ChatAnthropic, langchain-anthropic)
  openai_compatible — Any OpenAI-compatible endpoint: DO Inference, Ollama, etc.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Annotated

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from typing_extensions import TypedDict

from tools import ALL_TOOLS


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


def _build_llm(llm_cfg: dict) -> BaseChatModel:
    """
    Instantiate the right LangChain chat model based on llm.yaml → llm.provider.

    Packages are imported lazily so only the active provider needs to be installed.
    """
    provider    = llm_cfg.get("provider", "openai_compatible")
    model_name  = os.environ.get("LLM_MODEL") or llm_cfg["model"]
    api_key_env = llm_cfg.get("api_key_env", "")
    api_key     = os.environ.get(api_key_env, "") if api_key_env else ""
    max_tokens  = llm_cfg.get("max_tokens", 4096)
    max_retries = 6  # exponential backoff for transient errors

    if provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            api_key=api_key or None,       # falls back to OPENAI_API_KEY env var
            max_tokens=max_tokens,
            max_retries=max_retries,
            temperature=0,
        )

    elif provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            api_key=api_key or None,       # falls back to ANTHROPIC_API_KEY env var
            max_tokens=max_tokens,
            max_retries=max_retries,
            temperature=0,
        )

    elif provider == "openai_compatible":
        from langchain_openai import ChatOpenAI
        api_base = llm_cfg.get("api_base", "").rstrip("/")
        if not api_base:
            raise ValueError("llm.api_base is required for provider=openai_compatible")
        return ChatOpenAI(
            model=model_name,
            base_url=api_base,
            api_key=api_key or "none",     # some endpoints require a non-empty string
            max_tokens=max_tokens,
            max_retries=max_retries,
            temperature=0,
        )

    else:
        raise ValueError(
            f"Unknown llm.provider '{provider}'. "
            "Valid values: openai | anthropic | openai_compatible"
        )


def build_agent(llm_cfg: dict, skills_dir: str, max_hosts: int, c2_ips: str = ""):
    """
    Build and return the compiled LangGraph app.

    No checkpointer — every invocation starts with a fresh message list.
    Persistent state lives entirely in WorldState, accessed via tool calls.
    The recursion_limit passed at invocation time caps within-turn tool loops.
    """
    llm = _build_llm(llm_cfg)
    llm_with_tools = llm.bind_tools(ALL_TOOLS)

    # System message loaded once; prepended to every LLM call.
    system_path = Path(skills_dir) / "system.md"
    system_content = system_path.read_text().strip()
    c2_ip = c2_ips.split(",")[0].strip() if c2_ips else "unknown"
    parts = c2_ip.split(".")
    gateway_ip = ".".join(parts[:-1] + ["1"]) if len(parts) == 4 else "unknown"
    system_content = system_content.replace("{{C2_IP}}", c2_ip)
    system_content = system_content.replace("{{GATEWAY_IP}}", gateway_ip)
    system_content += f"\n\n## Lab Context\nThis testbed contains at most {max_hosts} hosts total."
    system_message = SystemMessage(content=system_content)

    async def call_model(state: AgentState) -> dict:
        messages = [system_message] + list(state["messages"])
        response = await llm_with_tools.ainvoke(messages)

        # Some models (e.g. Gemma) emit tool calls with id=None.
        # LangGraph's ToolNode requires a valid string id to build ToolMessage responses.
        # Patch any missing ids here before the message enters the graph state.
        if getattr(response, "tool_calls", None):
            for tc in response.tool_calls:
                if not tc.get("id"):
                    tc["id"] = f"call_{uuid.uuid4().hex[:8]}"

        return {"messages": [response]}

    def should_continue(state: AgentState) -> str:
        last = state["messages"][-1]
        if getattr(last, "tool_calls", None):
            return "tools"
        return END

    graph = StateGraph(AgentState)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(ALL_TOOLS))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    graph.add_edge("tools", "agent")

    return graph.compile()
