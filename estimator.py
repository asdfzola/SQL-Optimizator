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

from models import (
    AlgorithmEstimate,
    SelectionEstimate,
    JoinEstimate,
)


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

    return (
        attribute.distinct_values - 1
    ) / attribute.distinct_values


# ============================================================
# BASIC ESTIMATION
# ============================================================

def estimate_rows(table, selectivity):
    return max(
        1,
        math.ceil(table.row_count * selectivity)
    )


def estimate_blocks(table, output_rows):
    return max(
        1,
        math.ceil(output_rows / table.rows_per_block)
    )


def estimate_selection_result(table, attribute, operator):
    if operator == "=":
        rows = estimate_rows(
            table,
            equality_selectivity(attribute, table)
        )

    elif operator in ("<", ">", "<=", ">="):
        rows = estimate_rows(
            table,
            range_selectivity()
        )

    elif operator == "!=":
        rows = estimate_rows(
            table,
            not_equal_selectivity(attribute, table)
        )

    else:
        raise ValueError(
            f"Unknown operator: {operator}"
        )

    blocks = estimate_blocks(
        table,
        rows
    )

    return rows, blocks


# ============================================================
# CONDITION HELPERS
# ============================================================

def _condition_attribute_name(condition):
    """
    Vraća ime atributa iz selection uslova.

    Primer:
        Student.ime = 'Ana'  -> ime
        predmetId = 5        -> predmetId
    """

    reference = condition.left

    if "." in reference:
        return reference.split(".", 1)[1]

    return reference


def _find_attribute(table, attribute_name):
    for attribute in table.attributes:
        if attribute.name.lower() == attribute_name.lower():
            return attribute

    return None


def _condition_selectivity(table, condition):
    """
    Selektivnost jednog WHERE uslova.
    """

    attribute_name = _condition_attribute_name(
        condition
    )

    attribute = _find_attribute(
        table,
        attribute_name
    )

    if attribute is None:
        raise ValueError(
            f"Atribut '{attribute_name}' ne postoji "
            f"u tabeli '{table.name}'."
        )

    if condition.operator == "=":
        return equality_selectivity(
            attribute,
            table
        )

    if condition.operator in (
        "<",
        ">",
        "<=",
        ">="
    ):
        return range_selectivity()

    if condition.operator == "!=":
        return not_equal_selectivity(
            attribute,
            table
        )

    raise ValueError(
        f"Unknown operator: {condition.operator}"
    )


# ============================================================
# MULTIPLE SELECTIONS
# ============================================================

def estimate_multiple_selection_result(
    table,
    conditions
):
    """
    Procena rezultata za:

        A = x AND B = y AND ...

    Pretpostavlja nezavisnost uslova.
    """

    selectivity = 1.0

    for condition in conditions:
        selectivity *= _condition_selectivity(
            table,
            condition
        )

    output_rows = estimate_rows(
        table,
        selectivity
    )

    output_blocks = estimate_blocks(
        table,
        output_rows
    )

    return output_rows, output_blocks


def _condition_map(table, conditions):
    """
    Pravi mapu:

        ime_atributa -> condition

    """
    result = {}

    for condition in conditions:
        attribute_name = _condition_attribute_name(
            condition
        )

        result[attribute_name.lower()] = condition

    return result


# ============================================================
# COMPOSITE HASH INDEX
# ============================================================

def _find_composite_hash_index(
    table,
    conditions
):
    """
    Traži HASH indeks koji je potpuno pokriven
    equality uslovima.

    Primer:

        index = [predmetId, ocena]

        WHERE predmetId = 5 AND ocena = 9

    -> indeks može da se koristi.

    Ali:

        WHERE predmetId = 5

    -> ne koristimo ovaj indeks u ovoj funkciji,
       jer nije pokriven ceo ključ.
    """

    condition_map = _condition_map(
        table,
        conditions
    )

    for index in table.indexes:

        if index.index_type != "HASH":
            continue

        if len(index.attributes) <= 1:
            continue

        all_attributes_match = True

        for indexed_attribute in index.attributes:

            condition = condition_map.get(
                indexed_attribute.lower()
            )

            if condition is None:
                all_attributes_match = False
                break

            if condition.operator != "=":
                all_attributes_match = False
                break

        if all_attributes_match:
            return index

    return None


