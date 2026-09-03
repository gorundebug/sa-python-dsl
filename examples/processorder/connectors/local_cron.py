from processorder.project.processorder import project

local_cron = project.cron_connector(
    "Local Cron",
)
