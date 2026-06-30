"""Core skill invocation logic using Claude API.

This module provides the infrastructure for invoking skills defined in skills/
directory through the Claude API, with proper context setup and output validation.
"""
from __future__ import annotations
import os
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Any, Optional, TypeVar, Type
import re

from pydantic import BaseModel, ValidationError
import anthropic


T = TypeVar("T", bound=BaseModel)


class SkillInvoker:
    """Manages skill invocation through Claude API with context management."""

    def __init__(
        self,
        skills_dir: Path,
        data_dir: Path,
        api_key: Optional[str] = None,
    ):
        """Initialize skill invoker.

        Args:
            skills_dir: Path to skills/ directory
            data_dir: Path to data/ directory (for context files)
            api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
        """
        self.skills_dir = Path(skills_dir)
        self.data_dir = Path(data_dir)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

        if not self.api_key:
            raise ValueError(
                "API key required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )

        self.client = anthropic.Anthropic(api_key=self.api_key)

    def load_skill_definition(self, skill_name: str) -> dict[str, Any]:
        """Load and parse skill definition from SKILL.md.

        Args:
            skill_name: Name of skill directory (e.g., 'essdive_sm_curator')

        Returns:
            Dict with 'metadata' (frontmatter) and 'system_prompt' (extracted content)

        Raises:
            FileNotFoundError: If skill directory or SKILL.md not found
            ValueError: If SKILL.md is malformed
        """
        skill_path = self.skills_dir / skill_name / "SKILL.md"

        if not skill_path.exists():
            raise FileNotFoundError(
                f"Skill definition not found: {skill_path}\n"
                f"Available skills: {[d.name for d in self.skills_dir.iterdir() if d.is_dir()]}"
            )

        content = skill_path.read_text()

        # Extract YAML frontmatter
        frontmatter_match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
        if not frontmatter_match:
            raise ValueError(f"No YAML frontmatter found in {skill_path}")

        # Extract system prompt (content after "# SYSTEM PROMPT" marker)
        system_prompt_match = re.search(
            r'# =+\s*\n# SYSTEM PROMPT\s*\n# =+\s*\n(.*)',
            content,
            re.DOTALL | re.IGNORECASE
        )

        if not system_prompt_match:
            raise ValueError(
                f"No SYSTEM PROMPT section found in {skill_path}. "
                "Expected '# SYSTEM PROMPT' header."
            )

        system_prompt = system_prompt_match.group(1).strip()

        # Parse frontmatter (simplified YAML parsing for this use case)
        # In production, could use pyyaml, but avoiding dependency for now
        frontmatter_text = frontmatter_match.group(1)
        metadata = self._parse_simple_yaml(frontmatter_text)

        return {
            "metadata": metadata,
            "system_prompt": system_prompt,
            "skill_name": skill_name,
        }

    def _parse_simple_yaml(self, yaml_text: str) -> dict[str, Any]:
        """Simple YAML parser for skill frontmatter.

        Handles:
        - Simple key: value pairs
        - Lists (- item format)
        - Nested structure with indentation

        Does NOT handle:
        - Complex YAML features (anchors, multi-line strings, etc.)
        - Use pyyaml if you need full YAML support
        """
        result = {}
        current_key = None
        current_list = None
        current_dict_key = None

        for line in yaml_text.split('\n'):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            # Simple key: value
            if ':' in line and not line.startswith(' '):
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                if value.startswith('>'):
                    # Multi-line string indicator
                    current_key = key
                    result[key] = []
                    current_list = result[key]
                    current_dict_key = None
                elif value:
                    result[key] = value.strip('"\'')
                    current_key = None
                    current_list = None
                    current_dict_key = None
                else:
                    # Start of nested structure
                    current_key = key
                    result[key] = {}
                    current_list = None
                    current_dict_key = key

            # Nested key: value (indented)
            elif ':' in line and line.startswith(' ') and current_dict_key:
                key, value = line.split(':', 1)
                key = key.strip()
                value = value.strip()

                if isinstance(result[current_dict_key], dict):
                    if value:
                        result[current_dict_key][key] = value.strip('"\'')
                    else:
                        # Could be a list following
                        result[current_dict_key][key] = []
                        current_list = result[current_dict_key][key]

            # List item
            elif line.strip().startswith('-'):
                item = line.strip()[1:].strip()
                if current_list is not None and isinstance(current_list, list):
                    current_list.append(item)
                elif current_key and isinstance(result.get(current_key), list):
                    result[current_key].append(item)

            # Continuation of multi-line string
            elif current_key and isinstance(result.get(current_key), list) and not current_dict_key:
                result[current_key].append(stripped)

        # Join multi-line strings
        for key, value in result.items():
            if isinstance(value, list) and all(isinstance(v, str) for v in value):
                result[key] = ' '.join(value)

        return result

    def prepare_context_files(
        self,
        context_dependencies: list[str],
        exemplar_pool: Optional[list[int]] = None,
    ) -> dict[str, str]:
        """Load context files referenced by skill definition.

        Args:
            context_dependencies: List of file paths from skill metadata
            exemplar_pool: If provided, filter mapping JSON to only include these indices

        Returns:
            Dict mapping file path to file content (for inclusion in prompt)
        """
        context = {}

        for dep_pattern in context_dependencies:
            # Expand glob patterns
            if '*' in dep_pattern:
                matching_files = list(self.data_dir.glob(dep_pattern.replace('data/', '')))
            else:
                matching_files = [self.data_dir / dep_pattern.replace('data/', '')]

            for file_path in matching_files:
                if not file_path.exists():
                    continue

                content = file_path.read_text()

                # Special handling for mapping JSON: filter to exemplar pool
                if 'mapping.json' in file_path.name and exemplar_pool is not None:
                    try:
                        full_mapping = json.loads(content)
                        filtered_mapping = [
                            entry for entry in full_mapping
                            if entry.get('index') in exemplar_pool
                        ]
                        content = json.dumps(filtered_mapping, indent=2)
                    except json.JSONDecodeError:
                        pass  # Use full content if not valid JSON

                # Store with relative path as key
                rel_path = str(file_path.relative_to(self.data_dir.parent))
                context[rel_path] = content

        return context

    def invoke_skill(
        self,
        skill_name: str,
        user_prompt: str,
        model_id: str = "claude-sonnet-4-5",
        temperature: float = 1.0,
        max_tokens: int = 8192,
        output_schema: Optional[Type[T]] = None,
        exemplar_pool: Optional[list[int]] = None,
        **api_kwargs,
    ) -> dict[str, Any]:
        """Invoke a skill through Claude API.

        Args:
            skill_name: Name of skill to invoke
            user_prompt: User's input message
            model_id: Claude model to use
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            output_schema: Optional Pydantic model for structured output validation
            exemplar_pool: Dataset indices available as exemplars (filters context)
            **api_kwargs: Additional kwargs passed to Claude API

        Returns:
            Dict with:
                - 'response': Raw Claude API response
                - 'parsed_output': If output_schema provided, validated model instance
                - 'skill_version': Skill version from metadata
                - 'run_metadata': Execution metadata

        Raises:
            ValidationError: If output doesn't match schema
            anthropic.APIError: If API call fails
        """
        # Load skill definition
        skill_def = self.load_skill_definition(skill_name)
        system_prompt = skill_def["system_prompt"]
        metadata = skill_def["metadata"]

        # Load context dependencies
        context_deps = metadata.get("context_dependencies", [])
        if isinstance(context_deps, str):
            context_deps = [context_deps]

        context_files = self.prepare_context_files(context_deps, exemplar_pool)

        # Build enhanced user prompt with context
        enhanced_prompt = self._build_enhanced_prompt(
            user_prompt=user_prompt,
            context_files=context_files,
            skill_metadata=metadata,
        )

        # Invoke Claude API
        response = self.client.messages.create(
            model=model_id,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system_prompt,
            messages=[
                {"role": "user", "content": enhanced_prompt}
            ],
            **api_kwargs
        )

        # Extract text content
        response_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                response_text += block.text

        result = {
            "response": response,
            "response_text": response_text,
            "skill_version": metadata.get("version"),
            "run_metadata": {
                "skill_name": skill_name,
                "model_id": model_id,
                "temperature": temperature,
                "timestamp": datetime.utcnow().isoformat(),
                "usage": {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            },
        }

        # Parse and validate against schema if provided
        if output_schema is not None:
            parsed = self._extract_and_validate_output(
                response_text=response_text,
                schema=output_schema,
            )
            result["parsed_output"] = parsed

        return result

    def _build_enhanced_prompt(
        self,
        user_prompt: str,
        context_files: dict[str, str],
        skill_metadata: dict[str, Any],
    ) -> str:
        """Build enhanced prompt with context files and metadata.

        Args:
            user_prompt: User's original prompt
            context_files: Dict of file paths to contents
            skill_metadata: Skill metadata from frontmatter

        Returns:
            Enhanced prompt string
        """
        parts = []

        # Add context files if any
        if context_files:
            parts.append("# CONTEXT FILES\n")
            for path, content in context_files.items():
                parts.append(f"## {path}\n\n```\n{content}\n```\n")

        # Add user prompt
        parts.append("# YOUR TASK\n")
        parts.append(user_prompt)

        return "\n\n".join(parts)

    def _extract_and_validate_output(
        self,
        response_text: str,
        schema: Type[T],
    ) -> T:
        """Extract and validate structured output from response.

        Looks for JSON blocks in the response and validates against schema.

        Args:
            response_text: Raw response text from Claude
            schema: Pydantic model class

        Returns:
            Validated model instance

        Raises:
            ValidationError: If no valid JSON found or validation fails
        """
        # Try to extract JSON from code blocks
        json_blocks = re.findall(
            r'```(?:json)?\n(.*?)\n```',
            response_text,
            re.DOTALL
        )

        # Also try to find raw JSON objects
        json_objects = re.findall(
            r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',
            response_text,
            re.DOTALL
        )

        candidates = json_blocks + json_objects

        # Try each candidate
        errors = []
        for candidate in candidates:
            try:
                data = json.loads(candidate)
                return schema(**data)
            except (json.JSONDecodeError, ValidationError) as e:
                errors.append(str(e))
                continue

        # If we get here, no valid output found
        raise ValidationError(
            f"Could not extract valid {schema.__name__} from response.\n"
            f"Tried {len(candidates)} JSON candidates.\n"
            f"Errors: {errors[:3]}"  # Show first 3 errors
        )

    @staticmethod
    def generate_run_id(identifier: str, seed: int) -> str:
        """Generate deterministic run ID from identifier and seed."""
        content = f"{identifier}_{seed}"
        return hashlib.sha256(content.encode()).hexdigest()[:12]
