import math
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np
import scipy.optimize
from tqdm import tqdm

from classiq import *


def classical_qubo_value(bitlist, h, J):
    xv = np.array(bitlist, dtype=float)
    val = float(np.dot(h, xv))
    for i in range(len(xv)):
        for j in range(i + 1, len(xv)):
            val += J[i][j] * xv[i] * xv[j]
    return float(val)


def bounded_binary_weights(capacity: int):
    if capacity < 0:
        raise ValueError("Capacity must be nonnegative.")
    if capacity == 0:
        return []

    weights = []
    total = 0
    power = 1
    while total + power < capacity:
        weights.append(power)
        total += power
        power *= 2
    weights.append(capacity - total)
    return weights


def assignment_qubo_from_edges(edges, capacities, task_penalty=None, capacity_penalty=None):
    """
    edges format:
        (agent, task, assignment_cost)

    capacities format:
        {agent: max_number_of_tasks}

    Binary variable:
        x_(agent,task) = 1 if task is assigned to agent

    Objective:
        minimize total assignment cost

    Constraints:
        1) every task assigned exactly once
        2) each agent gets at most capacities[agent] tasks
    """
    if not edges:
        raise ValueError("The edge list is empty.")
    if not isinstance(capacities, dict):
        raise TypeError("capacities must be a dict: {agent: capacity}")

    for agent, cap in capacities.items():
        if int(cap) != cap or cap < 0:
            raise ValueError(f"Capacity for agent {agent!r} must be a nonnegative integer.")
    capacities = {agent: int(cap) for agent, cap in capacities.items()}

    tasks = sorted({task for (_, task, _) in edges}, key=str)
    agents = sorted(capacities.keys(), key=str)

    for edge in edges:
        if len(edge) != 3:
            raise ValueError("Each edge must be (agent, task, assignment_cost).")
        agent, task, cost = edge
        if agent not in capacities:
            raise ValueError(f"Agent {agent!r} appears in edges but not in capacities.")

    max_abs_cost = max(abs(float(cost)) for (_, _, cost) in edges)
    scale = max(1.0, max_abs_cost, float(len(tasks)))
    if task_penalty is None:
        task_penalty = 10.0 * scale + 1.0
    if capacity_penalty is None:
        capacity_penalty = 10.0 * scale + 1.0

    var_meta = []
    task_to_assignment_vars = defaultdict(list)
    agent_capacity_terms = defaultdict(list)

    # Assignment variables
    for agent, task, cost in edges:
        idx = len(var_meta)
        var_meta.append(
            {
                "kind": "x",
                "agent": agent,
                "task": task,
                "cost": float(cost),
            }
        )
        task_to_assignment_vars[task].append(idx)
        agent_capacity_terms[agent].append((idx, 1))  # every assignment counts as 1

    for task in tasks:
        if len(task_to_assignment_vars[task]) == 0:
            raise ValueError(f"Task {task!r} has no feasible assignment edges.")

    # Slack variables for capacities:
    #   sum_t x_(a,t) + slack_a = capacity_a
    slack_info = defaultdict(list)
    for agent in agents:
        weights = bounded_binary_weights(capacities[agent])
        for bit_pos, weight in enumerate(weights):
            idx = len(var_meta)
            var_meta.append(
                {
                    "kind": "s",
                    "agent": agent,
                    "bit": bit_pos,
                    "weight": weight,
                }
            )
            agent_capacity_terms[agent].append((idx, weight))
            slack_info[agent].append((idx, weight))

    nvars = len(var_meta)
    h = np.zeros(nvars, dtype=float)
    J = np.zeros((nvars, nvars), dtype=float)

    def add_quadratic(i, j, value):
        if i < j:
            J[i][j] += value
        else:
            J[j][i] += value

    # Objective: sum cost * x
    for i, meta in enumerate(var_meta):
        if meta["kind"] == "x":
            h[i] += meta["cost"]

    # Task constraints: A * (sum_a x_(a,t) - 1)^2
    for task in tasks:
        idxs = task_to_assignment_vars[task]
        for i in idxs:
            h[i] += -task_penalty
        for p in range(len(idxs)):
            for q in range(p + 1, len(idxs)):
                add_quadratic(idxs[p], idxs[q], 2.0 * task_penalty)

    # Capacity constraints with slack:
    # B * (sum_t x_(a,t) + slack_a - C_a)^2
    for agent in agents:
        cap = capacities[agent]
        terms = agent_capacity_terms[agent]

        for idx, coeff in terms:
            h[idx] += capacity_penalty * (coeff * coeff - 2.0 * cap * coeff)

        for p in range(len(terms)):
            i, ci = terms[p]
            for q in range(p + 1, len(terms)):
                j, cj = terms[q]
                add_quadratic(i, j, 2.0 * capacity_penalty * ci * cj)

    problem = {
        "tasks": tasks,
        "agents": agents,
        "capacities": capacities,
        "var_meta": var_meta,
        "task_penalty": task_penalty,
        "capacity_penalty": capacity_penalty,
        "slack_info": slack_info,
    }
    return h.tolist(), J.tolist(), problem


