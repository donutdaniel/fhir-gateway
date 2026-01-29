"""
MCP Prompts for FHIR Gateway.

Workflow templates that guide users through common FHIR operations.
"""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from pydantic import Field


def register_prompts(mcp: FastMCP) -> None:
    """Register MCP prompts."""

    @mcp.prompt(
        description="Guide through checking prior authorization requirements for a procedure."
    )
    async def prior_auth_workflow(
        patient_id: Annotated[str, Field(description="FHIR Patient resource ID")],
        procedure_code: Annotated[str, Field(description="CPT/HCPCS procedure code")],
    ) -> str:
        """Template for prior auth workflow."""
        return f"""# Prior Authorization Check Workflow

## Step 1: Find Patient's Coverage
Search for active coverage:
```
search(platform_id="<platform>", resource_type="Coverage", params={{"patient": "{patient_id}", "status": "active"}})
```

## Step 2: Check Authorization Requirements
```
check_prior_auth(platform_id="<platform>", patient_id="{patient_id}", coverage_id="<from_step_1>", procedure_code="{procedure_code}")
```

## Step 3: Get Documentation (if required)
```
get_questionnaire_package(platform_id="<platform>", coverage_id="<coverage_id>")
```

## Outcomes
- **required**: Prior auth needed before procedure
- **not-required**: No auth needed
- **conditional**: May be needed based on circumstances
"""

    @mcp.prompt(description="Get a comprehensive patient summary using $everything operation.")
    async def patient_summary_workflow(
        patient_id: Annotated[str, Field(description="FHIR Patient resource ID")],
    ) -> str:
        """Template for patient summary workflow."""
        return f"""# Patient Summary Workflow

## Step 1: Read Patient Demographics
```
read(platform_id="<platform>", resource_type="Patient", resource_id="{patient_id}")
```

## Step 2: Get All Patient Data
```
execute_operation(platform_id="<platform>", resource_type="Patient", resource_id="{patient_id}", operation="$everything")
```

## Key Resources to Review
- **Condition**: Active problems/diagnoses
- **MedicationRequest**: Current medications
- **AllergyIntolerance**: Allergies and intolerances
- **Observation**: Vitals, labs, assessments
- **Encounter**: Recent visits
"""

    @mcp.prompt(description="Authenticate with a platform and then query data.")
    async def auth_and_query_workflow(
        platform_id: Annotated[str, Field(description="Platform identifier")],
    ) -> str:
        """Template for authentication and query workflow."""
        return f"""# Authentication and Query Workflow

## Step 1: Check if Already Authenticated
```
get_auth_status(session_id="<your_session>", platform_id="{platform_id}")
```

## Step 2: Start Authentication (if needed)
```
start_auth(platform_id="{platform_id}", session_id="<your_session>")
```
Direct the user to the `authorization_url` returned.

## Step 3: Wait for Login to Complete
```
wait_for_auth(platform_id="{platform_id}", session_id="<your_session>", timeout=300)
```

## Step 4: Query Data
Now you can make FHIR requests. The token is automatically used:
```
search(platform_id="{platform_id}", resource_type="Patient", params={{"name": "Smith"}})
```
"""
