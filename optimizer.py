from models import *
from estimator import *


def create_scan_plan(table):
    return PlanNode(
        operation="SCAN",
        algorithm="Full Scan",
        cost=table.block_count,
        output_rows=table.row_count,
        output_blocks=table.block_count,
        children=[],
        details=table.name
    )


def optimize_selection(table, condition, child_plan=None):
    attribute_name = condition.left.split(".")[-1]
    attribute = table.get_attribute(attribute_name)

    estimate = estimate_selection(table, attribute, condition.operator)

    best = min(estimate.estimates, key=lambda x: x.cost)

    return PlanNode(
        operation="SELECTION",
        algorithm=best.algorithm,
        cost=best.cost,
        output_rows=estimate.output_rows,
        output_blocks=estimate.output_blocks,
        children=[] if child_plan is None else [child_plan],
        details=(condition.left + condition.operator + condition.right)
    )


def optimize_join(left_plan, right_plan, left_table, left_attr, right_table, right_attr, buffer_blocks):
    estimate = estimate_join(left_plan, right_plan, left_table, left_attr, right_table, right_attr, buffer_blocks)

    best = min(estimate.estimates, key=lambda x: x.cost)

    return PlanNode(
        operation="JOIN",
        algorithm=best.algorithm,
        cost=best.cost,
        output_rows=estimate.output_rows,
        output_blocks=estimate.output_blocks,
        children=[left_plan, right_plan],
        details=(left_table.name + "." + left_attr.name + "=" + right_table.name + "." + right_attr.name)
    )


def split_conditions(query):
    selection_conditions = []
    join_conditions = []

    for condition in query.where:
        if condition.is_join():
            join_conditions.append(condition)
        else:
            selection_conditions.append(condition)

    return selection_conditions, join_conditions


def apply_selections(table, conditions):
    plan = create_scan_plan(table)
    for condition in conditions:
        plan = optimize_selection(table, condition, plan)
    return plan


def calculate_total_cost(node):
    total = node.cost

    for child in node.children:
        total += calculate_total_cost(child)

    return total


def create_execution_plan(root):
    return ExecutionPlan(
        root=root,
        total_cost=calculate_total_cost(root)
    )


def optimize_query(query, schema):
    tables = []
    # uzimamo prvo sve tabele koje se pojavljuju u upitu
    for table_name in query.from_tables:
        tables.append(
            schema.get_table(table_name)
        )

    selection_conditions, join_conditions = split_conditions(query)

    # ako postoji samo 1 tabela

    if len(tables) == 1:
        table = tables[0]

        table_conditions = [
            c for c in selection_conditions
            if c.left.split(".")[0] == table.name
        ]

        plan = apply_selections(table, table_conditions)
        # apply_selections radi optimize_selections()

        # ORDER BY se dodaje ovde

        return plan

    # ako postoje 2 tabele

    if len(tables) == 2:

        # razdvajamo JOIN i SELECTION uslove jer prvo treba da se odradi selection!

        if len(join_conditions) == 0: raise Exception("No join conditions")

        join_condition = join_conditions[0]

        left_table_name = (join_condition.left.split(".")[0])
        left_attribute_name = (join_condition.left.split(".")[1])
        right_table_name = (join_condition.right.split(".")[0])
        right_attribute_name = (join_condition.right.split(".")[1])

        left_table = schema.get_table(left_table_name)
        right_table = schema.get_table(right_table_name)
        left_attribute = left_table.get_attribute(left_attribute_name)
        right_attribute = right_table.get_attribute(right_attribute_name)

        # prvo optimizujemo selekcije

        # za levu tabelu

        left_conditions = [
            c for c in selection_conditions
            if c.left.split(".")[0] == left_table.name
        ]
        # za desnu tabelu

        right_conditions = [
            c for c in selection_conditions
            if c.left.split(".")[0] == right_table.name
        ]

        left_plan = apply_selections(left_table, left_conditions)
        right_plan = apply_selections(right_table, right_conditions)

        join_plan = optimize_join(left_plan, right_plan, left_table, left_attribute, right_table, right_attribute,
                                  schema.buffer_blocks)

        return create_execution_plan(join_plan)
    # ovde nastavljamo za 3 i vise tabela...


def print_plan(node, level=0):
    indent = "  " * level
    print(
        indent +
        f"{node.operation} "
        f"[{node.algorithm}] "
        f"cost={node.cost}, "
        f"rows={node.output_rows}, "
        f"blocks={node.output_blocks}"
    )

    if node.details:
        print(indent + f"  ->{node.details}")

    for child in node.children:
        print_plan(child, level + 1)
