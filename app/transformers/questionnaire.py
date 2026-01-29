"""
FHIR to Markdown transformers for questionnaires.

This module converts FHIR Questionnaire resources into simplified structures
and markdown representations optimized for LLM context.
"""

from typing import Any

from app.config.logging import get_logger
from app.models.coverage import (
    AnswerOption,
    QuestionnaireItem,
    QuestionnaireItemType,
    QuestionnairePackageResult,
    TransformedQuestionnaire,
)

logger = get_logger(__name__)


class QuestionnaireTransformer:
    """
    Transforms FHIR Questionnaire resources for LLM consumption.

    Converts complex FHIR Questionnaire structures into:
    - Simplified QuestionnaireItem models
    - Human-readable markdown format
    """

    def __init__(self, value_sets: dict[str, Any] | None = None):
        """
        Initialize the transformer.

        Args:
            value_sets: Optional dict of ValueSet resources keyed by URL
                       for resolving coded answer options
        """
        self.value_sets = value_sets or {}

    def transform(self, questionnaire: dict[str, Any]) -> TransformedQuestionnaire:
        """
        Transform a FHIR Questionnaire into an LLM-friendly format.

        Args:
            questionnaire: FHIR Questionnaire resource

        Returns:
            TransformedQuestionnaire with simplified items and markdown
        """
        logger.debug(f"Transforming questionnaire: {questionnaire.get('id')}")

        # Extract basic metadata
        q_id = questionnaire.get("id", "unknown")
        url = questionnaire.get("url")
        title = questionnaire.get("title", questionnaire.get("name"))
        description = questionnaire.get("description")
        status = questionnaire.get("status", "unknown")

        # Transform items
        fhir_items = questionnaire.get("item", [])
        items = [self._transform_item(item) for item in fhir_items]

        # Count items and required items
        item_count, required_count = self._count_items(items)

        # Generate markdown
        markdown = self._generate_markdown(
            title=title,
            description=description,
            items=items,
            required_count=required_count,
        )

        return TransformedQuestionnaire(
            id=q_id,
            url=url,
            title=title,
            description=description,
            status=status,
            items=items,
            markdown=markdown,
            item_count=item_count,
            required_count=required_count,
        )

    def _transform_item(self, item: dict[str, Any]) -> QuestionnaireItem:
        """Transform a single FHIR Questionnaire item."""
        link_id = item.get("linkId", "")
        text = item.get("text")
        item_type_str = item.get("type", "string")

        # Map FHIR type to our enum
        try:
            item_type = QuestionnaireItemType(item_type_str)
        except ValueError:
            logger.warning(f"Unknown item type: {item_type_str}, defaulting to string")
            item_type = QuestionnaireItemType.STRING

        # Extract answer options
        answer_options = self._extract_answer_options(item)

        # Extract initial value
        initial_value = self._extract_initial_value(item)

        # Transform nested items
        nested_items = item.get("item", [])
        transformed_nested = (
            [self._transform_item(nested) for nested in nested_items] if nested_items else None
        )

        # Extract enable when condition as human-readable text
        enable_when = self._format_enable_when(item.get("enableWhen"))

        return QuestionnaireItem(
            link_id=link_id,
            text=text,
            type=item_type,
            required=item.get("required", False),
            repeats=item.get("repeats", False),
            read_only=item.get("readOnly", False),
            max_length=item.get("maxLength"),
            answer_options=answer_options,
            initial_value=initial_value,
            items=transformed_nested,
            enable_when=enable_when,
        )

    def _extract_answer_options(self, item: dict[str, Any]) -> list[AnswerOption] | None:
        """Extract answer options from a questionnaire item."""
        options = []

        # Check answerOption array
        answer_options = item.get("answerOption", [])
        for opt in answer_options:
            # Handle different value types
            if "valueCoding" in opt:
                coding = opt["valueCoding"]
                options.append(
                    AnswerOption(
                        value=coding.get("code", ""),
                        display=coding.get("display"),
                        system=coding.get("system"),
                    )
                )
            elif "valueString" in opt:
                options.append(AnswerOption(value=opt["valueString"]))
            elif "valueInteger" in opt:
                options.append(AnswerOption(value=str(opt["valueInteger"])))
            elif "valueDate" in opt:
                options.append(AnswerOption(value=opt["valueDate"]))
            elif "valueReference" in opt:
                ref = opt["valueReference"]
                options.append(
                    AnswerOption(
                        value=ref.get("reference", ""),
                        display=ref.get("display"),
                    )
                )

        # Check answerValueSet reference
        answer_value_set = item.get("answerValueSet")
        if answer_value_set and answer_value_set in self.value_sets:
            vs = self.value_sets[answer_value_set]
            vs_options = self._extract_valueset_options(vs)
            options.extend(vs_options)

        return options if options else None

    def _extract_valueset_options(self, value_set: dict[str, Any]) -> list[AnswerOption]:
        """Extract options from a ValueSet resource."""
        options = []

        # Handle expansion if present
        expansion = value_set.get("expansion", {})
        contains = expansion.get("contains", [])
        for item in contains:
            options.append(
                AnswerOption(
                    value=item.get("code", ""),
                    display=item.get("display"),
                    system=item.get("system"),
                )
            )

        # Handle compose if no expansion
        if not options:
            compose = value_set.get("compose", {})
            includes = compose.get("include", [])
            for inc in includes:
                concepts = inc.get("concept", [])
                system = inc.get("system")
                for concept in concepts:
                    options.append(
                        AnswerOption(
                            value=concept.get("code", ""),
                            display=concept.get("display"),
                            system=system,
                        )
                    )

        return options

    def _extract_initial_value(self, item: dict[str, Any]) -> str | None:
        """Extract initial/default value from an item."""
        initial = item.get("initial", [])
        if not initial:
            return None

        first_initial = initial[0]

        # Handle different value types
        for key in [
            "valueString",
            "valueInteger",
            "valueDecimal",
            "valueBoolean",
            "valueDate",
            "valueDateTime",
            "valueTime",
            "valueUri",
        ]:
            if key in first_initial:
                return str(first_initial[key])

        if "valueCoding" in first_initial:
            coding = first_initial["valueCoding"]
            return coding.get("display") or coding.get("code")

        if "valueQuantity" in first_initial:
            qty = first_initial["valueQuantity"]
            return f"{qty.get('value')} {qty.get('unit', '')}"

        return None

    def _format_enable_when(self, enable_when: list[dict[str, Any]] | None) -> str | None:
        """Format enableWhen conditions as human-readable text."""
        if not enable_when:
            return None

        conditions = []
        for condition in enable_when:
            question = condition.get("question", "")
            operator = condition.get("operator", "=")

            # Map operators to readable form
            op_map = {
                "exists": "is answered",
                "=": "equals",
                "!=": "not equals",
                ">": "greater than",
                "<": "less than",
                ">=": "greater than or equal to",
                "<=": "less than or equal to",
            }
            op_text = op_map.get(operator, operator)

            # Extract answer value
            answer = ""
            for key in ["answerBoolean", "answerString", "answerInteger", "answerDate"]:
                if key in condition:
                    answer = str(condition[key])
                    break
            if "answerCoding" in condition:
                coding = condition["answerCoding"]
                answer = coding.get("display") or coding.get("code", "")

            if operator == "exists":
                conditions.append(f"'{question}' {op_text}")
            else:
                conditions.append(f"'{question}' {op_text} '{answer}'")

        # Handle enableBehavior (all/any)
        behavior = " AND " if len(conditions) > 1 else ""
        return behavior.join(conditions)

    def _count_items(self, items: list[QuestionnaireItem]) -> tuple[int, int]:
        """Count total and required items recursively."""
        total = 0
        required = 0

        for item in items:
            # Skip display/group items from count
            if item.type not in [
                QuestionnaireItemType.DISPLAY,
                QuestionnaireItemType.GROUP,
            ]:
                total += 1
                if item.required:
                    required += 1

            # Count nested items
            if item.items:
                nested_total, nested_required = self._count_items(item.items)
                total += nested_total
                required += nested_required

        return total, required

    def _generate_markdown(
        self,
        title: str | None,
        description: str | None,
        items: list[QuestionnaireItem],
        required_count: int,
    ) -> str:
        """Generate markdown representation of the questionnaire."""
        lines = []

        # Title and description
        if title:
            lines.append(f"# {title}\n")
        if description:
            lines.append(f"{description}\n")

        lines.append(f"**Required fields:** {required_count}\n")
        lines.append("")

        # Generate item markdown
        lines.extend(self._items_to_markdown(items, level=1))

        return "\n".join(lines)

    def _items_to_markdown(
        self,
        items: list[QuestionnaireItem],
        level: int = 1,
    ) -> list[str]:
        """Convert items to markdown lines."""
        lines = []
        header_prefix = "#" * min(level + 1, 6)

        for i, item in enumerate(items, 1):
            # Skip display items in output
            if item.type == QuestionnaireItemType.DISPLAY:
                if item.text:
                    lines.append(f"*{item.text}*\n")
                continue

            # Item header
            required_marker = " *(required)*" if item.required else ""
            if item.type == QuestionnaireItemType.GROUP:
                lines.append(f"{header_prefix} {item.text or item.link_id}\n")
            else:
                type_hint = f" [{item.type.value}]"
                text = item.text or item.link_id
                lines.append(f"**{i}. {text}**{type_hint}{required_marker}\n")

            # Conditional display
            if item.enable_when:
                lines.append(f"  - *Show when:* {item.enable_when}")

            # Answer options
            if item.answer_options:
                lines.append("  - Options:")
                for opt in item.answer_options[:10]:  # Limit to 10 options
                    display = opt.display or opt.value
                    lines.append(f"    - {display}")
                if len(item.answer_options) > 10:
                    lines.append(f"    - ...and {len(item.answer_options) - 10} more")
                lines.append("")

            # Initial value
            if item.initial_value:
                lines.append(f"  - *Default:* {item.initial_value}")

            # Constraints
            if item.max_length:
                lines.append(f"  - *Max length:* {item.max_length}")
            if item.repeats:
                lines.append("  - *Can repeat*")
            if item.read_only:
                lines.append("  - *Read-only*")

            lines.append("")

            # Nested items
            if item.items:
                nested_lines = self._items_to_markdown(item.items, level + 1)
                lines.extend(nested_lines)

        return lines