def decode_assignment_solution(bitlist, problem):
    tasks = problem["tasks"]
    capacities = problem["capacities"]
    var_meta = problem["var_meta"]

    assignments_by_task = defaultdict(list)
    load_by_agent = defaultdict(int)
    slack_by_agent = defaultdict(int)
    selected_edges = []
    assignment_cost = 0.0

    for bit, meta in zip(bitlist, var_meta):
        if not bit:
            continue

        if meta["kind"] == "x":
            agent = meta["agent"]
            task = meta["task"]
            cost = meta["cost"]

            assignments_by_task[task].append(agent)
            load_by_agent[agent] += 1
            assignment_cost += cost
            selected_edges.append((agent, task, cost))

        elif meta["kind"] == "s":
            slack_by_agent[meta["agent"]] += meta["weight"]

    exactly_one_per_task = all(len(assignments_by_task[t]) == 1 for t in tasks)
    capacity_ok = all(load_by_agent[a] <= capacities[a] for a in capacities)
    encoded_capacity_equalities_hold = all(
        load_by_agent[a] + slack_by_agent[a] == capacities[a] for a in capacities
    )

    assignment_map = {}
    for task in tasks:
        if len(assignments_by_task[task]) == 1:
            assignment_map[task] = assignments_by_task[task][0]
        else:
            assignment_map[task] = None

    return {
        "assignment_map": assignment_map,
        "selected_edges": selected_edges,
        "assignment_cost": assignment_cost,
        "load_by_agent": dict(load_by_agent),
        "slack_by_agent": dict(slack_by_agent),
        "exactly_one_per_task": exactly_one_per_task,
        "capacity_ok": capacity_ok,
        "encoded_capacity_equalities_hold": encoded_capacity_equalities_hold,
        "feasible": exactly_one_per_task and capacity_ok,
    }


def build_optimized_assignment_graph(problem, edges, best_solution):
    decoded = best_solution["decoded"]
    selected_pairs = {(a, t) for (a, t, _w) in decoded.get("selected_edges", [])}

    nodes = []
    for agent in problem["agents"]:
        nodes.append(
            {
                "id": str(agent),
                "type": "agent",
                "capacity": int(problem["capacities"][agent]),
                "assigned": int(decoded.get("load_by_agent", {}).get(agent, 0)),
            }
        )

    for task in problem["tasks"]:
        nodes.append(
            {
                "id": str(task),
                "type": "task",
                "assigned_to": decoded.get("assignment_map", {}).get(task),
            }
        )

    graph_edges = []
    for agent, task, weight in edges:
        graph_edges.append(
            {
                "source": str(agent),
                "target": str(task),
                "weight": float(weight),
                "selected": (agent, task) in selected_pairs,
            }
        )

    return {
        "nodes": nodes,
        "edges": graph_edges,
        "summary": {
            "feasible": bool(decoded.get("feasible", False)),
            "assignment_cost": float(decoded.get("assignment_cost", 0.0)),
            "qubo_cost": float(best_solution.get("qubo_cost", 0.0)),
            "probability": float(best_solution.get("probability", 0.0)),
            "assignment_map": decoded.get("assignment_map", {}),
            "load_by_agent": decoded.get("load_by_agent", {}),
        },
    }


