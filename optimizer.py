from models import *
from estimator import *


# ============================================================
# POMOCNE FUNKCIJE
# ============================================================

def _case_insensitive_lookup(mapping, key):
    for k, v in mapping.items():
        if k.lower() == key.lower():
            return v
    return None


def _find_table_by_name(schema, table_name):
    """
    Case-insensitive pretraga tabele u schema.tables.
    """
    for name, table in schema.tables.items():
        if name.lower() == table_name.lower():
            return table
    raise ValueError(f"Tabela nije pronadjena: {table_name}")


def _find_attribute_case_insensitive(table, attribute_name):
    """
    Case-insensitive pretraga atributa u tabeli.
    """
    for attr in table.attributes:
        if attr.name.lower() == attribute_name.lower():
            return attr
    return None


def resolve_attribute_name(reference):
    """
    Podrzava:
        s.ime -> ime
        ime   -> ime
    """
    if "." in reference:
        return reference.split(".", 1)[1]
    return reference


def resolve_table_name(query, schema, reference):
    """
    Vraca pravo ime tabele za referencu.

    Podrzava:
        s.ime        -> Student   (ako je s alias)
        Student.ime  -> Student
        ime          -> jedina tabela ili jedina tabela
                        koja ima taj atribut
    """
    reference = reference.strip()

    # kvalifikovana referenca
    if "." in reference:
        prefix = reference.split(".", 1)[0]

        # prvo probaj alias
        mapped = _case_insensitive_lookup(query.table_aliases, prefix)
        if mapped is not None:
            return mapped

        # ako nije alias, probaj da li je samo ime tabele
        for table_name in query.from_tables:
            if table_name.lower() == prefix.lower():
                return table_name

        raise ValueError(f"Nepoznat alias ili tabela: {prefix}")

    # nekvalifikovana referenca
    if len(query.from_tables) == 1:
        return query.from_tables[0]

    # probaj da nadjes jedinstvenu tabelu koja ima taj atribut
    candidates = []
    for table_name in query.from_tables:
        table = _find_table_by_name(schema, table_name)
        if _find_attribute_case_insensitive(table, reference) is not None:
            candidates.append(table_name)

    if len(candidates) == 1:
        return candidates[0]

    if len(candidates) == 0:
        raise ValueError(f"Atribut nije pronadjen ni u jednoj tabeli: {reference}")

    raise ValueError(f"Ambigvitetan atribut: {reference}")


def split_conditions(query):
    """
    Razdvaja WHERE uslove na:
        - selection (normalizovani tako da je atributska referenca UVEK levo,
          npr. '5 = R.ocena' postaje 'R.ocena = 5' - vidi Condition.normalized())
        - join
    """
    selection_conditions = []
    join_conditions = []

    for condition in query.where:
        if condition.is_join(query.table_aliases):
            join_conditions.append(condition)
        else:
            selection_conditions.append(condition.normalized(query.table_aliases))

    return selection_conditions, join_conditions


def _condition_table_name(query, schema, condition_side):
    return resolve_table_name(query, schema, condition_side)


def _condition_to_text(condition):
    return f"{condition.left}{condition.operator}{condition.right}"


# ============================================================
# SCAN / SELECTION / JOIN  / SORT
# ============================================================

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


def optimize_selection(table, condition, table_aliases=None):
    """
    Bira najbolji access path za jednu selection logicku operaciju.
    """
    condition = condition.normalized(table_aliases)
    attribute_name = resolve_attribute_name(condition.left)
    attribute = _find_attribute_case_insensitive(table, attribute_name)

    if attribute is None:
        raise ValueError(
            f"Atribut '{attribute_name}' ne postoji u tabeli '{table.name}'"
        )

    estimate = estimate_selection(table, attribute, condition.operator)

    best = min(estimate.estimates, key=lambda x: x.cost)

    return PlanNode(
        operation="SELECTION",
        algorithm=best.algorithm,
        cost=best.cost,
        output_rows=estimate.output_rows,
        output_blocks=estimate.output_blocks,
        children=[],
        details=_condition_to_text(condition)
    )


