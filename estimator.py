import math

from algorithms import (
    selection_full_scan,
    linear_search,
    btree_equality,
    btree_range,
    hash_equality,
    external_merge_sort,
    nested_loop_join,
    block_nested_loop_join,
    index_nested_loop_join,
    merge_join,
    hash_join,
)
from models import AlgorithmEstimate, SelectionEstimate, JoinEstimate


# ============================================================
# SELECTIVITY
# ============================================================

def equality_selectivity(attribute, table):
    if attribute.unique:
        return 1 / table.row_count
    return 1 / attribute.distinct_values


def range_selectivity():
    return 0.5


def not_equal_selectivity(attribute, table):
    if attribute.unique:
        return (table.row_count - 1) / table.row_count

    return (attribute.distinct_values - 1) / attribute.distinct_values


# ============================================================
# BASIC ESTIMATION
# ============================================================

def estimate_rows(table, selectivity):
    return max(1, math.ceil(table.row_count * selectivity))


def estimate_blocks(table, output_rows):
    return max(1, math.ceil(output_rows / table.rows_per_block))


def estimate_selection_result(table, attribute, operator):
    if operator == "=":
        rows = estimate_rows(table, equality_selectivity(attribute, table))
    elif operator in ("<", ">", "<=", ">="):
        rows = estimate_rows(table, range_selectivity())
    elif operator == "!=":
        rows = estimate_rows(table, not_equal_selectivity(attribute, table))
    else:
        raise ValueError(f"Unknown operator: {operator}")

    blocks = estimate_blocks(table, rows)
    return rows, blocks


# ============================================================
# SELECTION
# ============================================================

def calculate_index_lookup_cost_for_selection(table, attribute, operator):
    """
    Vraća najmanju cenu pristupa preko indeksa za dati atribut.
    Koristi se samo ako atribut odgovara PRVOM atributu indeksa.
    """
    best_cost = None

    matching_rows = max(
        1,
        math.ceil(table.row_count / attribute.distinct_values)
    )
    matching_blocks = max(
        1,
        math.ceil(matching_rows / table.rows_per_block)
    )

    for index in table.indexes:
        if not index.attributes:
            continue

        # indeks se može koristiti samo ako traženi atribut
        # jeste prvi atribut indeksa
        if index.attributes[0] != attribute.name:
            continue

        # HASH
        if index.index_type == "HASH":
            if operator != "=":
                continue

            if len(index.attributes) > 1:
                continue

            cost = hash_equality(
                output_rows=matching_rows,
                output_blocks=matching_blocks,
                clustered=index.clustered,
                unique=attribute.unique,
            )

        # B+ TREE
        elif index.index_type == "B_PLUS_TREE":
            if index.tree_height is None:
                continue

            if operator == "=":
                cost = btree_equality(
                    height=index.tree_height,
                    clustered=index.clustered,
                    output_rows=matching_rows,
                    output_blocks=matching_blocks,
                    unique=attribute.unique,
                )
            else:
                cost = btree_range(
                    height=index.tree_height,
                    clustered=index.clustered,
                    output_rows=matching_rows,
                    output_blocks=matching_blocks,
                )
        else:
            continue

        if best_cost is None or cost < best_cost:
            best_cost = cost

    return best_cost


def estimate_selection(table, attribute, operator):
    """
    Računa sve mogućnosti za selekciju i bira cenu za svaki pristup.

    Cena selekcije = cena pristupa + cena materijalizacije rezultata.
    """
    output_rows, output_blocks = estimate_selection_result(
        table, attribute, operator
    )

    estimates = []

    # --------------------------------------------------------
    # FULL SCAN
    # --------------------------------------------------------
    access_cost = linear_search(
        table.block_count,
        attribute.unique,
        operator
    )
    total_cost = access_cost + output_blocks

    estimates.append(
        AlgorithmEstimate(
            algorithm="Full Scan",
            cost=total_cost
        )
    )

    # --------------------------------------------------------
    # INDEXES
    # --------------------------------------------------------
    for index in table.indexes:
        if not index.attributes:
            continue

        # indeks se može koristiti samo ako je atribut prvi u indeksu
        if index.attributes[0] != attribute.name:
            continue

        # HASH INDEX
        if index.index_type == "HASH":
            if operator != "=":
                continue

            if len(index.attributes) > 1:
                continue

            access_cost = hash_equality(
                output_rows=output_rows,
                output_blocks=output_blocks,
                clustered=index.clustered,
                unique=attribute.unique,
            )

            estimates.append(
                AlgorithmEstimate(
                    algorithm="Hash Index",
                    cost=access_cost + output_blocks
                )
            )

        # B+ TREE
        elif index.index_type == "B_PLUS_TREE":
            if index.tree_height is None:
                continue

            if operator == "=":
                access_cost = btree_equality(
                    height=index.tree_height,
                    clustered=index.clustered,
                    output_rows=output_rows,
                    output_blocks=output_blocks,
                    unique=attribute.unique,
                )
                alg_name = "B+ Tree"
            else:
                access_cost = btree_range(
                    height=index.tree_height,
                    clustered=index.clustered,
                    output_rows=output_rows,
                    output_blocks=output_blocks,
                )
                alg_name = "B+ Tree Range"

            estimates.append(
                AlgorithmEstimate(
                    algorithm=alg_name,
                    cost=access_cost + output_blocks
                )
            )

    return SelectionEstimate(
        output_rows=output_rows,
        output_blocks=output_blocks,
        estimates=estimates
    )

