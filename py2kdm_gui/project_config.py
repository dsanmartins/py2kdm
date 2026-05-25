from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class DynamicScenarioConfig:
    name: str
    script: str
    mode: str = "desktop"
    enabled: bool = True
    description: str = ""


@dataclass
class DynamicAnalysisConfig:
    enabled: bool = True
    scenarios: list[DynamicScenarioConfig] = field(default_factory=list)


@dataclass
class AgentConfig:
    llm_provider: str = "none"
    llm_model: str = ""
    llm_timeout: int = 300


@dataclass
class ProjectConfig:
    name: str
    root: str
    output_dir: str
    dynamic_analysis: DynamicAnalysisConfig = field(default_factory=DynamicAnalysisConfig)
    agents: AgentConfig = field(default_factory=AgentConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProjectConfig":
        project = data.get("project", {})

        dynamic = data.get("dynamic_analysis", {})
        scenarios = [
            DynamicScenarioConfig(
                name=item.get("name", ""),
                script=item.get("script", ""),
                mode=item.get("mode", "desktop"),
                enabled=item.get("enabled", True),
                description=item.get("description", ""),
            )
            for item in dynamic.get("scenarios", [])
        ]

        agents = data.get("agents", {})

        return cls(
            name=project.get("name", ""),
            root=project.get("root", ""),
            output_dir=project.get("output_dir", ""),
            dynamic_analysis=DynamicAnalysisConfig(
                enabled=dynamic.get("enabled", True),
                scenarios=scenarios,
            ),
            agents=AgentConfig(
                llm_provider=agents.get("llm_provider", "none"),
                llm_model=agents.get("llm_model", ""),
                llm_timeout=int(agents.get("llm_timeout", 300)),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "project": {
                "name": self.name,
                "root": self.root,
                "output_dir": self.output_dir,
            },
            "dynamic_analysis": {
                "enabled": self.dynamic_analysis.enabled,
                "scenarios": [
                    {
                        "name": scenario.name,
                        "script": scenario.script,
                        "mode": scenario.mode,
                        "enabled": scenario.enabled,
                        "description": scenario.description,
                    }
                    for scenario in self.dynamic_analysis.scenarios
                ],
            },
            "agents": {
                "llm_provider": self.agents.llm_provider,
                "llm_model": self.agents.llm_model,
                "llm_timeout": self.agents.llm_timeout,
            },
        }


def load_project_config(path: str | Path) -> ProjectConfig:
    path = Path(path)

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    return ProjectConfig.from_dict(data)


def save_project_config(config: ProjectConfig, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as handle:
        json.dump(config.to_dict(), handle, indent=2, ensure_ascii=False)
