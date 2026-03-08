import math
import matplotlib.pyplot as plt
import numpy as np
import scipy
from tqdm import tqdm

from classiq import *

LAMBDA = 20
TASKLAMBDA = 15

NUM_LAYERS = 5
NUM_SHOTS = 1000
MAX_ITERATIONS = 60

agents = 4
tasks = 3

qbits = agents*tasks
budgets = [10, 6, 12, 11]
weights = [
    [8, 4, 7],
    [5, 2, 3],
    [9, 6, 7],
    [9, 4, 8]
]


def object_func(x: QArray[QBit, qbits]):
    obj = 0
    budget_penalty = 0
    task_penalty = 0

    #objective and budget
    for i in range(agents):
        agent_cost = 0
        for j in range(tasks):
            qbit_idx = tasks*i + j
            agent_cost = agent_cost + weights[i][j] * x[qbit_idx]
        obj = obj + agent_cost
        budget_penalty = budget_penalty + (agent_cost - budgets[i])**2
    
    #task done by one person only
    for j in range(tasks):
        task_sum = 0
        for i in range(agents):
            qbit_idx = tasks*i + j
            task_sum = task_sum + x[qbit_idx]

        task_penalty = task_penalty + (task_sum - 1)**2
    
    return obj + budget_penalty * LAMBDA + TASKLAMBDA * task_penalty

def cost(x: QArray[QBit, qbits]):
    return object_func(x)

@qfunc
def initial_state(x: QArray[QBit, qbits]):
    prepare_dicke_state(tasks, x)

@qfunc
def cost_layer(gamma: CReal, x: QArray[QBit, qbits]):
    phase(cost(x), gamma)

@qfunc
def mixer_layer(beta: CReal, x: QArray):
    x_lsbs = QNum(size=x.len - 1)
    x_msb = QBit()
    within_apply(
        lambda: (invert(lambda: initial_state(x)), bind(x, [x_lsbs, x_msb]), X(x_msb)),
        lambda: control(x_lsbs == 0, lambda: RZ(-1.0 / np.pi * beta, x_msb)),
    )
    
@qfunc
def qaoa_ansatz(
    cost_layer: QCallable[CReal, QArray],
    mixer_layer: QCallable[CReal, QArray],
    gammas: CArray[CReal],
    betas: CArray[CReal],
    qba: QArray,
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
    qaoa_ansatz(cost_layer, mixer_layer, gammas, betas, x)

qprog_gmqaoa = synthesize(main)
show(qprog_gmqaoa)



initial_params = (
    np.concatenate((np.linspace(0, 1, NUM_LAYERS), np.linspace(1, 0, NUM_LAYERS)))
    * math.pi
)

cost_trace = []

def evaluate_params(es, params):
    cost_estimation = es.estimate_cost(
        cost_func=lambda state: cost(state["x"]),
        parameters={"params": params.tolist()},
    )
    cost_trace.append(cost_estimation)
    return cost_estimation

es = ExecutionSession(qprog_gmqaoa, execution_preferences=ExecutionPreferences(num_shots=NUM_SHOTS))

with tqdm(total=MAX_ITERATIONS, desc="Optimization Progress", leave=True) as pbar:
    def progress_bar(xk: np.ndarray) -> None:
        pbar.update(1)

    result = scipy.optimize.minimize(
        fun=lambda params: evaluate_params(es, params),
        x0=initial_params,
        method="COBYLA",
        options={"maxiter": MAX_ITERATIONS},
        callback=progress_bar,
    )

final_params = result.x.tolist()
print(f"Optimized parameters: {final_params}")

plt.plot(cost_trace)
plt.xlabel("Iterations")
plt.ylabel("Estimated cost")
plt.title("Cost convergence")
plt.show()

res = es.sample({"params": final_params})
es.close()

print("Top sampled solutions:")
for sampled in res.parsed_counts:
    x = sampled.state["x"]
    prob = sampled.shots / NUM_SHOTS
    val = cost(x)
    print(f"solution={x} probability={prob:.3f} cost={val}")