def solve_assignment_with_qaoa(
    edges,
    capacities,
    num_layers=3,
    num_shots=1000,
    max_iterations=60,
    task_penalty=None,
    capacity_penalty=None,
    show_circuit=False,
    plot_trace=True,
):
    h, J, problem = assignment_qubo_from_edges(
        edges=edges,
        capacities=capacities,
        task_penalty=task_penalty,
        capacity_penalty=capacity_penalty,
    )

    qbits = len(h)
    NUM_LAYERS = int(num_layers)

    def object_func(x: QArray[QBit, qbits]):
        obj = 0
        for i in range(qbits):
            obj = obj + (h[i] * x[i])
        for i in range(qbits):
            for j in range(i + 1, qbits):
                if J[i][j] != 0:
                    obj = obj + (J[i][j] * x[i] * x[j])
        return obj

    def cost(x: QArray[QBit, qbits]):
        return object_func(x)

    @qfunc
    def initial_state(x: QArray[QBit, qbits]):
        repeat(x.len, lambda i: H(x[i]))

    @qfunc
    def cost_layer(gamma: CReal, x: QArray[QBit, qbits]):
        phase(cost(x), gamma)

    @qfunc
    def x_mixer(beta: CReal, x: QArray[QBit, qbits]):
        repeat(x.len, lambda i: RX(2 * beta, x[i]))

    @qfunc
    def qaoa_ansatz(
        cost_layer: QCallable[CReal, QArray],
        mixer_layer: QCallable[CReal, QArray],
        gammas: CArray[CReal],
        betas: CArray[CReal],
        qba: QArray[QBit, qbits],
    ):
        repeat(
            betas.len,
            lambda i: [
                cost_layer(gammas[i], qba),
                mixer_layer(betas[i], qba),
            ],
        )

    @qfunc
    def main(
        params: CArray[CReal, NUM_LAYERS * 2],
        x: Output[QArray[QBit, qbits]],
    ):
        allocate(x)
        gammas = params[0:NUM_LAYERS]
        betas = params[NUM_LAYERS : 2 * NUM_LAYERS]
        initial_state(x)
        qaoa_ansatz(cost_layer, x_mixer, gammas, betas, x)

    qprog = synthesize(main)
    if show_circuit:
        show(qprog)

    initial_params = (
        np.concatenate(
            (
                np.linspace(0.0, 1.0, NUM_LAYERS),
                np.linspace(1.0, 0.0, NUM_LAYERS),
            )
        )
        * math.pi
    )

    cost_trace = []

    def evaluate_params(es, params):
        est = es.estimate_cost(
            cost_func=lambda state: classical_qubo_value(state["x"], h, J),
            parameters={"params": params.tolist()},
        )
        cost_trace.append(est)
        return est

    es = ExecutionSession(
        qprog,
        execution_preferences=ExecutionPreferences(num_shots=num_shots),
    )

    with tqdm(total=max_iterations, desc="Optimization Progress", leave=True) as pbar:
        def progress_bar(_xk: np.ndarray):
            pbar.update(1)

        result = scipy.optimize.minimize(
            fun=lambda params: evaluate_params(es, params),
            x0=initial_params,
            method="COBYLA",
            options={"maxiter": max_iterations},
            callback=progress_bar,
        )

    final_params = result.x.tolist()
    print(f"\nOptimized parameters: {final_params}")

    if plot_trace:
        plt.figure(figsize=(7, 4))
        plt.plot(cost_trace)
        plt.xlabel("Iterations")
        plt.ylabel("Estimated QUBO cost")
        plt.title("QAOA parameter optimization")
        plt.tight_layout()
        plt.show()

    sample_res = es.sample({"params": final_params})
    es.close()

    sampled_solutions = []
    for sampled in sample_res.parsed_counts:
        bitstring = list(sampled.state["x"])
        qubo_cost = classical_qubo_value(bitstring, h, J)
        decoded = decode_assignment_solution(bitstring, problem)
        sampled_solutions.append(
            {
                "bitstring": bitstring,
                "probability": sampled.shots / num_shots,
                "qubo_cost": qubo_cost,
                "decoded": decoded,
            }
        )

    feasible = [s for s in sampled_solutions if s["decoded"]["feasible"]]
    if feasible:
        feasible.sort(key=lambda s: (s["decoded"]["assignment_cost"], -s["probability"]))
        best_solution = feasible[0]
    else:
        sampled_solutions.sort(key=lambda s: (s["qubo_cost"], -s["probability"]))
        best_solution = sampled_solutions[0]

    print("\nTop sampled solutions:")
    sampled_solutions_sorted = sorted(
        sampled_solutions,
        key=lambda s: (-s["probability"], s["qubo_cost"])
    )

    for s in sampled_solutions_sorted[:10]:
        dec = s["decoded"]
        print(
            f"bitstring={s['bitstring']} "
            f"prob={s['probability']:.3f} "
            f"qubo={s['qubo_cost']:.3f} "
            f"assign_cost={dec['assignment_cost']:.3f} "
            f"feasible={dec['feasible']} "
            f"assignment={dec['assignment_map']}"
        )

    print("\nBest interpreted solution:")
    print(f"  feasible        = {best_solution['decoded']['feasible']}")
    print(f"  assignment_cost = {best_solution['decoded']['assignment_cost']}")
    print(f"  qubo_cost       = {best_solution['qubo_cost']}")
    print(f"  assignment      = {best_solution['decoded']['assignment_map']}")
    print(f"  load_by_agent   = {best_solution['decoded']['load_by_agent']}")
    print(f"  slack_by_agent  = {best_solution['decoded']['slack_by_agent']}")

    optimized_graph = build_optimized_assignment_graph(problem, edges, best_solution)
    optimized_graph["optimization"] = {
        "final_params": [float(x) for x in final_params],
        "cost_trace": [float(x) for x in cost_trace],
    }
    return optimized_graph


