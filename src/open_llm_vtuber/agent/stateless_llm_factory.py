from typing import Type

from loguru import logger

from .stateless_llm.stateless_llm_interface import StatelessLLMInterface
from .stateless_llm.wsl_claude import WSLClaudeLLM


class LLMFactory:
    @staticmethod
    def create_llm(llm_provider, **kwargs) -> Type[StatelessLLMInterface]:
        """Create an LLM. Always returns WSLClaudeLLM regardless of llm_provider.

        WSL Claude subprocess is the sole permitted LLM backend.
        """
        # Force WSL Claude regardless of what conf.yaml says
        llm_provider = "wsl_claude_llm"
        logger.info(f"Initializing LLM: {llm_provider} (WSL Claude subprocess)")

        return WSLClaudeLLM(
            system=kwargs.get("system_prompt", ""),
            session_dir=kwargs.get("session_dir", "sessions"),
        )
