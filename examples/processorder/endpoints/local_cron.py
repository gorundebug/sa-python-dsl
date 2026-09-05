from processorder.connectors.local_cron import local_cron

from processorder.packages.cron import cron_package

from sa_dsl import (
    CronSchedule,
    Function,
    ScheduleMissedRunPolicy,
    ScheduleOverlapPolicy,
)

analytics_schedule = local_cron.schedule(
    "Analytics Schedule",
    function=Function(
        name="AnalyticsSchedule",
        package=cron_package,
        description="Create an analytics job message identifying the local scheduled firing.\n",
        public=False,
    ),
    enabled=True,
    tracing_enabled=False,
    trigger=CronSchedule(expression="*/5 * * * *", timezone="UTC", overlap_policy=ScheduleOverlapPolicy.SKIP, missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE),
)

local_schedule = local_cron.schedule(
    "Local Schedule",
    function=Function(
        name="LocalSchedule",
        package=cron_package,
        description="Create a job message identifying the local scheduled firing.\n",
        public=False,
    ),
    enabled=True,
    tracing_enabled=False,
    trigger=CronSchedule(expression="*/5 * * * *", timezone="UTC", overlap_policy=ScheduleOverlapPolicy.SKIP, missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE),
)
