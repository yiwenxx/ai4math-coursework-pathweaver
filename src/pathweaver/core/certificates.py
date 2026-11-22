"""Domain-neutral Branch-and-Bound optimality proof-tree verifier."""
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CertificateOutcome:
    """Minimal outcome emitted by the domain-neutral BnB proof-tree kernel."""

    status: str  # "verified" | "rejected"
    verified_nodes: int = 0
    reason: str | None = None


def verify_bnb_proof_tree(
    tree: Mapping[str, Any],
    *,
    root_state: Any,
    apply_branch: Callable[[Any, Any, int], Any],
    lower_bound_fn: Callable[[Any], int],
    is_infeasible_fn: Callable[[Any], bool],
    evaluate_leaf_fn: Callable[[Any, Mapping[str, Any]], int],
    incumbent_objective: int,
    max_nodes: int = 250_000,
) -> CertificateOutcome:
    """Independently verify an exhaustive binary Branch-and-Bound optimality proof tree.

    Internal ``branch`` nodes must cover both ``include`` (1) and ``exclude`` (0).
    Leaves must be proved ``infeasible``, ``pruned_by_bound`` (``lb >= incumbent``),
    or ``incumbent`` (feasible value >= incumbent, with >=1 leaf attaining it exactly).
    """
    if not isinstance(tree, Mapping):
        return CertificateOutcome(status="rejected", reason="Proof tree must be an object")

    visited = 0
    matched_incumbent = False
    stack: list[tuple[Mapping[str, Any], Any]] = [(tree, root_state)]
    try:
        while stack:
            node, state = stack.pop()
            visited += 1
            if visited > max_nodes:
                raise ValueError(f"Proof tree exceeds node limit ({max_nodes})")
            if not isinstance(node, Mapping):
                raise ValueError("Proof node must be a mapping")
            kind = node.get("kind")
            if kind == "branch":
                var, left, right = node.get("var"), node.get("include"), node.get("exclude")
                if var is None or left is None or right is None:
                    raise ValueError("Branch node must specify var, include, and exclude children")
                stack.append((left, apply_branch(state, var, 1)))
                stack.append((right, apply_branch(state, var, 0)))
            elif kind == "infeasible":
                if not is_infeasible_fn(state):
                    raise ValueError("Leaf marked infeasible is not independently infeasible")
            elif kind == "pruned_by_bound":
                lb = lower_bound_fn(state)
                if type(lb) is not int or lb < incumbent_objective:
                    raise ValueError(f"Pruned leaf lower bound {lb} < incumbent {incumbent_objective}")
            elif kind == "incumbent":
                leaf_val = evaluate_leaf_fn(state, node)
                if type(leaf_val) is not int or leaf_val < incumbent_objective:
                    raise ValueError(f"Incumbent leaf value {leaf_val} < declared incumbent {incumbent_objective}")
                if leaf_val == incumbent_objective:
                    matched_incumbent = True
            else:
                raise ValueError(f"Unknown proof-tree node kind: {kind!r}")

        if not matched_incumbent:
            raise ValueError("Proof tree has no leaf attaining the declared incumbent objective")
    except (ValueError, TypeError, KeyError) as error:
        return CertificateOutcome(status="rejected", reason=str(error))

    return CertificateOutcome(status="verified", verified_nodes=visited)
