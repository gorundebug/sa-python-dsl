from processorder.project.processorder import project

default_pool = project.pool(
    "Default Pool",
    executors_count=2,
)
