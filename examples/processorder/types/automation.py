from processorder.modules.model import model

from processorder.project.processorder import project

automation_job = project.string_type(
    "AutomationJob",
    use_alias=False,
    description="Automation job payload and result.",
    public_type=True,
    module=model,
)
