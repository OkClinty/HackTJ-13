import math
import matplotlib.pyplot as plt
import numpy as np
import scipy
from tqdm import tqdm

from classiq import *

n = 4
k = 2

qbits = n

h = [5.0, 6.0, 3.0, 7.0]

J = [
    [0.0, 1.6, 1.7, -0.5],
    [1.6, 0.0, 0.5, 0.2],
    [1.7, 0.5, 0.0, -0.5],
    [-0.5, 0.2, -0.5, 0.0],
]

def classical_qubo_value(bitlist, h, J):
    xv = np.array(bitlist, dtype=float)
    val = np.dot(h, xv)
    for i in range(len(xv)):
        for j in range(i + 1, len(xv)):
            val += J[i][j] * xv[i] * xv[j]
    return float(val)

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
    prepare_dicke_state(k, x[0:qbits])

@qfunc
def cost_layer(gamma: CReal, x: QArray[QBit, qbits]):
    phase(cost(x), gamma)

@qfunc
def grover_mixer(beta: CReal, x: QArray[QBit, qbits]):
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
    qba: QArray[QBit, qbits],
):
    repeat(
        betas.len,
        lambda i: [
            cost_layer(gammas[i], qba),
            mixer_layer(betas[i], qba),
        ],
    )

NUM_LAYERS = 3

@qfunc
def main(
    params: CArray[CReal, NUM_LAYERS * 2],
    x: Output[QArray[QBit, qbits]],
):
    allocate(x)
    gammas = params[0:NUM_LAYERS]
    betas = params[NUM_LAYERS : 2 * NUM_LAYERS]
    initial_state(x)
    qaoa_ansatz(cost_layer, grover_mixer, gammas, betas, x)

qprog_gmqaoa = synthesize(main)
show(qprog_gmqaoa)

NUM_SHOTS = 1000
MAX_ITERATIONS = 60

initial_params = (
    np.concatenate((np.linspace(0, 1, NUM_LAYERS), np.linspace(1, 0, NUM_LAYERS)))
    * math.pi
)

cost_trace = []

def evaluate_params(es, params):
    cost_estimation = es.estimate_cost(
        cost_func=lambda state: classical_qubo_value(state["x"], h, J),
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

print("Top sampled solutions (fixed weight k={}):".format(k))
for sampled in res.parsed_counts:
    x = sampled.state["x"]
    prob = sampled.shots / NUM_SHOTS
    val = classical_qubo_value(x, h, J)
    print(f"solution={x} probability={prob:.3f} cost={val}")
