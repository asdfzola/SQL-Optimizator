import re

from models import Query, Condition

MAX_TABLES = 4
MAX_CONDITIONS = 6


def _split_top_level(text: str, separator: str) -> list[str]:
    return [part.strip() for part in text.split(separator) if part.strip()]


def _parse_from_item(item: str) -> tuple[str, str]:
    """
    Parsira jednu FROM stavku u (naziv_tabele, alias).
    Podrzava: 'Tabela', 'Tabela alias', 'Tabela AS alias'.
    Ako alias nije naveden, alias == naziv_tabele.
    """
    item = item.strip()

    match = re.match(r"^(\w+)\s+AS\s+(\w+)$", item, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2)

    match = re.match(r"^(\w+)\s+(\w+)$", item)
    if match:
        return match.group(1), match.group(2)

    match = re.match(r"^(\w+)$", item)
    if match:
        return match.group(1), match.group(1)

    raise Exception(f"Ne mogu da parsiram FROM stavku: '{item}'")


def parse_query(sql: str) -> Query:
    sql = sql.strip()
    sql = sql.replace(";", "")

    select_match = re.search(r"SELECT(.*?)FROM", sql, re.IGNORECASE | re.DOTALL)
    if not select_match:
        raise Exception("Upit mora sadrzati SELECT i FROM klauzulu")

    from_match = re.search(r"FROM(.*?)(WHERE|ORDER BY|$)", sql, re.IGNORECASE | re.DOTALL)
    if not from_match:
        raise Exception("Upit mora sadrzati FROM klauzulu")

    select = _split_top_level(select_match.group(1), ",")
    if not select:
        raise Exception("SELECT lista ne sme biti prazna")

    from_items = _split_top_level(from_match.group(1), ",")
    if not from_items:
        raise Exception("FROM klauzula ne sme biti prazna")

    if len(from_items) > MAX_TABLES:
        raise Exception(f"Upit ne sme imati vise od {MAX_TABLES} tabele u FROM klauzuli")

    from_tables = []
    table_aliases = {}  # alias -> pravo ime tabele

    for item in from_items:
        table_name, alias = _parse_from_item(item)

        if alias in table_aliases:
            raise Exception(f"Alias '{alias}' je vec upotrebljen u FROM klauzuli")

        from_tables.append(table_name)
        table_aliases[alias] = table_name

    where_conditions = []

    where_match = re.search(r"WHERE(.*?)(ORDER BY|$)", sql, re.IGNORECASE | re.DOTALL)

    if where_match:
        where_part = where_match.group(1).strip()

        if where_part:
            conditions = re.split(r"\s+AND\s+", where_part, flags=re.IGNORECASE)

            if len(conditions) > MAX_CONDITIONS:
                raise Exception(f"WHERE klauzula ne sme imati vise od {MAX_CONDITIONS} uslova")

            for condition in conditions:
                match = re.match(r"(.+?)(!=|>=|<=|=|>|<)(.+)", condition.strip())
                if not match:
                    raise Exception(f"Ne mogu da parsiram uslov: '{condition.strip()}'")

                left = match.group(1).strip()
                operator = match.group(2)
                right = match.group(3).strip()

                where_conditions.append(Condition(left, operator, right))

    order_by = None

    order_match = re.search(r"ORDER BY\s+(.+)", sql, re.IGNORECASE)

    if order_match:
        order_by = order_match.group(1).strip()

    if order_by and "," in order_by:
        raise Exception("ORDER BY podrzava samo jedan atribut")

    return Query(
        select=select,
        from_tables=from_tables,
        where=where_conditions,
        order_by=order_by,
        table_aliases=table_aliases
    )