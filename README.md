# AgentWorm

> [!WARNING]
> ⚠️ This project is intended solely for ethical, defensive, and research-oriented experimentation in controlled environments.
> 🚫 Using it for unauthorized access, malicious activity, or any harmful purpose is strictly unethical and strongly discouraged.
> 🛑 Please refrain from using this repository outside of legitimate research and authorized testing contexts.

> [!NOTE]
> 🔬 This repository is still under active research and development.
> 🧪 The code, architecture, and documentation are evolving as experiments and sprint work progress.

AgentWorm is a research project focused on building and studying an agentic command-and-control system for autonomous network propagation in a contained lab environment. The repository explores how a lightweight local agent and an LLM-driven C2 brain can work together to simulate reconnaissance, lateral movement, credential discovery, and multi-host coordination in a controlled and observable setting. This project is still a research effort and is intended for academic, defensive, and experimentation purposes only.

## Documentation

The repository includes several design and planning documents that explain the system in more detail:

- [AGENTIC_C2_DESIGN.md](AGENTIC_C2_DESIGN.md) — describes the proposed agentic C2 architecture and the shift from a prompt-dispatch design toward a tool-driven agent loop.
- [PLAN.md](PLAN.md) — captures the overall implementation plan, milestones, and project direction.
- [EXPLOIT_CHAIN.md](EXPLOIT_CHAIN.md) — outlines the exploit-chain research design and the multi-hop propagation scenarios being studied.
- [DO_EXPLOIT_CHAIN.md](DO_EXPLOIT_CHAIN.md) — documents the DigitalOcean-based testbed design and its final topology.
- [CLAUDE.md](CLAUDE.md) — contains knowledge for agentic development (Claude Code, Copilot, etc.)

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
