#!/usr/bin/env python
import sys
sys.path.insert(0, r'G:\My Drive\Fun\Projects\qc\HackTJ-13')

from app import parse_edges_text, fixedges

# Test 1: Without budgets
edges_text_1 = """A B 2.5
B C 3.0
C A 1.5"""

parsed_1, budgets_1 = parse_edges_text(edges_text_1)
print("Test 1 - Without budgets:")
print(f"  Edges: {parsed_1}")
print(f"  Budgets: {budgets_1}")
print()

# Test 2: With budgets
edges_text_2 = """A B 2.5 50
B C 3.0 75
C A 1.5 40"""

parsed_2, budgets_2 = parse_edges_text(edges_text_2)
print("Test 2 - With budgets:")
print(f"  Edges: {parsed_2}")
print(f"  Budgets: {budgets_2}")
print()

# Test 3: Mixed (some with budgets, some without)
edges_text_3 = """A B 2.5 50
B C 3.0
C A 1.5 40"""

parsed_3, budgets_3 = parse_edges_text(edges_text_3)
print("Test 3 - Mixed:")
print(f"  Edges: {parsed_3}")
print(f"  Budgets: {budgets_3}")
print()

# Test 4: fixedges conversion
fixed = fixedges(parsed_2)
print("Test 4 - Converted to tuples:")
print(f"  Fixed edges: {fixed}")