def transform_questionnaire_bundle(
    bundle: dict[str, Any],
    raw_format: bool = False,
) -> QuestionnairePackageResult:
    """
    Transform a $questionnaire-package Bundle response.

    Args:
        bundle: FHIR Bundle from $questionnaire-package operation
        raw_format: If True, return raw bundle without transformation

    Returns:
        QuestionnairePackageResult with transformed questionnaires
    """
    logger.debug("Transforming questionnaire package bundle")

    result = QuestionnairePackageResult()

    # Return raw if requested
    if raw_format:
        result.raw_bundle = bundle
        return result

    # Handle OperationOutcome error
    if bundle.get("resourceType") == "OperationOutcome":
        result.raw_bundle = bundle
        return result

    # Extract resources from bundle
    entries = bundle.get("entry", [])

    questionnaires = []
    value_sets: dict[str, Any] = {}
    libraries: list[str] = []

    for entry in entries:
        resource = entry.get("resource", {})
        resource_type = resource.get("resourceType")

        if resource_type == "Questionnaire":
            questionnaires.append(resource)
        elif resource_type == "ValueSet":
            # Key by URL for lookup
            url = resource.get("url")
            if url:
                value_sets[url] = resource
        elif resource_type == "Library":
            # Store library reference
            lib_url = resource.get("url", resource.get("id"))
            if lib_url:
                libraries.append(lib_url)

    # Transform questionnaires with ValueSet context
    transformer = QuestionnaireTransformer(value_sets=value_sets)
    transformed = []
    for q in questionnaires:
        try:
            transformed.append(transformer.transform(q))
        except Exception as e:
            logger.warning(f"Failed to transform questionnaire {q.get('id')}: {e}")

    result.questionnaires = transformed
    result.value_sets = value_sets if value_sets else None
    result.libraries = libraries if libraries else None

    return result