def estimate_multiple_selections(table, conditions):
    """
    Procena selekcije koja ima vise uslova povezanih sa AND.

    Primer:
        predmetId = 5 AND ocena = 9
    """

    if not conditions:
        return None

    # --------------------------------------------------------
    # 1. RACUNANJE UKUPNE SELEKTIVNOSTI
    # --------------------------------------------------------

    total_selectivity = 1.0

    for condition in conditions:

        attribute = table.get_attribute(
            condition.left.split(".", 1)[-1]
        )

        if attribute is None:
            raise ValueError(
                f"Atribut {condition.left} nije pronadjen u tabeli {table.name}"
            )

        if condition.operator == "=":
            selectivity = equality_selectivity(
                attribute,
                table
            )

        elif condition.operator in ("<", ">", "<=", ">="):
            selectivity = range_selectivity()

        elif condition.operator == "!=":
            selectivity = not_equal_selectivity(
                attribute,
                table
            )

        else:
            raise ValueError(
                f"Unknown operator: {condition.operator}"
            )

        total_selectivity *= selectivity

    # --------------------------------------------------------
    # 2. REZULTAT SELEKCIJE
    # --------------------------------------------------------

    output_rows = max(
        1,
        math.ceil(
            table.row_count * total_selectivity
        )
    )

    output_blocks = estimate_blocks(
        table,
        output_rows
    )

    estimates = []

    # --------------------------------------------------------
    # 3. FULL SCAN
    # --------------------------------------------------------

    full_scan_cost = (
        linear_search(
            table.block_count
        )
        + output_blocks
    )

    estimates.append(
        AlgorithmEstimate(
            algorithm="Full Scan",
            cost=full_scan_cost
        )
    )

    # --------------------------------------------------------
    # 4. INDEX ACCESS
    # --------------------------------------------------------

    for condition in conditions:

        attribute_name = condition.left.split(".", 1)[-1]

        attribute = table.get_attribute(
            attribute_name
        )

        if attribute is None:
            continue

        # Za access cost koristimo broj redova koji
        # odgovara TOM uslovu, a ne konacnom rezultatu.
        if condition.operator == "=":

            if attribute.unique:
                matching_rows = 1
            else:
                matching_rows = max(
                    1,
                    math.ceil(
                        table.row_count /
                        attribute.distinct_values
                    )
                )

        elif condition.operator in ("<", ">", "<=", ">="):

            matching_rows = math.ceil(
                table.row_count / 2
            )

        else:
            matching_rows = math.ceil(
                table.row_count *
                (
                    attribute.distinct_values - 1
                ) /
                attribute.distinct_values
            )

        matching_blocks = max(
            1,
            math.ceil(
                matching_rows /
                table.rows_per_block
            )
        )

        # ----------------------------------------------------
        # Proveravamo indekse
        # ----------------------------------------------------

        for index in table.indexes:

            if not index.attributes:
                continue

            # Koristimo indeks samo ako je atribut
            # prvi atribut indeksa.
            if index.attributes[0] != attribute.name:
                continue

            # HASH
            if index.index_type == "HASH":

                if condition.operator != "=":
                    continue

                if len(index.attributes) > 1:
                    continue

                access_cost = hash_equality(
                    output_rows=matching_rows,
                    output_blocks=matching_blocks,
                    clustered=index.clustered,
                    unique=attribute.unique
                )

                total_cost = (
                    access_cost +
                    output_blocks
                )

                estimates.append(
                    AlgorithmEstimate(
                        algorithm="Hash Index",
                        cost=total_cost
                    )
                )

            # B+ TREE
            elif index.index_type == "B_PLUS_TREE":

                if index.tree_height is None:
                    continue

                if condition.operator == "=":

                    access_cost = btree_equality(
                        height=index.tree_height,
                        clustered=index.clustered,
                        output_rows=matching_rows,
                        output_blocks=matching_blocks,
                        unique=attribute.unique
                    )

                else:

                    access_cost = btree_range(
                        height=index.tree_height,
                        clustered=index.clustered,
                        output_rows=matching_rows,
                        output_blocks=matching_blocks
                    )

                total_cost = (
                    access_cost +
                    output_blocks
                )

                estimates.append(
                    AlgorithmEstimate(
                        algorithm="B+ Tree",
                        cost=total_cost
                    )
                )

    return SelectionEstimate(
        output_rows=output_rows,
        output_blocks=output_blocks,
        estimates=estimates
    )


# ============================================================
# JOIN RESULT
# ============================================================