def optimize_multiple_selections(table, conditions):
    estimate = estimate_multiple_selections(
        table,
        conditions
    )

    best = min(
        estimate.estimates,
        key=lambda x: x.cost
    )

    return PlanNode(
        operation="SELECTION",
        algorithm=best.algorithm,
        cost=best.cost,
        output_rows=estimate.output_rows,
        output_blocks=estimate.output_blocks,
        children=[],
        details=" AND ".join(
            f"{c.left}{c.operator}{c.right}"
            for c in conditions
        )
    )


def optimize_order_by(plan, table, attribute, buffer_blocks):
    from algorithms import external_merge_sort

    # Proveri da li postoji clustered B+ tree indeks
    for index in table.indexes:
        if (
                index.index_type == "B_PLUS_TREE"
                and index.clustered
                and index.attributes
                and index.attributes[0].lower() == attribute.lower()
        ):
            cost = index.tree_height + table.block_count

            return PlanNode(
                operation="SORT",
                algorithm="Clustered B+ Tree Scan",
                cost=cost,
                output_rows=plan.output_rows,
                output_blocks=plan.output_blocks,
                children=[plan],
                details=attribute
            )

    # Ako nema odgovarajućeg clustered indeksa,
    # radi se external merge sort
    cost = external_merge_sort(
        plan.output_blocks,
        buffer_blocks
    )

    return PlanNode(
        operation="SORT",
        algorithm="External Merge Sort",
        cost=cost,
        output_rows=plan.output_rows,
        output_blocks=plan.output_blocks,
        children=[plan],
        details=attribute
    )


def _build_selection_plan_for_table(query, schema, table, conditions):
    """
    Za jednu tabelu:
    - ako nema selection uslova -> SCAN
    - ako ima -> izaberi najbolji access path medju uslovima
      i izracunaj combined output size za sve selection uslove.
    """

    if not conditions:
        return create_scan_plan(table)

    return optimize_multiple_selections(table, conditions)


def _calculate_total_cost(node):
    total = node.cost
    for child in node.children:
        total += _calculate_total_cost(child)
    return total


def _make_execution_plan(root):
    return ExecutionPlan(
        root=root,
        total_cost=_calculate_total_cost(root)
    )


# ============================================================
# JOIN HELPERS
# ============================================================

def _condition_side_info(query, schema, condition):
    """
    Vraca:
        left_table_name, left_attr_name, right_table_name, right_attr_name
    """
    left_table_name = resolve_table_name(query, schema, condition.left)
    right_table_name = resolve_table_name(query, schema, condition.right)

    left_attr_name = resolve_attribute_name(condition.left)
    right_attr_name = resolve_attribute_name(condition.right)

    return left_table_name, left_attr_name, right_table_name, right_attr_name


def _find_join_condition_between(query, schema, left_table_names, right_table_name, join_conditions):
    """
    Nadje prvi join uslov koji povezuje jednu od
    trenutno spojenih tabela sa sledecom tabelom.
    """
    for condition in join_conditions:
        lt, _, rt, _ = _condition_side_info(query, schema, condition)

        if (
                (lt in left_table_names and rt == right_table_name)
                or
                (rt in left_table_names and lt == right_table_name)
        ):
            return condition

    return None


def _build_join_candidate(
        left_plan,
        right_plan,
        left_table,
        left_attribute,
        right_table,
        right_attribute,
        buffer_blocks,
        operator,
        condition_text
):
    """
    Pravi kandidata za JOIN na osnovu cost modela.
    """
    join_estimate = estimate_join(
        left_plan=left_plan,
        right_plan=right_plan,
        left_table=left_table,
        left_attribute=left_attribute,
        right_table=right_table,
        right_attribute=right_attribute,
        buffer_blocks=buffer_blocks,
        operator=operator
    )

    best = min(join_estimate.estimates, key=lambda x: x.cost)

    return PlanNode(
        operation="JOIN",
        algorithm=best.algorithm,
        cost=best.cost,
        output_rows=join_estimate.output_rows,
        output_blocks=join_estimate.output_blocks,
        children=[left_plan, right_plan],
        details=condition_text
    )