if __name__ == "__main__":
    # edges = (agent, task, assignment_cost)
    fixededges = [
  [
    "anish",
    "smelly",
    1
  ],
  [
    "anish",
    "fat",
    1
  ],
  [
    "anish",
    "owen",
    1
  ],
  [
    "clinton",
    "owen",
    1
  ],
  [
    "clinton",
    "asshole",
    1
  ],
  [
    "owen",
    "cute",
    1
  ]
]

    capacities = {
    }

    for edge in fixededges:
        node1 = edge[0]
        node2 = edge[1]
        if node1 not in capacities:
            capacities[node1] = 0
        if node2 not in capacities:
            capacities[node2] = 0
        capacities[node1] += 1
        capacities[node2] += 1


    for edge in fixededges:
        node1 = edge[0]
        node2 = edge[1]
        if node1 not in capacities:
            capacities[node1] = 0
        if node2 not in capacities:
            capacities[node2] = 0
        capacities[node1] += 1
        capacities[node2] += 1

    result = solve_assignment_with_qaoa(
        edges=fixededges,
        capacities=capacities,
        num_layers=3,
        num_shots=1000,
        max_iterations=60,
        task_penalty=30.0,
        capacity_penalty=30.0,
        show_circuit=False,
        plot_trace=True,
    )

