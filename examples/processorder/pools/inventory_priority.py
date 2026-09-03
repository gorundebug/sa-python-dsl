from processorder.project.processorder import project

inventory_priority_workers = project.pool(
    "Inventory Priority Workers",
    executors_count=2,
)