def optimize_join_between_plans(
        query,
        schema,
        current_plan,
        current_table_names,
        next_plan,
        next_table_name,
        join_condition,
        buffer_blocks
):
    """
    Za jedan join uslov proba obe orijentacije:
        current_plan LEFT / next_plan RIGHT
        next_plan LEFT / current_plan RIGHT
    i bira jeftiniju.
    """
    left_table_name, left_attr_name, right_table_name, right_attr_name = _condition_side_info(
        query, schema, join_condition
    )

    # Ako je uslov tipa:
    #   A.x = B.y
    # a current_tables sadrzi A, a next_table je B,
    # onda candidate1 = current LEFT, next RIGHT
    # candidate2 = obrnuto

    current_contains_left = left_table_name in current_table_names
    current_contains_right = right_table_name in current_table_names

    if not ((current_contains_left and right_table_name == next_table_name) or
            (current_contains_right and left_table_name == next_table_name)):
        raise ValueError("Join uslov ne povezuje trenutni plan sa sledecim planom.")

    left_table_obj = _find_table_by_name(schema, left_table_name)
    right_table_obj = _find_table_by_name(schema, right_table_name)

    left_attr_obj = _find_attribute_case_insensitive(left_table_obj, left_attr_name)
    right_attr_obj = _find_attribute_case_insensitive(right_table_obj, right_attr_name)

    if left_attr_obj is None or right_attr_obj is None:
        raise ValueError("Atribut iz join uslova nije pronadjen.")

    # Kandidat 1: current_plan kao LEFT, next_plan kao RIGHT
    if current_contains_left and right_table_name == next_table_name:
        cand1 = _build_join_candidate(
            left_plan=current_plan,
            right_plan=next_plan,
            left_table=left_table_obj,
            left_attribute=left_attr_obj,
            right_table=right_table_obj,
            right_attribute=right_attr_obj,
            buffer_blocks=buffer_blocks,
            operator=join_condition.operator,
            condition_text=_condition_to_text(join_condition)
        )
    elif current_contains_right and left_table_name == next_table_name:
        # uslov je obrnut u tekstu, pa mapiramo tako da current ostane levo
        cand1 = _build_join_candidate(
            left_plan=current_plan,
            right_plan=next_plan,
            left_table=right_table_obj,
            left_attribute=right_attr_obj,
            right_table=left_table_obj,
            right_attribute=left_attr_obj,
            buffer_blocks=buffer_blocks,
            operator=join_condition.operator,
            condition_text=_condition_to_text(join_condition)
        )
    else:
        cand1 = None

    # Kandidat 2: next_plan kao LEFT, current_plan kao RIGHT
    if current_contains_left and right_table_name == next_table_name:
        cand2 = _build_join_candidate(
            left_plan=next_plan,
            right_plan=current_plan,
            left_table=right_table_obj,
            left_attribute=right_attr_obj,
            right_table=left_table_obj,
            right_attribute=left_attr_obj,
            buffer_blocks=buffer_blocks,
            operator=join_condition.operator,
            condition_text=_condition_to_text(join_condition)
        )
    elif current_contains_right and left_table_name == next_table_name:
        cand2 = _build_join_candidate(
            left_plan=next_plan,
            right_plan=current_plan,
            left_table=left_table_obj,
            left_attribute=left_attr_obj,
            right_table=right_table_obj,
            right_attribute=right_attr_obj,
            buffer_blocks=buffer_blocks,
            operator=join_condition.operator,
            condition_text=_condition_to_text(join_condition)
        )
    else:
        cand2 = None

    candidates = [c for c in (cand1, cand2) if c is not None]
    if not candidates:
        raise ValueError("Nije moguce formirati JOIN kandidata.")

    best_join = min(candidates, key=lambda p: _calculate_total_cost(p))
    return best_join