def estimate_join_result(
    left_plan,
    right_plan,
    left_attribute,
    right_attribute,
    left_table,
    right_table,
    operator="="
):
    """
    Procena broja redova i blokova nakon JOIN-a.
    """
    left_rows = left_plan.output_rows
    right_rows = right_plan.output_rows

    if operator == "=":
        left_distinct = min(left_attribute.distinct_values, left_rows)
        right_distinct = min(right_attribute.distinct_values, right_rows)
        max_distinct = max(left_distinct, right_distinct)

        output_rows = max(
            1,
            math.ceil((left_rows * right_rows) / max_distinct)
        )
    else:
        output_rows = max(
            1,
            math.ceil(0.5 * left_rows * right_rows)
        )

    rows_per_block = min(left_table.rows_per_block, right_table.rows_per_block)
    output_blocks = max(
        1,
        math.ceil(output_rows / rows_per_block)
    )

    return output_rows, output_blocks


# ============================================================
# JOIN
# ============================================================

def calculate_index_lookup_cost_for_join(table, attribute, operator):
    """
    Najjeftiniji lookup kroz indeks na unutrašnjoj relaciji
    za Index Nested Loop Join.
    """
    best_cost = None

    if attribute.unique:
        matching_rows = 1
    else:
        matching_rows = max(
            1,
            math.ceil(table.row_count / attribute.distinct_values)
        )

    matching_blocks = max(
        1,
        math.ceil(matching_rows / table.rows_per_block)
    )

    for index in table.indexes:
        if not index.attributes:
            continue

        if index.attributes[0] != attribute.name:
            continue

        if index.index_type == "B_PLUS_TREE":
            if index.tree_height is None:
                continue

            if operator == "=":
                if attribute.unique:
                    cost = index.tree_height + 1
                elif index.clustered:
                    cost = index.tree_height + matching_blocks
                else:
                    cost = index.tree_height + matching_rows
            else:
                if index.clustered:
                    cost = index.tree_height + matching_blocks
                else:
                    cost = index.tree_height + matching_rows

        elif index.index_type == "HASH":
            if operator != "=":
                continue

            if attribute.unique:
                cost = 1.2
            elif index.clustered:
                cost = 1.2 + matching_blocks
            else:
                cost = 1.2 + matching_rows

        else:
            continue

        if best_cost is None or cost < best_cost:
            best_cost = cost

    return best_cost


def estimate_join(
    left_plan,
    right_plan,
    left_table,
    left_attribute,
    right_table,
    right_attribute,
    buffer_blocks,
    operator="="
):
    """
    Računa sve moguće JOIN algoritme.

    Cena JOIN-a = cena algoritma + materijalizacija rezultata.
    """
    output_rows, output_blocks = estimate_join_result(
        left_plan,
        right_plan,
        left_attribute,
        right_attribute,
        left_table,
        right_table,
        operator=operator
    )

    estimates = []
    materialization_cost = output_blocks

    left_blocks = left_plan.output_blocks
    right_blocks = right_plan.output_blocks
    left_rows = left_plan.output_rows
    right_rows = right_plan.output_rows

    # --------------------------------------------------------
    # NESTED LOOP JOIN
    # --------------------------------------------------------
    cost = nested_loop_join(
        left_blocks,
        left_rows,
        right_blocks
    )
    estimates.append(
        AlgorithmEstimate(
            algorithm="Nested Loop Join",
            cost=cost + materialization_cost
        )
    )

    # --------------------------------------------------------
    # BLOCK NESTED LOOP JOIN
    # --------------------------------------------------------
    cost = block_nested_loop_join(
        left_blocks,
        right_blocks,
        buffer_blocks
    )
    estimates.append(
        AlgorithmEstimate(
            algorithm="Block Nested Loop Join",
            cost=cost + materialization_cost
        )
    )

    # --------------------------------------------------------
    # HASH JOIN
    # --------------------------------------------------------
    if operator == "=":
        cost = hash_join(
            left_blocks,
            right_blocks,
            buffer_blocks
        )
        estimates.append(
            AlgorithmEstimate(
                algorithm="Hash Join",
                cost=cost + materialization_cost
            )
        )

    # --------------------------------------------------------
    # MERGE JOIN
    # --------------------------------------------------------
    if operator == "=":
        left_sort_cost = external_merge_sort(left_blocks, buffer_blocks)
        right_sort_cost = external_merge_sort(right_blocks, buffer_blocks)

        cost = merge_join(
            left_blocks,
            right_blocks,
            left_sort_cost,
            right_sort_cost
        )

        estimates.append(
            AlgorithmEstimate(
                algorithm="Merge Join",
                cost=cost + materialization_cost
            )
        )

    # --------------------------------------------------------
    # INDEX NESTED LOOP JOIN
    # --------------------------------------------------------
    if operator == "=":
        lookup_cost = calculate_index_lookup_cost_for_join(
            right_table,
            right_attribute,
            operator
        )

        if lookup_cost is not None:
            cost = index_nested_loop_join(
                left_blocks,
                left_rows,
                lookup_cost
            )
            estimates.append(
                AlgorithmEstimate(
                    algorithm="Index Nested Loop Join",
                    cost=cost + materialization_cost
                )
            )

    return JoinEstimate(
        output_rows=output_rows,
        output_blocks=output_blocks,
        estimates=estimates
    )