from algorithms import *
from models import *
import math


def equality_selectivity(attribute):
    return 1 / attribute.distinct_values


def range_selectivity():
    return 1 / 3


def not_equal_selectivity(attribute):
    return (attribute.distinct_values - 1) / attribute.distinct_values


def estimate_rows(table, selectivity):
    return math.ceil(table.row_count * selectivity)


def estimate_blocks(table, output_rows):
    return math.ceil(output_rows / table.rows_per_block)


def estimate_equality(table, attribute):
    sel = equality_selectivity(attribute)
    rows = estimate_rows(table, sel)
    blocks = estimate_blocks(table, rows)
    return rows, blocks


def estimate_selection(table, attribute, operator):
    if operator == "=":
        sel = equality_selectivity(attribute)
    elif operator in ("<", ">", "<=", ">="):
        sel = range_selectivity()
    elif operator == "!=":
        sel = not_equal_selectivity(attribute)
    else:
        raise Exception("Unknown operator")

    rows = estimate_rows(table, sel)
    blocks = estimate_blocks(table, rows)

    estimates = []

    estimates.append(
        AlgorithmEstimate(
            "Full Scan",
            selection_full_scan(
                table.block_count
            )
        )
    )

    for index in table.indexes:

        if attribute.name not in index.attributes:
            continue

        if index.index_type == "HASH" and operator == "=":
            estimates.append(
                AlgorithmEstimate("Hash Index", hash_equality())
            )

        if index.index_type == "B_PLUS_TREE":
            if operator == "=":
                estimates.append(
                    AlgorithmEstimate("B+ Tree", btree_equality(index.tree_height, index.clustered, blocks))
                )
            else:
                estimates.append(
                    AlgorithmEstimate("B+ Tree Range", btree_equality(index.tree_height, 1, blocks))
                )

    return SelectionEstimate(
        output_rows=rows,
        output_blocks=blocks,
        estimates=estimates
    )


def estimate_join(left_plan, right_plan, left_table, left_attribute, right_table, right_attribute, buffer_blocks):
    output_rows = math.ceil(
        (left_plan.output_rows * right_plan.output_rows) / max(left_attribute.distinct_values,
                                                               right_attribute.distinct_values))

    output_blocks = math.ceil(output_rows / min(left_table.rows_per_block, right_table.rows_per_block))

    estimates = []

    # Nested loop Join
    cost = nested_loop_join(
        left_plan.output_blocks,
        left_plan.output_rows,
        right_plan.output_blocks
    )

    estimates.append(AlgorithmEstimate("Nested Loop Join", cost))

    # Block Nested Loop Join
    cost = block_nested_loop_join(
        left_plan.output_blocks,
        right_plan.output_blocks,
        buffer_blocks
    )

    estimates.append(AlgorithmEstimate("Block Nested Loop Join", cost))

    # Hash Join
    cost = hash_join(
        left_plan.output_blocks,
        right_plan.output_blocks
    )

    estimates.append(AlgorithmEstimate("Hash Join", cost))

    # Merge Join
    left_sort = external_merge_sort(
        left_plan.output_blocks,
        buffer_blocks
    )
    right_sort = external_merge_sort(
        right_plan.output_blocks,
        buffer_blocks
    )

    cost = merged_join(
        left_plan.output_blocks,
        right_plan.output_blocks,
        sorted=False,
        sort_cost=left_sort + right_sort
    )

    estimates.append(AlgorithmEstimate("Merge Join", cost))

    # Index Nested Loop Join
    # optimizer ce da proba da li index postoji u unutrasnjoj relaciji
    for index in right_table.indexes:

        if right_attribute.name not in index.attributes: continue

        if index.index_type != "B_PLUS_TREE": continue

        matching_rows = math.ceil(right_plan.output_rows / right_attribute.distinct_values)

        cost = index_nested_loop_join(
            left_plan.output_blocks,
            left_plan.output_rows,
            index.tree_height,
            index.clustered,
            matching_rows
        )

        estimates.append(AlgorithmEstimate("Index Nested Loop Join", cost))

    return JoinEstimate(
        output_rows=output_rows,
        output_blocks=output_blocks,
        estimates=estimates
    )
