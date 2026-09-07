from sa_dsl import ROOT_PACKAGE

from processorder.project.processorder import project

analytics_key = project.string_type(
    'AnalyticsKey',
    use_alias=False,
    description='Correlation key used by the canonical analytics joins.',
    public_type=False,
    package=ROOT_PACKAGE,
)