def _composite_hash_cost(
    output_rows,
    output_blocks
):
    """
    Cost za potpuno pokriven kompozitni HASH indeks.

    Za primer:

        Ispit:
        output_rows = 17
        output_blocks = 2

    cost:

        1 + 17 + 2 = 20
    """

    return 1 + output_rows + output_blocks


# ============================================================
# SINGLE INDEX LOOKUP
# ============================================================

def calculate_index_lookup_cost_for_selection(
    table,
    attribute,
    operator
):
    """
    Vraća najjeftiniji pristup preko indeksa
    za jedan selection uslov.

    Koristi se samo za jednostavne uslove.
    """

    best_cost = None

    matching_rows = max(
        1,
        math.ceil(
            table.row_count /
            attribute.distinct_values
        )
    )

    matching_blocks = max(
        1,
        math.ceil(
            matching_rows /
            table.rows_per_block
        )
    )

    for index in table.indexes:

        if not index.attributes:
            continue

        # Za single-condition lookup atribut mora
        # biti prvi atribut indeksa.
        if (
            index.attributes[0].lower()
            != attribute.name.lower()
        ):
            continue

        # ----------------------------------------------------
        # HASH
        # ----------------------------------------------------

        if index.index_type == "HASH":

            # Kompozitne HASH indekse ovde ne koristimo.
            # Njih obrađuje estimate_multiple_selections().
            if len(index.attributes) > 1:
                continue

            if operator != "=":
                continue

            cost = hash_equality(
                output_rows=matching_rows,
                output_blocks=matching_blocks,
                clustered=index.clustered,
                unique=attribute.unique
            )

        # ----------------------------------------------------
        # B+ TREE
        # ----------------------------------------------------

        elif index.index_type == "B_PLUS_TREE":

            if index.tree_height is None:
                continue

            if operator == "=":

                cost = btree_equality(
                    height=index.tree_height,
                    clustered=index.clustered,
                    output_rows=matching_rows,
                    output_blocks=matching_blocks,
                    unique=attribute.unique
                )

            else:

                cost = btree_range(
                    height=index.tree_height,
                    clustered=index.clustered,
                    output_rows=matching_rows,
                    output_blocks=matching_blocks
                )

        else:
            continue

        if (
            best_cost is None
            or cost < best_cost
        ):
            best_cost = cost

    return best_cost


# ============================================================
# SINGLE SELECTION
# ============================================================

