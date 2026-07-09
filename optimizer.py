from models import *
from estimator import *


def optimize_selection(table, condition):
    attribute_name = condition.left.split(".")[-1]
    attribute = table.get_attribute(attribute_name)

    estimate = estimate_selection(table, attribute, condition.operator)

    best = min(estimate.estimates, key=lambda x: x.cost)

    return PlanNode(
        operation="SELECTION",
        algorithm=best.algorithm,
        cost=best.cost,
        children=[],
        details=(condition.left + condition.operator + condition.right)
    )


def optimize_join(left_table, left_attr, right_table, right_attr, buffer_blocks):
    estimate = estimate_join(left_table, left_attr, right_table, right_attr, buffer_blocks)

    best = min(estimate.estimates, key=lambda x: x.cost)

    return PlanNode(
        operation="JOIN",
        algorithm=best.algorithm,
        cost=best.cost,
        children=[],
        details=(left_table.name + "." + left_attr.name + "=" + right_table.name + "." + right_attr.name)
    )


def optimize_query(query, schema):
    tables = []
    # uzimamo prvo sve tabele koje se pojavljuju u upitu
    for table_name in query.from_tables:
        tables.append(
            schema.get_table(table_name)
        )

    # ako postoji samo 1 tabela

    if len(tables) == 1:
        table = tables[0]
        plan = None

        for condition in query.where:
            if condition.is_selection():
                plan = optimize_selection(table, condition)

        if plan is None:  # Nema nijedan uslov
            plan = PlanNode(
                operation="SCAN",
                algorithm="Full Scan",
                cost=table.block_count,
                children=[],
                details=table.name
            )

        return plan

    # ako postoje 2 tabele

    if len(tables) == 2:
        join_condition = None

        selection_condition = []

        # razdvajamo JOIN i SELECTION uslove jer prvo treba da se odradi selection!

        for condition in query.where:
            if condition.is_join():
                join_condition = condition
            else:
                selection_condition.append(condition)

        if join_condition is None: raise Exception("no join condition")

        left_table_name = (join_condition.left.split(".")[0])
        left_attribute_name = (join_condition.left.split(".")[1])
        right_table_name = (join_condition.right.split(".")[0])
        right_attribute_name = (join_condition.right.split(".")[1])

        left_table = schema.get_table(left_table_name)
        right_table = schema.get_table(right_table_name)
        left_attribute = left_table.get_attribute(left_attribute_name)
        right_attribute = right_table.get_attribute(right_attribute_name)

        # prvo optimizujemo selekcije
        left_plan = PlanNode(
            operation="SCAN",
            algorithm="Full Scan",
            cost=left_table.block_count,
            children=[],
            details=left_table.name
        )
        right_plan = PlanNode(
            operation="SCAN",
            algorithm="Full Scan",
            cost=right_table.block_count,
            children=[],
            details=right_table.name
        )

        for condition in selection_condition:
            condition_table_name = (condition.left.split(".")[0])
            if condition_table_name == left_table.name:
                left_plan = optimize_selection(left_table, condition)
            elif condition_table_name == right_table.name:
                right_plan = optimize_selection(right_table, condition)

        # kada smo zavrsili selection, sada radimo JOIN

        join_plan = optimize_join(left_table, left_attribute, right_table, right_attribute, schema.buffer_blocks)

        join_plan.children = [left_plan, right_plan]

        return join_plan
    # ovde nastavljamo za 3 i vise tabela...
