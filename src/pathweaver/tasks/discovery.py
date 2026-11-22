"""Explicit trusted TaskPack registry for discovery; never load candidate plugins."""


def discovery_task(task_id):
    if task_id == "eda_assignment":
        from pathweaver.tasks.eda_assignment.discovery import EdaDiscoveryTask
        return EdaDiscoveryTask()
    if task_id == "weighted_vertex_cover":
        from pathweaver.tasks.weighted_vertex_cover.discovery import WeightedVertexCoverDiscoveryTask
        return WeightedVertexCoverDiscoveryTask()
    if task_id == "jsp158_coloring":
        from pathweaver.tasks.jsp158_coloring.discovery import Jsp158DiscoveryTask
        return Jsp158DiscoveryTask()
    if task_id == "lean_proof":
        from pathweaver.tasks.lean_proof.discovery import LeanProofDiscoveryTask
        return LeanProofDiscoveryTask()
    raise ValueError(f"No implemented discovery adapter for task {task_id!r}")
