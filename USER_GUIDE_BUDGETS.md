# Budget-Aware Assignment Optimization - User Guide

## Input Format

The Create page now supports an **optional** 4th column for agent budgets.

### Format
```
from_node to_node weight [optional_budget]
```

### Examples

#### Example 1: Simple assignment (no budgets)
```
A B 2.5
B C 3.0
C A 1.5
```
Result: Minimizes assignment cost without budget constraints.

#### Example 2: Assignment with budgets
```
A B 2.5 50
B C 3.0 75
C A 1.5 40
```
Result: Minimizes assignment cost while penalizing budget violations:
- Agent A has a cost budget of 50
- Agent B has a cost budget of 75  
- Agent C has a cost budget of 40

#### Example 3: Mixed (some with budgets, some without)
```
A B 2.5 50
B C 3.0
C A 1.5 40
```
Result: Agents A and C have budgets; agent B has no constraint.

## How It Works

When you specify a budget for an agent:

1. **During optimization**: The QAOA solver adds penalty terms to discourage assigning more cost than the budget
2. **Penalty weight**: Budget violations are penalized with a weight of **20.0** (same as in assignmentprob.py)
3. **Output**: The optimized assignment respects both capacity constraints AND budget constraints when feasible

## Understanding the Output

- **Feasible**: ✓ means all constraints are satisfied (tasks done by one agent, budgets respected)
- **Assignment cost**: Total cost of the assigned tasks
- **Assignment map**: Shows which task is assigned to which agent

### Example Output
```
Optimization complete
Feasible: true
Assignment cost: 12.5
Assignment map:
{
  "task1": "AgentA",
  "task2": "AgentB",
  "task3": "AgentC"
}
```

## Behind the Scenes: Algorithm Update

The solver now uses the **assignment_with_budgets** algorithm from `assignmentprob.py`:

1. Creates a QUBO formulation with:
   - **Objective**: Minimize total assignment cost
   - **Constraint 1**: Each task done by exactly one agent
   - **Constraint 2**: Total task cost ≤ agent capacity (hard constraint)
   - **Constraint 3**: Total task cost ≈ agent budget (soft penalty)

2. Uses QAOA to find the best quantum solution

3. Returns both the optimized graph and a detailed summary

## Tips

- **Large budgets**: If you set a budget larger than the sum of all edge weights, the budget constraint becomes non-binding
- **Small budgets**: Very restrictive budgets may force the solver into infeasible regions
- **No budgets**: Leave the 4th column blank to ignore budget constraints entirely
- **Comments**: Lines starting with `#` are ignored (useful for documentation)

## Example Workflow

```
# Task assignment problem
# From  To    Weight  Budget
AgentA TaskX  3.5     50
AgentA TaskY  2.0     50
AgentB TaskX  4.0     45
AgentB TaskZ  2.5     45
AgentC TaskY  1.5     40
AgentC TaskZ  3.0     40
```

Click **Draw** to:
1. Show the input graph in the left panel
2. Run the QAOA solver with budget constraints
3. Display the optimized assignment graph in the right panel
4. Show the optimization summary below the graph

