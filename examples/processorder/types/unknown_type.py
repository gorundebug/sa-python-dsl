from sa_dsl import LocalType

from processorder.project.processorder import project

unknown_type = project.int_type(
    'UnknownType',
    use_alias=False,
    description='',
    public_type=False,
    module=LocalType(),
)
