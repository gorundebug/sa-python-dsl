from sa_dsl import (
    CronSchedule,
    Function,
    ScheduleMissedRunPolicy,
    ScheduleOverlapPolicy,
)

from processorder.connectors.local_cron import connector_local_cron
from processorder.packages.cron import cron_package

endpoint_analytics_schedule = connector_local_cron.schedule(
    'Analytics Schedule',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='AnalyticsSchedule',
        package=cron_package,
        public=False,
        description='Create an analytics job message identifying the local scheduled firing.\n',
    ),
    trigger=CronSchedule(expression='*/5 * * * *', timezone='UTC', overlap_policy=ScheduleOverlapPolicy.SKIP, missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE),
)

endpoint_local_schedule = connector_local_cron.schedule(
    'Local Schedule',
    enabled=True,
    tracing_enabled=False,
    function=Function(
        name='LocalSchedule',
        package=cron_package,
        public=False,
        description='Create a job message identifying the local scheduled firing.\n',
    ),
    trigger=CronSchedule(expression='*/5 * * * *', timezone='UTC', overlap_policy=ScheduleOverlapPolicy.SKIP, missed_run_policy=ScheduleMissedRunPolicy.FIRE_ONCE),
)