def estimate_selection(
    table,
    attribute,
    operator
):
    """
    Računa sve mogućnosti za jednu selection
    operaciju.
    """

    output_rows, output_blocks = (
        estimate_selection_result(
            table,
            attribute,
            operator
        )
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

    total_cost = (
        access_cost +
        output_blocks
    )

    estimates.append(
        AlgorithmEstimate(
            algorithm="Full Scan",
            cost=total_cost
        )
    )

    # --------------------------------------------------------
    # INDEX
    # --------------------------------------------------------

    index_cost = (
        calculate_index_lookup_cost_for_selection(
            table,
            attribute,
            operator
        )
    )

    if index_cost is not None:

        # Proveravamo tip indeksa da bismo dobili
        # odgovarajući naziv algoritma.
        for index in table.indexes:

            if not index.attributes:
                continue

            if (
                index.attributes[0].lower()
                != attribute.name.lower()
            ):
                continue

            if len(index.attributes) > 1:
                continue

            if index.index_type == "HASH":

                if operator == "=":

                    estimates.append(
                        AlgorithmEstimate(
                            algorithm="Hash Index",
                            cost=(
                                index_cost +
                                output_blocks
                            )
                        )
                    )

            elif index.index_type == "B_PLUS_TREE":

                if operator == "=":

                    estimates.append(
                        AlgorithmEstimate(
                            algorithm="B+ Tree",
                            cost=(
                                index_cost +
                                output_blocks
                            )
                        )
                    )

                else:

                    estimates.append(
                        AlgorithmEstimate(
                            algorithm="B+ Tree Range",
                            cost=(
                                index_cost +
                                output_blocks
                            )
                        )
                    )

    return SelectionEstimate(
        output_rows=output_rows,
        output_blocks=output_blocks,
        estimates=estimates
    )


# ============================================================
# MULTIPLE SELECTIONS
# ============================================================

def estimate_multiple_selections(
    table,
    conditions
):
    """
    Računa selection sa više AND uslova.

    Primer:

        predmetId = 5 AND ocena = 9

    Posebno podržava kompozitne HASH indekse.
    """

    if not conditions:
        raise ValueError(
            "estimate_multiple_selections zahteva "
            "bar jedan uslov."
        )

    # --------------------------------------------------------
    # OUTPUT SIZE
    # --------------------------------------------------------

    output_rows, output_blocks = (
        estimate_multiple_selection_result(
            table,
            conditions
        )
    )

    estimates = []

    # --------------------------------------------------------
    # FULL SCAN
    # --------------------------------------------------------

    full_scan_cost = (
        table.block_count +
        output_blocks
    )

    estimates.append(
        AlgorithmEstimate(
            algorithm="Full Scan",
            cost=full_scan_cost
        )
    )

    # --------------------------------------------------------
    # COMPOSITE HASH INDEX
    # --------------------------------------------------------

    composite_hash = _find_composite_hash_index(
        table,
        conditions
    )

    if composite_hash is not None:

        cost = _composite_hash_cost(
            output_rows,
            output_blocks
        )

        estimates.append(
            AlgorithmEstimate(
                algorithm="Hash Index",
                cost=cost
            )
        )

    # --------------------------------------------------------
    # SINGLE-ATTRIBUTE INDEXES
    # --------------------------------------------------------

    for condition in conditions:

        attribute_name = (
            _condition_attribute_name(
                condition
            )
        )

        attribute = _find_attribute(
            table,
            attribute_name
        )

        if attribute is None:
            continue

        index_cost = (
            calculate_index_lookup_cost_for_selection(
                table,
                attribute,
                condition.operator
            )
        )

        if index_cost is None:
            continue

        # ----------------------------------------------------
        # Napomena:
        #
        # Ako imamo vise AND uslova, indeks koji odgovara
        # samo jednom atributu nije dovoljan da direktno
        # predstavi ceo rezultat.
        #
        # Zato ovde dodajemo procenjeni broj output blokova
        # kao materijalizaciju rezultata.
        # ----------------------------------------------------

        total_cost = (
            index_cost +
            output_blocks
        )

        # Odredi naziv algoritma
        for index in table.indexes:

            if not index.attributes:
                continue

            if (
                index.attributes[0].lower()
                != attribute.name.lower()
            ):
                continue

            # Kompozitni HASH indeks je vec obradjen gore.
            if (
                index.index_type == "HASH"
                and len(index.attributes) > 1
            ):
                continue

            if index.index_type == "HASH":

                if condition.operator == "=":

                    estimates.append(
                        AlgorithmEstimate(
                            algorithm="Hash Index",
                            cost=total_cost
                        )
                    )

            elif index.index_type == "B_PLUS_TREE":

                if condition.operator == "=":

                    estimates.append(
                        AlgorithmEstimate(
                            algorithm="B+ Tree",
                            cost=total_cost
                        )
                    )

                else:

                    estimates.append(
                        AlgorithmEstimate(
                            algorithm="B+ Tree Range",
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

        left_distinct = min(
            left_attribute.distinct_values,
            left_rows
        )

        right_distinct = min(
            right_attribute.distinct_values,
            right_rows
        )

        max_distinct = max(
            left_distinct,
            right_distinct
        )

        output_rows = max(
            1,
            math.ceil(
                (
                    left_rows *
                    right_rows
                ) / max_distinct
            )
        )

    else:

        output_rows = max(
            1,
            math.ceil(
                0.5 *
                left_rows *
                right_rows
            )
        )

    rows_per_block = min(
        left_table.rows_per_block,
        right_table.rows_per_block
    )

    output_blocks = max(
        1,
        math.ceil(
            output_rows /
            rows_per_block
        )
    )

    return output_rows, output_blocks


# ============================================================
# JOIN INDEX LOOKUP
# ============================================================

def calculate_index_lookup_cost_for_join(
    table,
    attribute,
    operator
):
    """
    Najjeftiniji lookup kroz indeks na unutrašnjoj
    relaciji za Index Nested Loop Join.
    """

    best_cost = None

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

    matching_blocks = max(
        1,
        math.ceil(
            matching_rows /
            table.rows_per_block
        )
    )

    for index in table.indexes:

        if not index.attributes:
            continue

        if (
            index.attributes[0].lower()
            != attribute.name.lower()
        ):
            continue

        # ----------------------------------------------------
        # B+ TREE
        # ----------------------------------------------------

        if index.index_type == "B_PLUS_TREE":

            if index.tree_height is None:
                continue

            if operator == "=":

                if attribute.unique:

                    cost = (
                        index.tree_height +
                        1
                    )

                elif index.clustered:

                    cost = (
                        index.tree_height +
                        matching_blocks
                    )

                else:

                    cost = (
                        index.tree_height +
                        matching_rows
                    )

            else:

                if index.clustered:

                    cost = (
                        index.tree_height +
                        matching_blocks
                    )

                else:

                    cost = (
                        index.tree_height +
                        matching_rows
                    )

        # ----------------------------------------------------
        # HASH
        # ----------------------------------------------------

        elif index.index_type == "HASH":

            if operator != "=":
                continue

            if len(index.attributes) > 1:
                continue

            if attribute.unique:

                cost = 1.2

            elif index.clustered:

                cost = (
                    1.2 +
                    matching_blocks
                )

            else:

                cost = (
                    1.2 +
                    matching_rows
                )

        else:
            continue

        if (
            best_cost is None
            or cost < best_cost
        ):
            best_cost = cost

    return best_cost


# ============================================================
# JOIN
# ============================================================

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
    """

    output_rows, output_blocks = (
        estimate_join_result(
            left_plan,
            right_plan,
            left_attribute,
            right_attribute,
            left_table,
            right_table,
            operator
        )
    )

    estimates = []

    left_blocks = left_plan.output_blocks
    right_blocks = right_plan.output_blocks

    left_rows = left_plan.output_rows

    materialization_cost = output_blocks

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
            cost=(
                cost +
                materialization_cost
            )
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
            cost=(
                cost +
                materialization_cost
            )
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
                cost=(
                    cost +
                    materialization_cost
                )
            )
        )

    # --------------------------------------------------------
    # MERGE JOIN
    # --------------------------------------------------------

    if operator == "=":

        left_sort_cost = external_merge_sort(
            left_blocks,
            buffer_blocks
        )

        right_sort_cost = external_merge_sort(
            right_blocks,
            buffer_blocks
        )

        cost = merge_join(
            left_blocks,
            right_blocks,
            left_sort_cost,
            right_sort_cost
        )

        estimates.append(
            AlgorithmEstimate(
                algorithm="Merge Join",
                cost=(
                    cost +
                    materialization_cost
                )
            )
        )

    # --------------------------------------------------------
    # INDEX NESTED LOOP JOIN
    # --------------------------------------------------------

    if operator == "=":

        lookup_cost = (
            calculate_index_lookup_cost_for_join(
                right_table,
                right_attribute,
                operator
            )
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
                    cost=(
                        cost +
                        materialization_cost
                    )
                )
            )

    return JoinEstimate(
        output_rows=output_rows,
        output_blocks=output_blocks,
        estimates=estimates
    )