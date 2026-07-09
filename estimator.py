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
    elif operator == ("<", ">", "<=", ">="):
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