# ============================================================
# MAIN OPTIMIZER
# ============================================================

def optimize_query(query, schema):
    """
    Glavna funkcija optimizer-a.

    Podrzava:
        - 1 tabelu
        - 2 tabele
        - vise tabela (left-deep plan)
    """

    if not query.from_tables:
        raise ValueError("FROM klauzula je prazna.")

    selection_conditions, join_conditions = split_conditions(query)

    # --------------------------------------------------------
    # BAZNI PLANOVI ZA SVAKU TABELU
    # --------------------------------------------------------
    base_plans = {}
    for table_name in query.from_tables:
        table = _find_table_by_name(schema, table_name)

        table_conditions = []
        for condition in selection_conditions:
            try:
                condition_table_name = resolve_table_name(query, schema, condition.left)
            except Exception:
                continue

            if condition_table_name.lower() == table_name.lower():
                table_conditions.append(condition)

        base_plans[table_name] = _build_selection_plan_for_table(
            query,
            schema,
            table,
            table_conditions
        )

    # --------------------------------------------------------
    # 1 TABELA
    # --------------------------------------------------------
    if len(query.from_tables) == 1:
        root = base_plans[query.from_tables[0]]

        # ORDER BY
        if query.order_by:
            table = _find_table_by_name(schema, query.from_tables[0])
            attribute_name = resolve_attribute_name(query.order_by)

            root = optimize_order_by(
                root,
                table,
                attribute_name,
                schema.buffer_blocks
            )

        return _make_execution_plan(root)

    # --------------------------------------------------------
    # 2+ TABELE
    # --------------------------------------------------------
    current_table_names = [query.from_tables[0]]
    current_plan = base_plans[query.from_tables[0]]

    for next_table_name in query.from_tables[1:]:
        next_plan = base_plans[next_table_name]

        candidate_conditions = []
        for condition in join_conditions:
            try:
                lt, _, rt, _ = _condition_side_info(query, schema, condition)
            except Exception:
                continue

            if (
                    (lt in current_table_names and rt == next_table_name)
                    or
                    (rt in current_table_names and lt == next_table_name)
            ):
                candidate_conditions.append(condition)

        if not candidate_conditions:
            raise ValueError(
                f"Nema JOIN uslova koji povezuje trenutni plan sa tabelom '{next_table_name}'."
            )

        # Izaberi najjeftiniji JOIN medju svim kandidatima uslova
        best_join_plan = None
        best_total = None

        for condition in candidate_conditions:
            join_plan = optimize_join_between_plans(
                query=query,
                schema=schema,
                current_plan=current_plan,
                current_table_names=current_table_names,
                next_plan=next_plan,
                next_table_name=next_table_name,
                join_condition=condition,
                buffer_blocks=schema.buffer_blocks
            )

            join_total = _calculate_total_cost(join_plan)

            if best_total is None or join_total < best_total:
                best_total = join_total
                best_join_plan = join_plan

        current_plan = best_join_plan
        current_table_names.append(next_table_name)

    root = current_plan

    # ORDER BY
    if query.order_by:
        # Kod JOIN-a ORDER BY atribut može pripadati bilo kojoj
        # tabeli iz FROM klauzule.
        order_by_attribute = resolve_attribute_name(query.order_by)
        order_by_table_name = resolve_table_name(
            query,
            schema,
            query.order_by
        )

        order_by_table = _find_table_by_name(
            schema,
            order_by_table_name
        )

        root = optimize_order_by(
            root,
            order_by_table,
            order_by_attribute,
            schema.buffer_blocks
        )
    return _make_execution_plan(root)


# ============================================================
# PRINT PLAN
# ============================================================

def print_plan(node, level=0):
    indent = "  " * level
    print(
        indent
        + f"{node.operation} "
        + f"[{node.algorithm}] "
        + f"cost={node.cost}, "
        + f"rows={node.output_rows}, "
        + f"blocks={node.output_blocks}"
    )

    if node.details:
        print(indent + f"  ->{node.details}")

    for child in node.children:
        print_plan(child, level + 1)
